from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, AsyncIterator, Awaitable, Callable, Literal

from fastapi import Depends, FastAPI, File, Form, Path, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hisedu.dataset import normalize_text
from hisedu.ocr import OcrError

from .cache import TTLCache
from .errors import (
    AiServiceError,
    ImageTooLargeError,
    KnowledgeNotFoundError,
    OcrRecognitionError,
    RequestTimeoutError,
    RetrievalServiceError,
    WebApiError,
)
from .feedback_store import FeedbackStore
from .openai_adapter import OpenAIResponsesAdapter
from .progress_stream import publish_partial_result, publish_progress, stream_operation
from .quiz_store import QuizStore
from .rate_limit import InMemoryRateLimiter
from .schemas import (
    AnswerFeedbackRequest,
    AnswerFeedbackResponse,
    AskResponse,
    ErrorDetail,
    ErrorResponse,
    GeneratedLesson,
    GeneratedLessonCore,
    HealthResponse,
    OcrPreviewResponse,
    QuestionRequest,
    Quiz,
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    RetrievalInfo,
    Source,
    Video,
)
from .services import (
    GenerationResult,
    HISEduRetrievalService,
    LessonGenerationService,
    RetrievalResult,
    RetrievalService,
)
from .settings import WebSettings
from .validation import sanitize_lesson, validate_image
from .video_recommender import (
    VideoRecommendationService,
    YouTubeVideoRecommender,
)


logger = logging.getLogger("uvicorn.error")


@dataclass(slots=True)
class CachedLesson:
    lesson: object
    sources: list[Source]
    videos: list[Video]


@dataclass(slots=True)
class _KeyedLockEntry:
    lock: asyncio.Lock
    users: int = 0


class _KeyedLockPool:
    """Serialize duplicate cache keys without blocking unrelated questions."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._entries: dict[str, _KeyedLockEntry] = {}

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[None]:
        async with self._guard:
            entry = self._entries.setdefault(key, _KeyedLockEntry(asyncio.Lock()))
            entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            async with self._guard:
                entry.users -= 1
                if entry.users == 0 and self._entries.get(key) is entry:
                    self._entries.pop(key, None)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex)


def _record_timing(request: Request, stage: str, started_at: float) -> None:
    duration_ms = (time.perf_counter() - started_at) * 1_000
    timings = getattr(request.state, "server_timings", None)
    if isinstance(timings, list):
        timings.append((stage, duration_ms))
    logger.info(
        "hisedu_stage request_id=%s stage=%s duration_ms=%.1f",
        _request_id(request),
        stage,
        duration_ms,
    )


def _error_chain(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    for _ in range(4):
        if current is None:
            break
        message = str(current).replace("\r", " ").replace("\n", " ")[:240]
        parts.append(f"{type(current).__name__}: {message}")
        current = current.__cause__
    return " <- ".join(parts)


def _error_response(request: Request, *, status: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=_request_id(request))
    )
    return JSONResponse(status_code=status, content=payload.model_dump(mode="json"))


def _cache_key(
    question: str,
    result: RetrievalResult,
    *,
    prompt_version: str,
    model: str,
    web_search: bool,
    video_provider_version: str,
) -> str:
    records = [
        {
            "id": str(match.get("id", "")),
            "version": str((match.get("fields") or {}).get("dataset_version", "")),
            "checksum": str((match.get("fields") or {}).get("content_checksum", "")),
        }
        for match in result.matches
    ]
    payload = {
        "question": normalize_text(question).casefold(),
        "records": records,
        "prompt_version": prompt_version,
        "model": model,
        "web_search": web_search,
        "video_provider_version": video_provider_version,
        "schema_version": "hisedu-web-response-v4-youtube-api",
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _text_retrieval_cache_key(question: str, *, top_k: int) -> str:
    payload = {
        "kind": "text",
        "question": normalize_text(question).casefold(),
        "top_k": top_k,
        "schema_version": "hisedu-retrieval-v1",
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _image_retrieval_cache_key(
    data: bytes,
    *,
    content_type: str,
    top_k: int,
    mode: str,
    question: str | None,
) -> str:
    # Only the one-way digest is retained in the key. The uploaded bytes are
    # never stored in the process cache.
    payload = {
        "kind": "image",
        "image_sha256": hashlib.sha256(data).hexdigest(),
        "content_type": content_type,
        "top_k": top_k,
        "mode": mode,
        "question": normalize_text(question).casefold() if question else "",
        "schema_version": "hisedu-retrieval-v1",
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _score_kind(value: str) -> Literal["cosine", "reciprocal_rank_fusion", "mixed"]:
    if value in {"cosine", "reciprocal_rank_fusion", "mixed"}:
        return value
    return "mixed"


def create_app(
    *,
    retrieval_service: RetrievalService | None = None,
    ai_service: LessonGenerationService | None = None,
    settings: WebSettings | None = None,
    response_cache: TTLCache[CachedLesson] | None = None,
    retrieval_cache: TTLCache[RetrievalResult] | None = None,
    quiz_store: QuizStore | None = None,
    feedback_store: FeedbackStore | None = None,
    video_recommender: VideoRecommendationService | None = None,
) -> FastAPI:
    config = settings or WebSettings.from_env()
    runtime_retrieval = retrieval_service or HISEduRetrievalService(
        timeout_seconds=config.retrieval_timeout_seconds,
        pinecone_timeout_seconds=config.pinecone_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        warmup_task: asyncio.Task[None] | None = None
        if isinstance(runtime_retrieval, HISEduRetrievalService):
            # The 327-record JSON lookup is tiny and makes canonical lesson
            # questions immediately available. CLIP/Pinecone warmup continues
            # in the background so it no longer delays Uvicorn's Ready state.
            await runtime_retrieval.warmup_local_dataset()

            async def warm_remote_retrieval() -> None:
                warmup_started = time.perf_counter()
                try:
                    await runtime_retrieval.warmup_text()
                    logger.info(
                        "hisedu_retrieval_warmup status=ready duration_ms=%.1f",
                        (time.perf_counter() - warmup_started) * 1_000,
                    )
                except Exception as exc:
                    logger.warning(
                        "hisedu_retrieval_warmup status=failed duration_ms=%.1f chain=%s",
                        (time.perf_counter() - warmup_started) * 1_000,
                        _error_chain(exc),
                    )

            warmup_task = asyncio.create_task(
                warm_remote_retrieval(), name="hisedu-retrieval-warmup"
            )
        try:
            yield
        finally:
            if warmup_task is not None:
                if not warmup_task.done():
                    warmup_task.cancel()
                await asyncio.gather(warmup_task, return_exceptions=True)

    app = FastAPI(
        title="HISEDU API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.state.settings = config
    app.state.retrieval = runtime_retrieval
    app.state.ai = ai_service or OpenAIResponsesAdapter(config)
    app.state.response_cache = response_cache or TTLCache(
        ttl_seconds=config.cache_ttl_seconds, max_items=512
    )
    app.state.retrieval_cache = retrieval_cache or TTLCache(
        ttl_seconds=config.cache_ttl_seconds, max_items=512
    )
    app.state.quiz_store = quiz_store or QuizStore(ttl_seconds=config.quiz_ttl_seconds)
    app.state.feedback_store = feedback_store or FeedbackStore(
        config.feedback_path,
        context_ttl_seconds=config.feedback_context_ttl_seconds,
        max_file_bytes=config.feedback_max_bytes,
    )
    app.state.video_recommender = video_recommender or YouTubeVideoRecommender(
        config.youtube_api_key,
        timeout_seconds=config.youtube_timeout_seconds,
        cache_ttl_seconds=config.youtube_cache_ttl_seconds,
    )
    # Duplicate questions share a lock, while different questions can be
    # generated concurrently instead of queueing behind one global lock.
    app.state.generation_locks = _KeyedLockPool()
    app.state.retrieval_locks = _KeyedLockPool()
    app.state.rate_limiter = InMemoryRateLimiter(
        max_requests=config.rate_limit_requests,
        window_seconds=config.rate_limit_window_seconds,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        total_started = time.perf_counter()
        inbound = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            inbound
            if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", inbound)
            else uuid.uuid4().hex
        )
        request.state.server_timings = []
        response = await call_next(request)
        _record_timing(request, "total", total_started)
        response.headers["Server-Timing"] = ", ".join(
            f"{name};dur={duration_ms:.1f}"
            for name, duration_ms in request.state.server_timings
        )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(WebApiError)
    async def domain_error(request: Request, exc: WebApiError):
        return _error_response(
            request, status=exc.status_code, code=exc.code, message=exc.message
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error_response(
            request,
            status=422,
            code="INVALID_REQUEST",
            message="Dữ liệu gửi lên không hợp lệ.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        return _error_response(
            request,
            status=500,
            code="INTERNAL_ERROR",
            message="Đã xảy ra lỗi. Vui lòng thử lại sau.",
        )

    def enforce_rate_limit(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        app.state.rate_limiter.check(client)

    async def cached_retrieval(
        key: str, loader: Callable[[], Awaitable[RetrievalResult]]
    ) -> RetrievalResult:
        cached = app.state.retrieval_cache.get(key)
        if cached is not None:
            return cached
        # Singleflight: concurrent duplicates wait for the first retrieval,
        # then consume its cached result instead of querying Pinecone again.
        async with app.state.retrieval_locks.hold(key):
            cached = app.state.retrieval_cache.get(key)
            if cached is not None:
                return cached
            result = await loader()
            app.state.retrieval_cache.set(key, result)
            return result

    async def build_response(result: RetrievalResult, request: Request) -> AskResponse:
        if not result.matches:
            raise KnowledgeNotFoundError()
        # A calibrated rejection must stop before any paid or generative work.
        # Uncalibrated results retain the existing behavior until a threshold
        # has been measured and configured for the retrieval pipeline.
        if result.matches[0].get("confidence_status") == "below_threshold":
            raise KnowledgeNotFoundError()

        await publish_progress(
            request,
            "generation",
            "Đang đối chiếu dữ kiện và biên soạn câu trả lời…",
        )

        async def recommend_videos() -> list[Video]:
            started = time.perf_counter()
            try:
                topics = [
                    str((match.get("fields") or {}).get(field) or "")
                    for match in result.matches
                    for field in (
                        "question",
                        "chapter_title",
                        "lesson_title",
                        "source_locator",
                    )
                ]
                return await app.state.video_recommender.recommend(
                    question=result.query,
                    topics=topics,
                    limit=6,
                )
            except Exception as exc:
                # Video enrichment is optional and must fail closed. Do not
                # log exception text because URLs may contain an API key.
                logger.warning(
                    "hisedu_youtube_error request_id=%s error_type=%s",
                    _request_id(request),
                    type(exc).__name__,
                )
                return []
            finally:
                _record_timing(request, "youtube_video", started)

        key = _cache_key(
            result.query,
            result,
            prompt_version=config.prompt_version,
            model=config.openai_model,
            web_search=config.enable_web_search,
            video_provider_version=str(
                getattr(app.state.video_recommender, "provider_version", "unknown")
            ),
        )
        cached = app.state.response_cache.get(key)
        partial_published = False

        async def publish_core(
            core: GeneratedLessonCore, returned_urls: set[str]
        ) -> None:
            nonlocal partial_published
            partial_lesson = GeneratedLesson.model_validate(
                {**core.model_dump(), "quiz": []}
            )
            cleaned_core, core_sources, _ = sanitize_lesson(
                partial_lesson,
                result.matches,
                returned_web_urls=returned_urls,
            )
            await publish_partial_result(
                request,
                {
                    "request_id": _request_id(request),
                    "question": result.query,
                    "answer": cleaned_core.answer.model_dump(mode="json"),
                    "mindmap": cleaned_core.mindmap.model_dump(mode="json"),
                    "sources": [
                        source.model_dump(mode="json") for source in core_sources
                    ],
                    "limitations": list(cleaned_core.limitations),
                },
            )
            partial_published = True

        if cached is None:
            lock_started = time.perf_counter()
            async with app.state.generation_locks.hold(key):
                _record_timing(request, "generation_lock", lock_started)
                cached = app.state.response_cache.get(key)
                if cached is None:
                    # YouTube uses only the concise question/retrieved topic,
                    # so it can run beside generation instead of adding up to
                    # five seconds after the lesson is already complete.
                    video_task = asyncio.create_task(
                        recommend_videos(), name="hisedu-youtube-video"
                    )
                    try:
                        ai_started = time.perf_counter()
                        try:
                            generate_with_progress = getattr(
                                app.state.ai, "generate_with_core_progress", None
                            )
                            if callable(generate_with_progress):
                                generated = await generate_with_progress(
                                    result.query,
                                    result.matches,
                                    on_core_ready=publish_core,
                                )
                            else:
                                generated = await app.state.ai.generate(
                                    result.query, result.matches
                                )
                        except WebApiError as exc:
                            logger.warning(
                                "hisedu_ai_error request_id=%s chain=%s",
                                _request_id(request),
                                _error_chain(exc),
                            )
                            raise
                        except Exception as exc:
                            logger.warning(
                                "hisedu_ai_error request_id=%s chain=%s",
                                _request_id(request),
                                _error_chain(exc),
                            )
                            raise AiServiceError() from exc
                        finally:
                            _record_timing(request, "openai", ai_started)
                        if isinstance(generated, GenerationResult):
                            raw_lesson = generated.lesson
                            returned_urls = generated.web_urls
                        else:
                            raw_lesson = generated
                            returned_urls = set()
                        cleaned, sources, _generated_videos = sanitize_lesson(
                            raw_lesson,
                            result.matches,
                            returned_web_urls=returned_urls,
                        )
                        if not partial_published:
                            await publish_core(
                                GeneratedLessonCore.model_validate(
                                    cleaned.model_dump(exclude={"quiz"})
                                ),
                                returned_urls,
                            )
                        # Only the allowlisted YouTube provider may populate
                        # videos; model-generated URLs are always discarded.
                        await publish_progress(
                            request,
                            "enrichment",
                            "Đang chọn video và bài luyện tập phù hợp…",
                        )
                        videos = await video_task
                        cleaned = cleaned.model_copy(update={"videos": videos})
                        cached = CachedLesson(
                            lesson=cleaned, sources=sources, videos=videos
                        )
                        app.state.response_cache.set(key, cached)
                    finally:
                        if not video_task.done():
                            video_task.cancel()
                        await asyncio.gather(video_task, return_exceptions=True)
        if not partial_published:
            # A response-cache hit is already sanitized. Reuse its public
            # sources so evidence metadata stays identical to the final event.
            await publish_partial_result(
                request,
                {
                    "request_id": _request_id(request),
                    "question": result.query,
                    "answer": cached.lesson.answer.model_dump(mode="json"),
                    "mindmap": cached.lesson.mindmap.model_dump(mode="json"),
                    "sources": [
                        source.model_dump(mode="json") for source in cached.sources
                    ],
                    "limitations": list(cached.lesson.limitations),
                },
            )
            partial_published = True
        await publish_progress(
            request,
            "finalizing",
            "Đang sắp xếp bài học để hiển thị…",
        )
        lesson = cached.lesson
        quiz = app.state.quiz_store.create(lesson.quiz)
        limitations = list(lesson.limitations)
        if any(source.page_status == "unverified" for source in cached.sources):
            limitations.append(
                "Dữ liệu hiện tại chưa ghi nhận số trang SGK đã xác minh; hệ thống "
                "không hiển thị nguồn đó như trích dẫn SGK."
            )
        top = result.matches[0]
        low_confidence = top.get("confidence_status") == "below_threshold"
        if top.get("confidence_status") in {None, "not_calibrated"}:
            limitations.append(
                "Ngưỡng độ tin cậy chưa được hiệu chỉnh; điểm tương đồng không phải xác suất."
            )
        matched_ids = [str(match.get("id", "")) for match in result.matches]
        answer_id = app.state.feedback_store.register(
            request_id=_request_id(request),
            question=result.query,
            answer=lesson.answer,
            sources=cached.sources,
            matched_ids=matched_ids,
        )
        return AskResponse(
            request_id=_request_id(request),
            answer_id=answer_id,
            question=result.query,
            answer=lesson.answer,
            mindmap=lesson.mindmap,
            videos=cached.videos,
            sources=cached.sources,
            quiz=quiz,
            retrieval=RetrievalInfo(
                matched_ids=matched_ids,
                score_kind=_score_kind(result.score_kind),
                low_confidence=low_confidence,
            ),
            limitations=list(dict.fromkeys(limitations)),
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        # Deliberately does not contact Pinecone, load CLIP, or call OpenAI.
        return HealthResponse(
            services={
                "retrieval": "configured",
                "ai": "configured" if config.chatgpt_api_key else "missing_api_key",
                "youtube": (
                    "configured" if config.youtube_api_key else "missing_api_key"
                ),
            }
        )

    @app.post(
        "/api/questions/ocr",
        response_model=OcrPreviewResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def preview_question_ocr(
        request: Request,
        file: Annotated[UploadFile, File(...)],
    ) -> OcrPreviewResponse:
        """Return editable local OCR text without retrieval or generation."""

        data = await file.read(config.max_image_bytes + 1)
        filename = file.filename or "upload.img"
        await file.close()
        if len(data) > config.max_image_bytes:
            raise ImageTooLargeError()
        claimed_mime = validate_image(
            data, file.content_type or "", max_pixels=config.max_image_pixels
        )
        ocr_started = time.perf_counter()
        try:
            preview = await asyncio.wait_for(
                app.state.retrieval.extract_image_text(
                    data,
                    filename=filename,
                    content_type=claimed_mime,
                ),
                timeout=float(config.retrieval_timeout_seconds),
            )
        except asyncio.TimeoutError as exc:
            raise RequestTimeoutError(
                "Nhận dạng chữ trong ảnh mất quá nhiều thời gian. Em hãy thử ảnh rõ hơn."
            ) from exc
        except OcrError as exc:
            raise OcrRecognitionError() from exc
        except WebApiError:
            raise
        except Exception as exc:
            logger.warning(
                "hisedu_ocr_error request_id=%s error_type=%s",
                _request_id(request),
                type(exc).__name__,
            )
            raise OcrRecognitionError() from exc
        finally:
            _record_timing(request, "ocr", ocr_started)

        text = "\n".join(
            normalize_text(line)
            for line in preview.text.splitlines()
            if normalize_text(line)
        )[:2_000].strip()
        if len(text) < 3:
            raise OcrRecognitionError()
        mean_score = preview.mean_score
        return OcrPreviewResponse(
            text=text,
            line_count=min(preview.line_count, 500),
            mean_score=mean_score,
            needs_review=mean_score is None or mean_score < 0.75,
        )

    @app.post(
        "/api/questions/ask",
        response_model=AskResponse,
        responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def ask(payload: QuestionRequest, request: Request) -> AskResponse:
        async def process() -> AskResponse:
            await publish_progress(
                request,
                "retrieval",
                "Đang tìm và đối chiếu sử liệu liên quan…",
            )
            retrieval_started = time.perf_counter()
            normalized_question = normalize_text(payload.question)
            retrieval_key = _text_retrieval_cache_key(
                normalized_question, top_k=payload.top_k
            )
            try:
                result = await cached_retrieval(
                    retrieval_key,
                    lambda: app.state.retrieval.search_text(
                        normalized_question, top_k=payload.top_k
                    ),
                )
                # Cache keys intentionally ignore casing; echo this request's
                # normalized wording rather than the first caller's casing.
                result = RetrievalResult(
                    query=normalized_question,
                    matches=result.matches,
                    score_kind=result.score_kind,
                )
            except WebApiError:
                raise
            except Exception as exc:
                logger.warning(
                    "hisedu_retrieval_error request_id=%s chain=%s",
                    _request_id(request),
                    _error_chain(exc),
                )
                raise RetrievalServiceError() from exc
            finally:
                _record_timing(request, "retrieval", retrieval_started)
            return await build_response(result, request)

        try:
            return await asyncio.wait_for(
                process(), timeout=float(config.request_timeout_seconds)
            )
        except asyncio.TimeoutError as exc:
            raise RequestTimeoutError() from exc

    @app.post(
        "/api/questions/ask-image",
        response_model=AskResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def ask_image(
        request: Request,
        file: Annotated[UploadFile, File(...)],
        question: Annotated[str | None, Form(max_length=2_000)] = None,
        top_k: Annotated[int, Form(ge=1, le=10)] = 3,
        mode: Annotated[Literal["clip", "ocr", "hybrid"], Form()] = "hybrid",
    ) -> AskResponse:
        data = await file.read(config.max_image_bytes + 1)
        await file.close()
        if len(data) > config.max_image_bytes:
            raise ImageTooLargeError()
        claimed_mime = validate_image(
            data, file.content_type or "", max_pixels=config.max_image_pixels
        )
        normalized_question = normalize_text(question) if question else None
        if normalized_question is not None and len(normalized_question) < 3:
            raise RequestValidationError([])
        retrieval_key = _image_retrieval_cache_key(
            data,
            content_type=claimed_mime,
            top_k=top_k,
            mode=mode,
            question=normalized_question,
        )

        async def process() -> AskResponse:
            await publish_progress(
                request,
                "retrieval",
                "Đang nhận dạng ảnh và tìm sử liệu liên quan…",
            )
            retrieval_started = time.perf_counter()
            try:
                result = await cached_retrieval(
                    retrieval_key,
                    lambda: app.state.retrieval.search_image(
                        data,
                        filename=file.filename or "upload.img",
                        content_type=claimed_mime,
                        top_k=top_k,
                        mode=mode,
                        question=normalized_question,
                    ),
                )
                if normalized_question is not None:
                    result = RetrievalResult(
                        query=normalized_question,
                        matches=result.matches,
                        score_kind=result.score_kind,
                    )
            except WebApiError:
                raise
            except Exception as exc:
                logger.warning(
                    "hisedu_retrieval_error request_id=%s chain=%s",
                    _request_id(request),
                    _error_chain(exc),
                )
                raise RetrievalServiceError() from exc
            finally:
                _record_timing(request, "retrieval", retrieval_started)
            return await build_response(result, request)

        try:
            return await asyncio.wait_for(
                process(), timeout=float(config.request_timeout_seconds)
            )
        except asyncio.TimeoutError as exc:
            raise RequestTimeoutError() from exc

    @app.post(
        "/api/questions/ask-stream",
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def ask_stream(payload: QuestionRequest, request: Request):
        """SSE variant of ``ask``; the existing JSON endpoint stays stable."""

        return stream_operation(
            request=request,
            request_id=_request_id(request),
            operation=lambda: ask(payload, request),
        )

    @app.post(
        "/api/questions/ask-image-stream",
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def ask_image_stream(
        request: Request,
        file: Annotated[UploadFile, File(...)],
        question: Annotated[str | None, Form(max_length=2_000)] = None,
        top_k: Annotated[int, Form(ge=1, le=10)] = 3,
        mode: Annotated[Literal["clip", "ocr", "hybrid"], Form()] = "hybrid",
    ):
        """SSE variant of image search, including the real OCR/retrieval stage."""

        return stream_operation(
            request=request,
            request_id=_request_id(request),
            operation=lambda: ask_image(
                request=request,
                file=file,
                question=question,
                top_k=top_k,
                mode=mode,
            ),
        )

    @app.post(
        "/api/quizzes/{quiz_id}/submit",
        response_model=QuizSubmitResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def submit_quiz(
        quiz_id: str, payload: QuizSubmitRequest
    ) -> QuizSubmitResponse:
        return app.state.quiz_store.submit(quiz_id, payload.answers)

    @app.post(
        "/api/quizzes/{quiz_id}/answer",
        response_model=QuizAnswerResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def answer_quiz_question(
        quiz_id: str, payload: QuizAnswerRequest
    ) -> QuizAnswerResponse:
        return app.state.quiz_store.answer_one(
            quiz_id,
            question_id=payload.question_id,
            option_id=payload.option_id,
        )

    @app.post(
        "/api/quizzes/{quiz_id}/reset",
        response_model=Quiz,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def reset_quiz(quiz_id: str) -> Quiz:
        return app.state.quiz_store.reset(quiz_id)

    @app.post(
        "/api/answers/{answer_id}/feedback",
        response_model=AnswerFeedbackResponse,
        status_code=201,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def submit_answer_feedback(
        answer_id: Annotated[
            str,
            Path(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"),
        ],
        payload: AnswerFeedbackRequest,
    ) -> AnswerFeedbackResponse:
        return await asyncio.to_thread(
            app.state.feedback_store.create, answer_id, payload
        )

    return app


app = create_app()
