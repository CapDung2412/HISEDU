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
    openai_model: str = "gpt-4.1-mini"
    enable_web_search: bool = False
    openai_timeout_seconds: int = 45
    max_image_bytes: int = 5 * 1024 * 1024
    max_image_pixels: int = 20_000_000
    cache_ttl_seconds: int = 900
    quiz_ttl_seconds: int = 1_800
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    prompt_version: str = "hisedu-web-v1"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)

    @classmethod
    def from_env(cls) -> "WebSettings":
        load_project_env()
        origins = tuple(
            value.strip()
            for value in os.getenv("HISEDU_CORS_ORIGINS", "http://localhost:3000").split(",")
            if value.strip()
        )
        return cls(
            chatgpt_api_key=os.getenv("CHATGPT_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            enable_web_search=_boolean("HISEDU_ENABLE_WEB_SEARCH", False),
            openai_timeout_seconds=_positive_int("HISEDU_OPENAI_TIMEOUT_SECONDS", 45),
            max_image_bytes=_positive_int("HISEDU_MAX_IMAGE_BYTES", 5 * 1024 * 1024),
            max_image_pixels=_positive_int("HISEDU_MAX_IMAGE_PIXELS", 20_000_000),
            cache_ttl_seconds=_positive_int("HISEDU_CACHE_TTL_SECONDS", 900),
            quiz_ttl_seconds=_positive_int("HISEDU_QUIZ_TTL_SECONDS", 1_800),
            rate_limit_requests=_positive_int("HISEDU_RATE_LIMIT_REQUESTS", 20),
            rate_limit_window_seconds=_positive_int("HISEDU_RATE_LIMIT_WINDOW_SECONDS", 60),
            prompt_version=os.getenv("HISEDU_PROMPT_VERSION", "hisedu-web-v1").strip(),
            cors_origins=origins,
        )
