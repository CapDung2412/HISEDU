from __future__ import annotations

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
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrError(
                "PaddleOCR is optional; install `python -m pip install -e \".[ocr]\"` "
                "and a supported PaddlePaddle inference engine"
            ) from exc
        self._pipeline = PaddleOCR(
            lang=self.language,
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
        )
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

