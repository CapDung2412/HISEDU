from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .clip_encoder import ClipEncoder
from .ocr import OcrError, PaddleOcrExtractor
from .pinecone_store import PineconeVectorStore


QueryMode = Literal["clip", "ocr", "hybrid"]


def _confidence_status(score: float | None, threshold: float | None) -> str:
    if threshold is None:
        return "not_calibrated"
    if score is None:
        return "no_raw_similarity"
    return "accepted" if score >= threshold else "below_threshold"


def reciprocal_rank_fusion(
    branches: dict[str, list[dict[str, Any]]], *, k: int = 60
) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}
    for branch_name, matches in branches.items():
        for rank, match in enumerate(matches, start=1):
            record_id = str(match["id"])
            item = fused.setdefault(
                record_id,
                {
                    "id": record_id,
                    "fields": dict(match.get("fields", {})),
                    "rrf_score": 0.0,
                    "branch_scores": {},
                },
            )
            item["rrf_score"] += 1.0 / (k + rank)
            item["branch_scores"][branch_name] = float(match["score"])
    return sorted(
        fused.values(),
        key=lambda item: (
            item["rrf_score"],
            max(item["branch_scores"].values(), default=float("-inf")),
            item["id"],
        ),
        reverse=True,
    )


class ImageQueryService:
    def __init__(
        self,
        encoder: ClipEncoder,
        store: PineconeVectorStore,
        *,
        ocr: PaddleOcrExtractor | None = None,
        min_score: float | None = None,
    ) -> None:
        self.encoder = encoder
        self.store = store
        self.ocr = ocr
        if min_score is not None and not -1.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between -1 and 1")
        self.min_score = min_score

    def _clip_branch(self, image_path: Path, candidate_k: int) -> list[dict[str, Any]]:
        vector = self.encoder.encode_images([image_path])[0]
        return self.store.query(vector, top_k=candidate_k)

    def _ocr_branch(
        self, image_path: Path, candidate_k: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.ocr is None:
            raise OcrError("OCR mode requested but no OCR extractor is configured")
        ocr_result = self.ocr.extract(image_path)
        vector = self.encoder.encode_texts([ocr_result.text])[0]
        matches = self.store.query(vector, top_k=candidate_k)
        return matches, {
            "text": ocr_result.text,
            "line_count": len(ocr_result.lines),
            "mean_line_score": ocr_result.mean_score,
        }

    def query_image(
        self,
        image_path: Path | str,
        *,
        top_k: int = 5,
        mode: QueryMode = "hybrid",
    ) -> dict[str, Any]:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if mode not in {"clip", "ocr", "hybrid"}:
            raise ValueError(f"Unsupported query mode: {mode}")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        candidate_k = max(top_k * 3, 10) if mode == "hybrid" else top_k
        branches: dict[str, list[dict[str, Any]]] = {}
        ocr_details: dict[str, Any] | None = None
        ocr_error: str | None = None
        if mode in {"clip", "hybrid"}:
            branches["clip"] = self._clip_branch(path, candidate_k)
        if mode in {"ocr", "hybrid"}:
            try:
                branches["ocr"], ocr_details = self._ocr_branch(path, candidate_k)
            except OcrError as exc:
                if mode == "ocr":
                    raise
                ocr_error = str(exc)

        if len(branches) == 1:
            branch_name, raw_matches = next(iter(branches.items()))
            matches = [
                {
                    "id": match["id"],
                    "fields": dict(match.get("fields", {})),
                    "score": float(match["score"]),
                    "score_kind": "cosine",
                    "branch_scores": {branch_name: float(match["score"])},
                    "confidence_status": _confidence_status(
                        float(match["score"]), self.min_score
                    ),
                }
                for match in raw_matches[:top_k]
            ]
        else:
            fused = reciprocal_rank_fusion(branches)[:top_k]
            matches = []
            for match in fused:
                raw_score = max(match["branch_scores"].values(), default=None)
                matches.append(
                    {
                        "id": match["id"],
                        "fields": match["fields"],
                        "branch_scores": match["branch_scores"],
                        "score": match["rrf_score"],
                        "score_kind": "reciprocal_rank_fusion",
                        "confidence_status": _confidence_status(
                            raw_score, self.min_score
                        ),
                    }
                )
        return {
            "image": str(path.resolve()),
            "mode_requested": mode,
            "branches_used": sorted(branches),
            "threshold": self.min_score,
            "ocr": ocr_details,
            "ocr_error": ocr_error,
            "matches": matches,
        }
