from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Annotated, Literal

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


@dataclass(slots=True)
class CachedLesson:
    lesson: object
    sources: list[Source]
    videos: list[Video]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex)


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
        "schema_version": "hisedu-web-response-v1",
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
    app.state.retrieval = retrieval_service or HISEduRetrievalService()
    app.state.ai = ai_service or OpenAIResponsesAdapter(config)
    app.state.response_cache = response_cache or TTLCache(
        ttl_seconds=config.cache_ttl_seconds, max_items=256
    )
    app.state.quiz_store = quiz_store or QuizStore(ttl_seconds=config.quiz_ttl_seconds)
    # Single-flight generation avoids duplicate billable OpenAI calls when
    # several students submit the same uncached question simultaneously.
    app.state.generation_lock = asyncio.Lock()
    app.state.rate_limiter = InMemoryRateLimiter(
        max_requests=config.rate_limit_requests,
        window_seconds=config.rate_limit_window_seconds,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        inbound = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            inbound
            if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", inbound)
            else uuid.uuid4().hex
        )
        response = await call_next(request)
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
        )
        cached = app.state.response_cache.get(key)
        if cached is None:
            async with app.state.generation_lock:
                cached = app.state.response_cache.get(key)
                if cached is None:
                    try:
                        generated = await app.state.ai.generate(
                            result.query, result.matches
                        )
                    except WebApiError:
                        raise
                    except Exception as exc:
                        raise AiServiceError() from exc
                    if isinstance(generated, GenerationResult):
                        raw_lesson = generated.lesson
                        returned_urls = generated.web_urls
                    else:
                        raw_lesson = generated
                        returned_urls = set()
                    cleaned, sources, videos = sanitize_lesson(
                        raw_lesson,
                        result.matches,
                        returned_web_urls=returned_urls,
                    )
                    cached = CachedLesson(
                        lesson=cleaned, sources=sources, videos=videos
                    )
                    app.state.response_cache.set(key, cached)
        lesson = cached.lesson
        quiz = app.state.quiz_store.create(lesson.quiz)
        limitations = list(lesson.limitations)
        if any(source.type == "sgk" and source.page is None for source in cached.sources):
            limitations.append("Dữ liệu hiện tại chưa ghi nhận số trang SGK.")
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
            }
        )

    @app.post(
        "/api/questions/ask",
        response_model=AskResponse,
        responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
        dependencies=[Depends(enforce_rate_limit)],
    )
    async def ask(payload: QuestionRequest, request: Request) -> AskResponse:
        try:
            result = await app.state.retrieval.search_text(
                normalize_text(payload.question), top_k=payload.top_k
            )
        except WebApiError:
            raise
        except Exception as exc:
            raise RetrievalServiceError() from exc
        return await build_response(result, request)

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
            raise RetrievalServiceError() from exc
        return await build_response(result, request)

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
