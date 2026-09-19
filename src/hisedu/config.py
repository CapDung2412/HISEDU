from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


def load_project_env() -> None:
    """Load the project .env without overwriting process-level variables."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


def _optional_score(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if not -1.0 <= value <= 1.0:
        raise ConfigurationError(f"{name} must be between -1 and 1")
    return value


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    text_model: str = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
    image_model: str = "sentence-transformers/clip-ViT-B-32"
    device: str | None = None
    embedding_batch_size: int = 32
    upsert_batch_size: int = 50
    pinecone_api_key: str | None = None
    pinecone_index_name: str = "hisedu-clip-v1"
    pinecone_namespace: str = "history8-v1-0-0"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    min_score: float | None = None
    ocr_language: str = "vi"
    ocr_min_line_score: float = 0.50

    @property
    def questions_dir(self) -> Path:
        return self.project_root / "questions"

    @property
    def answers_dir(self) -> Path:
        return self.project_root / "answers"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "reports"

    @classmethod
    def from_env(cls, *, require_pinecone: bool = False) -> "Settings":
        load_project_env()
        key = os.getenv("PINECONE_API_KEY", "").strip() or None
        if require_pinecone and not key:
            raise ConfigurationError(
                "PINECONE_API_KEY is required for Pinecone ingest/query; add it to .env"
            )
        index_name = os.getenv("PINECONE_INDEX_NAME", "hisedu-clip-v1").strip()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,43}[a-z0-9])?", index_name):
            raise ConfigurationError(
                "PINECONE_INDEX_NAME must be 1-45 lowercase letters, digits, or hyphens"
            )
        namespace = os.getenv("PINECONE_NAMESPACE", "history8-v1-0-0").strip()
        if not namespace:
            raise ConfigurationError("PINECONE_NAMESPACE must not be empty")
        device = os.getenv("HISEDU_DEVICE", "").strip() or None
        configured_root = os.getenv("HISEDU_PROJECT_ROOT", "").strip()
        project_root = (
            Path(configured_root).expanduser().resolve()
            if configured_root
            else PROJECT_ROOT
        )
        return cls(
            project_root=project_root,
            text_model=os.getenv(
                "HISEDU_TEXT_MODEL",
                "sentence-transformers/clip-ViT-B-32-multilingual-v1",
            ).strip(),
            image_model=os.getenv(
                "HISEDU_IMAGE_MODEL", "sentence-transformers/clip-ViT-B-32"
            ).strip(),
            device=device,
            embedding_batch_size=_positive_int("HISEDU_EMBED_BATCH_SIZE", 32),
            upsert_batch_size=_positive_int("HISEDU_UPSERT_BATCH_SIZE", 50),
            pinecone_api_key=key,
            pinecone_index_name=index_name,
            pinecone_namespace=namespace,
            pinecone_cloud=os.getenv("PINECONE_CLOUD", "aws").strip(),
            pinecone_region=os.getenv("PINECONE_REGION", "us-east-1").strip(),
            min_score=_optional_score("HISEDU_MIN_SCORE"),
            ocr_language=os.getenv("HISEDU_OCR_LANGUAGE", "vi").strip(),
            ocr_min_line_score=_bounded_float(
                "HISEDU_OCR_MIN_LINE_SCORE", 0.50, 0.0, 1.0
            ),
        )
