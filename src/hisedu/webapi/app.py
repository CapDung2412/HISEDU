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
from typing import Annotated, AsyncIterator, Literal

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hisedu.dataset import normalize_text

from .cache import TTLCache
from .errors import (
    AiServiceError,
    ImageTooLargeError,
    KnowledgeNotFoundError,
    RequestTimeoutError,
    RetrievalServiceError,
    WebApiError,
)
from .openai_adapter import OpenAIResponsesAdapter
from .quiz_store import QuizStore
from .rate_limit import InMemoryRateLimiter
from .schemas import (
    AskResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    QuestionRequest,
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
    quiz_store: QuizStore | None = None,
    video_recommender: VideoRecommendationService | None = None,
) -> FastAPI:
    config = settings or WebSettings.from_env()
    app = FastAPI(
        title="HISEDU API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.state.settings = config
    app.state.retrieval = retrieval_service or HISEduRetrievalService(
        timeout_seconds=config.retrieval_timeout_seconds,
        pinecone_timeout_seconds=config.pinecone_timeout_seconds,
    )
    app.state.ai = ai_service or OpenAIResponsesAdapter(config)
    app.state.response_cache = response_cache or TTLCache(
        ttl_seconds=config.cache_ttl_seconds, max_items=256
    )
    app.state.quiz_store = quiz_store or QuizStore(ttl_seconds=config.quiz_ttl_seconds)
    app.state.video_recommender = video_recommender or YouTubeVideoRecommender(
        config.youtube_api_key,
        timeout_seconds=config.youtube_timeout_seconds,
        cache_ttl_seconds=config.youtube_cache_ttl_seconds,
    )
    # Duplicate questions share a lock, while different questions can be
    # generated concurrently instead of queueing behind one global lock.
    app.state.generation_locks = _KeyedLockPool()
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

    async def build_response(result: RetrievalResult, request: Request) -> AskResponse:
        if not result.matches:
            raise KnowledgeNotFoundError()
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
        if cached is None:
            lock_started = time.perf_counter()
            async with app.state.generation_locks.hold(key):
                _record_timing(request, "generation_lock", lock_started)
                cached = app.state.response_cache.get(key)
                if cached is None:
                    ai_started = time.perf_counter()
                    try:
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
                    # Only the allowlisted YouTube provider may populate videos.
                    # Never retain model-generated URLs or the retired local catalog.
                    videos: list[Video] = []
                    cleaned = cleaned.model_copy(update={"videos": videos})
                    youtube_video_started = time.perf_counter()
                    try:
                        answer_text = " ".join(
                            [
                                cleaned.answer.summary,
                                *cleaned.answer.key_points,
                                *(
                                    section.content
                                    for section in cleaned.answer.sections
                                ),
                                *(
                                    str((match.get("fields") or {}).get("answer") or "")
                                    for match in result.matches
                                ),
                            ]
                        )
                        topics = [
                            cleaned.mindmap.title,
                            *(node.label for node in cleaned.mindmap.nodes),
                            *(
                                str((match.get("fields") or {}).get(field) or "")
                                for match in result.matches
                                for field in (
                                    "chapter_title",
                                    "lesson_title",
                                    "source_locator",
                                )
                            ),
                        ]
                        videos = await app.state.video_recommender.recommend(
                            question=result.query,
                            answer=answer_text,
                            topics=topics,
                            limit=6,
                        )
                        cleaned = cleaned.model_copy(update={"videos": videos})
                    except Exception as exc:
                        # Video enrichment is optional and must fail closed. Do
                        # not log exception text because an HTTP URL may contain
                        # the YouTube API key.
                        logger.warning(
                            "hisedu_youtube_error request_id=%s error_type=%s",
                            _request_id(request),
                            type(exc).__name__,
                        )
                    finally:
                        _record_timing(
                            request, "youtube_video", youtube_video_started
                        )
                    cached = CachedLesson(
                        lesson=cleaned, sources=sources, videos=videos
                    )
                    app.state.response_cache.set(key, cached)
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
        return AskResponse(
            request_id=_request_id(request),
            question=result.query,
            answer=lesson.answer,
            mindmap=lesson.mindmap,
            videos=cached.videos,
            sources=cached.sources,
            quiz=quiz,
            retrieval=RetrievalInfo(
                matched_ids=[str(match.get("id", "")) for match in result.matches],
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
        "/api/questions/ask",
        response_model=AskResponse,
        responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def ask(payload: QuestionRequest, request: Request) -> AskResponse:
        async def process() -> AskResponse:
            retrieval_started = time.perf_counter()
            try:
                result = await app.state.retrieval.search_text(
                    normalize_text(payload.question), top_k=payload.top_k
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
        top_k: Annotated[int, Form(ge=1, le=10)] = 5,
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
        async def process() -> AskResponse:
            retrieval_started = time.perf_counter()
            try:
                result = await app.state.retrieval.search_image(
                    data,
                    filename=file.filename or "upload.img",
                    content_type=claimed_mime,
                    top_k=top_k,
                    mode=mode,
                    question=normalized_question,
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
        "/api/quizzes/{quiz_id}/submit",
        response_model=QuizSubmitResponse,
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def submit_quiz(
        quiz_id: str, payload: QuizSubmitRequest
    ) -> QuizSubmitResponse:
        return app.state.quiz_store.submit(quiz_id, payload.answers)

    return app


app = create_app()
