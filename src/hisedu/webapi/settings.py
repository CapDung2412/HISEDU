from __future__ import annotations

import os
from dataclasses import dataclass, field

from hisedu.config import load_project_env


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class WebSettings:
    chatgpt_api_key: str | None = field(default=None, repr=False)
    youtube_api_key: str | None = field(default=None, repr=False)
    openai_model: str = "gpt-4.1-mini"
    enable_web_search: bool = False
    openai_timeout_seconds: int = 30
    openai_quiz_grace_seconds: float = 2.0
    openai_core_max_output_tokens: int = 2_200
    openai_quiz_max_output_tokens: int = 1_200
    openai_core_max_matches: int = 3
    retrieval_timeout_seconds: int = 45
    request_timeout_seconds: int = 70
    pinecone_timeout_seconds: int = 8
    youtube_timeout_seconds: float = 5.0
    youtube_cache_ttl_seconds: int = 86_400
    max_image_bytes: int = 5 * 1024 * 1024
    max_image_pixels: int = 20_000_000
    cache_ttl_seconds: int = 3_600
    quiz_ttl_seconds: int = 1_800
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    feedback_path: str = "feedback/answer-feedback.jsonl"
    feedback_context_ttl_seconds: int = 3_600
    feedback_max_bytes: int = 5 * 1024 * 1024
    prompt_version: str = "hisedu-web-v8-latency-budget"
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    @classmethod
    def from_env(cls) -> "WebSettings":
        load_project_env()
        origins = tuple(
            value.strip()
            for value in os.getenv(
                "HISEDU_CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if value.strip()
        )
        return cls(
            chatgpt_api_key=os.getenv("CHATGPT_API_KEY", "").strip() or None,
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            enable_web_search=_boolean("HISEDU_ENABLE_WEB_SEARCH", False),
            openai_timeout_seconds=_positive_int("HISEDU_OPENAI_TIMEOUT_SECONDS", 30),
            openai_quiz_grace_seconds=_positive_float(
                "HISEDU_OPENAI_QUIZ_GRACE_SECONDS", 2.0
            ),
            openai_core_max_output_tokens=_positive_int(
                "HISEDU_OPENAI_CORE_MAX_OUTPUT_TOKENS", 2_200
            ),
            openai_quiz_max_output_tokens=_positive_int(
                "HISEDU_OPENAI_QUIZ_MAX_OUTPUT_TOKENS", 1_200
            ),
            openai_core_max_matches=_positive_int(
                "HISEDU_OPENAI_CORE_MAX_MATCHES", 3
            ),
            retrieval_timeout_seconds=_positive_int(
                "HISEDU_RETRIEVAL_TIMEOUT_SECONDS", 45
            ),
            request_timeout_seconds=_positive_int(
                "HISEDU_REQUEST_TIMEOUT_SECONDS", 70
            ),
            pinecone_timeout_seconds=_positive_int(
                "HISEDU_PINECONE_TIMEOUT_SECONDS", 8
            ),
            youtube_timeout_seconds=_positive_float(
                "HISEDU_YOUTUBE_TIMEOUT_SECONDS", 5.0
            ),
            youtube_cache_ttl_seconds=_positive_int(
                "HISEDU_YOUTUBE_CACHE_TTL_SECONDS", 86_400
            ),
            max_image_bytes=_positive_int("HISEDU_MAX_IMAGE_BYTES", 5 * 1024 * 1024),
            max_image_pixels=_positive_int("HISEDU_MAX_IMAGE_PIXELS", 20_000_000),
            cache_ttl_seconds=_positive_int("HISEDU_CACHE_TTL_SECONDS", 3_600),
            quiz_ttl_seconds=_positive_int("HISEDU_QUIZ_TTL_SECONDS", 1_800),
            rate_limit_requests=_positive_int("HISEDU_RATE_LIMIT_REQUESTS", 20),
            rate_limit_window_seconds=_positive_int("HISEDU_RATE_LIMIT_WINDOW_SECONDS", 60),
            feedback_path=os.getenv(
                "HISEDU_FEEDBACK_PATH", "feedback/answer-feedback.jsonl"
            ).strip()
            or "feedback/answer-feedback.jsonl",
            feedback_context_ttl_seconds=_positive_int(
                "HISEDU_FEEDBACK_CONTEXT_TTL_SECONDS", 3_600
            ),
            feedback_max_bytes=_positive_int(
                "HISEDU_FEEDBACK_MAX_BYTES", 5 * 1024 * 1024
            ),
            prompt_version=os.getenv(
                "HISEDU_PROMPT_VERSION", "hisedu-web-v8-latency-budget"
            ).strip(),
            cors_origins=origins,
        )
