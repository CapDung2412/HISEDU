from __future__ import annotations

import os
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import normalize_text


class OcrError(RuntimeError):
    """Raised when OCR is unavailable or produces no usable text."""


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    lines: tuple[str, ...]
    scores: tuple[float, ...]
    mean_score: float | None


class PaddleOcrExtractor:
    """Optional local PaddleOCR 3.x adapter for Vietnamese phone photos."""

    def __init__(
        self,
        *,
        language: str = "vi",
        min_line_score: float = 0.50,
        pipeline: Any = None,
    ) -> None:
        if not 0.0 <= min_line_score <= 1.0:
            raise ValueError("min_line_score must be between 0 and 1")
        self.language = language
        self.min_line_score = min_line_score
        self._pipeline = pipeline

    def _ensure_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        # PaddleOCR 3.7 + PaddlePaddle 3.3 can select oneDNN automatically on
        # Windows CPU and fail with ConvertPirAttribute2RuntimeAttribute.
        # The plain Paddle backend is slower but stable; an explicit user value
        # still takes precedence over this safe default.
        os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrError(
                "PaddleOCR is optional; install `python -m pip install -e \".[ocr]\"` "
                "and a supported PaddlePaddle inference engine"
            ) from exc
        try:
            options: dict[str, Any] = {
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
            }
            if self.language == "vi":
                # Mobile models are substantially faster on local Windows CPU
                # while the Latin recognizer retains Vietnamese diacritics.
                options.update(
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
                )
            else:
                options["lang"] = self.language
            self._pipeline = PaddleOCR(**options)
        except Exception as exc:
            raise OcrError(
                f"Could not initialize PaddleOCR: {type(exc).__name__}: {exc}"
            ) from exc
        return self._pipeline

    @staticmethod
    def _list(value: Any) -> list[Any]:
        if hasattr(value, "tolist"):
            value = value.tolist()
        return list(value or [])

    def extract(self, image_path: Path | str) -> OcrResult:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        pipeline = self._ensure_pipeline()
        accepted_lines: list[str] = []
        accepted_scores: list[float] = []
        try:
            for result in pipeline.predict(str(path)):
                payload = getattr(result, "json", result)
                if callable(payload):
                    payload = payload()
                if not isinstance(payload, dict):
                    continue
                data = payload.get("res", payload)
                texts = self._list(data.get("rec_texts"))
                scores = self._list(data.get("rec_scores"))
                if len(scores) < len(texts):
                    scores.extend([1.0] * (len(texts) - len(scores)))
                for raw_text, raw_score in zip(texts, scores):
                    text = normalize_text(str(raw_text))
                    score = float(raw_score)
                    if text and score >= self.min_line_score:
                        accepted_lines.append(text)
                        accepted_scores.append(score)
        except Exception as exc:
            raise OcrError(
                f"PaddleOCR inference failed: {type(exc).__name__}: {exc}"
            ) from exc
        combined = normalize_text(" ".join(accepted_lines))
        if not combined:
            raise OcrError(
                f"OCR found no text at or above score {self.min_line_score:.2f}"
            )
        return OcrResult(
            text=combined,
            lines=tuple(accepted_lines),
            scores=tuple(accepted_scores),
            mean_score=(statistics.mean(accepted_scores) if accepted_scores else None),
        )
