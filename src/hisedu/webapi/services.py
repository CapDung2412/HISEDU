from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal, Protocol

from hisedu.clip_encoder import ClipEncoder
from hisedu.config import Settings
from hisedu.ocr import PaddleOcrExtractor
from hisedu.pinecone_store import PineconeVectorStore
from hisedu.query import ImageQueryService, QueryMode

from .schemas import GeneratedLesson


RETURN_FIELDS = [
    "record_id",
    "chunk_id",
    "dataset_version",
    "question",
    "answer",
    "answer_type",
    "difficulty",
    "chapter_title",
    "lesson_title",
    "source_name",
    "source_url",
    "source_locator",
    "source_page_number",
    "review_status",
    "provenance_note",
    "content_checksum",
    "embedding_model",
]


@dataclass(slots=True)
class RetrievalResult:
    query: str
    matches: list[dict[str, Any]]
    score_kind: str = "cosine"


@dataclass(slots=True)
class GenerationResult:
    lesson: GeneratedLesson
    web_urls: set[str]


class RetrievalService(Protocol):
    async def search_text(self, question: str, *, top_k: int) -> RetrievalResult: ...

    async def search_image(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        top_k: int,
        mode: QueryMode,
        question: str | None,
    ) -> RetrievalResult: ...


class LessonGenerationService(Protocol):
    async def generate(
        self, question: str, matches: list[dict[str, Any]]
    ) -> GenerationResult | GeneratedLesson: ...


class HISEduRetrievalService:
    """Lazy adapter over existing CLIP/Pinecone code; never creates an index."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._inference_lock = Lock()
        self._encoder: ClipEncoder | None = None
        self._store: PineconeVectorStore | None = None
        self._index_dimension: int | None = None

    def _runtime(
        self, tower: Literal["text", "image"]
    ) -> tuple[Settings, ClipEncoder, PineconeVectorStore]:
        with self._lock:
            if self._encoder is None or self._store is None:
                settings = Settings.from_env(require_pinecone=True)
                encoder = ClipEncoder(
                    text_model_name=settings.text_model,
                    image_model_name=settings.image_model,
                    device=settings.device,
                    batch_size=settings.embedding_batch_size,
                )
                store = PineconeVectorStore(settings)
                self._encoder = encoder
                self._store = store
            dimension = (
                self._encoder.text_dimension
                if tower == "text"
                else self._encoder.image_dimension
            )
            if self._index_dimension is None:
                # Explicitly refuse index creation from the web process.
                self._store.ensure_index(dimension, create_if_missing=False)
                self._index_dimension = dimension
            elif dimension != self._index_dimension:
                raise ValueError(
                    f"{tower} embedding dimension {dimension} does not match "
                    f"Pinecone dimension {self._index_dimension}"
                )
        return self._store.settings, self._encoder, self._store

    async def search_text(self, question: str, *, top_k: int) -> RetrievalResult:
        return await asyncio.to_thread(self._search_text_sync, question, top_k)

    def _search_text_sync(self, question: str, top_k: int) -> RetrievalResult:
        _, encoder, store = self._runtime("text")
        with self._inference_lock:
            vector = encoder.encode_texts([question])[0]
        matches = store.query(vector, top_k=top_k, fields=RETURN_FIELDS)
        return RetrievalResult(query=question, matches=matches, score_kind="cosine")

    async def search_image(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        top_k: int,
        mode: QueryMode,
        question: str | None,
    ) -> RetrievalResult:
        return await asyncio.to_thread(
            self._search_image_sync, data, content_type, top_k, mode, question
        )

    def _search_image_sync(
        self,
        data: bytes,
        content_type: str,
        top_k: int,
        mode: QueryMode,
        question: str | None,
    ) -> RetrievalResult:
        first_tower = "text" if mode == "ocr" else "image"
        settings, encoder, store = self._runtime(first_tower)
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(content_type, ".img")
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_file.write(data)
                temp_path = Path(temp_file.name)
            ocr = (
                PaddleOcrExtractor(
                    language=settings.ocr_language,
                    min_line_score=settings.ocr_min_line_score,
                )
                if mode in {"ocr", "hybrid"}
                else None
            )
            with self._inference_lock:
                result = ImageQueryService(
                    encoder, store, ocr=ocr, min_score=settings.min_score
                ).query_image(temp_path, top_k=top_k, mode=mode)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        query = question or (result.get("ocr") or {}).get("text") or "Câu hỏi trong hình ảnh"
        score_kinds = {str(match.get("score_kind", "cosine")) for match in result["matches"]}
        score_kind = next(iter(score_kinds)) if len(score_kinds) == 1 else "mixed"
        return RetrievalResult(query=query, matches=result["matches"], score_kind=score_kind)
