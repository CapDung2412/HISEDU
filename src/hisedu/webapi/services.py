from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal, Protocol

from hisedu.clip_encoder import ClipEncoder
from hisedu.config import Settings
from hisedu.dataset import HISEduDataset, normalize_text
from hisedu.ocr import OcrResult, PaddleOcrExtractor
from hisedu.pinecone_store import PineconeVectorStore
from hisedu.query import ImageQueryService, QueryMode

from .errors import RetrievalTimeoutError
from .schemas import GeneratedLesson


logger = logging.getLogger("uvicorn.error")


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
    "source_grade",
    "source_book_series",
    "source_page_number",
    "source_page_status",
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
class OcrPreview:
    text: str
    line_count: int
    mean_score: float | None


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

    async def extract_image_text(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> OcrPreview: ...


class LessonGenerationService(Protocol):
    async def generate(
        self, question: str, matches: list[dict[str, Any]]
    ) -> GenerationResult | GeneratedLesson: ...


class HISEduRetrievalService:
    """Lazy adapter over existing CLIP/Pinecone code; never creates an index."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        pinecone_timeout_seconds: float = 8.0,
    ) -> None:
        if timeout_seconds <= 0 or pinecone_timeout_seconds <= 0:
            raise ValueError("retrieval timeouts must be positive")
        self._lock = Lock()
        self._dataset_lock = Lock()
        self._inference_lock = Lock()
        self._encoder: ClipEncoder | None = None
        self._store: PineconeVectorStore | None = None
        self._ocr: PaddleOcrExtractor | None = None
        self._exact_text_index: dict[str, list[dict[str, Any]]] | None = None
        self._index_dimension: int | None = None
        self._timeout_seconds = float(timeout_seconds)
        self._pinecone_timeout_seconds = float(pinecone_timeout_seconds)

    async def warmup_local_dataset(self) -> None:
        """Load the small JSON repository used by the exact-question fast path."""

        await asyncio.to_thread(self._ensure_exact_text_index)

    async def warmup_text(self) -> None:
        """Load the text tower and verify the Pinecone query path once.

        Doing this during application startup keeps the first student request
        from paying the relatively expensive local CLIP cold-start cost.
        """

        await asyncio.to_thread(self._warmup_text_sync)

    def _warmup_text_sync(self) -> None:
        _, encoder, store = self._runtime("text")
        with self._inference_lock:
            vector = encoder.encode_texts(["Lịch sử Việt Nam"])[0]
        store.query(vector, top_k=1, fields=["record_id"])

    def _ensure_exact_text_index(self) -> dict[str, list[dict[str, Any]]]:
        """Build a trusted local lookup without loading CLIP or contacting Pinecone.

        The teaching dataset is the canonical JSON repository. Exact questions can
        therefore be served from it directly; paraphrases continue through the
        aligned CLIP/Pinecone path below.
        """

        with self._dataset_lock:
            if self._exact_text_index is not None:
                return self._exact_text_index
            index: dict[str, list[dict[str, Any]]] = {}
            try:
                settings = Settings.from_env(require_pinecone=False)
                records = HISEduDataset(
                    settings.questions_dir, settings.answers_dir
                ).load()
                for record in records:
                    document = record.pinecone_document(
                        [1.0], embedding_model="local-json-exact"
                    )
                    fields = {
                        field: document[field]
                        for field in RETURN_FIELDS
                        if field in document
                    }
                    match = {
                        "id": record.chunk_id,
                        "score": 1.0,
                        "fields": fields,
                        "confidence_status": "exact_match",
                        "retrieval_path": "local_exact",
                    }
                    key = normalize_text(record.question).casefold()
                    index.setdefault(key, []).append(match)
            except Exception as exc:
                # The cloud retrieval path remains available if a deployment does
                # not ship the local repository. Avoid logging paths or record data.
                logger.warning(
                    "hisedu_local_dataset status=unavailable error_type=%s",
                    type(exc).__name__,
                )
            self._exact_text_index = index
            return index

    def _search_exact_text(
        self, question: str, top_k: int
    ) -> RetrievalResult | None:
        key = normalize_text(question).casefold()
        matches = self._ensure_exact_text_index().get(key)
        if not matches:
            return None
        return RetrievalResult(
            query=normalize_text(question),
            matches=matches[:top_k],
            score_kind="mixed",
        )

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
                    # Ingest already downloaded the exact models used to build
                    # the index. Avoid slow Hugging Face network probes on each
                    # local backend cold start.
                    local_files_only=True,
                )
                store = PineconeVectorStore(
                    settings,
                    max_attempts=1,
                    request_timeout_seconds=self._pinecone_timeout_seconds,
                )
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
        exact = await asyncio.to_thread(self._search_exact_text, question, top_k)
        if exact is not None:
            return exact
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._search_text_sync, question, top_k),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise RetrievalTimeoutError() from exc

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
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._search_image_sync,
                    data,
                    content_type,
                    top_k,
                    mode,
                    question,
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise RetrievalTimeoutError() from exc

    async def extract_image_text(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
    ) -> OcrPreview:
        """Read a question photo locally without contacting Pinecone or OpenAI."""

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._extract_image_text_sync,
                    data,
                    content_type,
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise RetrievalTimeoutError(
                "Nhận dạng chữ trong ảnh mất quá nhiều thời gian. Em hãy thử ảnh rõ hơn."
            ) from exc
        return OcrPreview(
            # Preserve OCR line boundaries in the editable preview. The final
            # text query is normalized only after the student confirms it.
            text="\n".join(result.lines),
            line_count=len(result.lines),
            mean_score=result.mean_score,
        )

    def _extract_image_text_sync(
        self,
        data: bytes,
        content_type: str,
    ) -> OcrResult:
        settings = Settings.from_env(require_pinecone=False)
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
            with self._lock:
                if self._ocr is None:
                    self._ocr = PaddleOcrExtractor(
                        language=settings.ocr_language,
                        min_line_score=settings.ocr_min_line_score,
                    )
                ocr = self._ocr
            # PaddleOCR's predictor is not thread-safe. Reuse the existing
            # inference lock so preview and legacy hybrid-image requests cannot
            # execute it at the same time.
            with self._inference_lock:
                return ocr.extract(temp_path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def _search_image_sync(
        self,
        data: bytes,
        content_type: str,
        top_k: int,
        mode: QueryMode,
        question: str | None,
    ) -> RetrievalResult:
        # Uploaded question photos are read as text first. The heavier image
        # tower is initialized only when explicit CLIP mode/fallback needs it.
        first_tower = "text" if mode in {"ocr", "hybrid"} else "image"
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
            ocr = None
            if mode in {"ocr", "hybrid"}:
                # Keep the local OCR pipeline warm; rebuilding its models for
                # every uploaded photo is both slow and memory-intensive.
                with self._lock:
                    if self._ocr is None:
                        self._ocr = PaddleOcrExtractor(
                            language=settings.ocr_language,
                            min_line_score=settings.ocr_min_line_score,
                        )
                    ocr = self._ocr
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
