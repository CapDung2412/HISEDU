from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from .errors import AnswerFeedbackNotFoundError
from .schemas import (
    AnswerContent,
    AnswerFeedbackRequest,
    AnswerFeedbackResponse,
    Source,
)


@dataclass(slots=True)
class _FeedbackContext:
    expires_at: float
    request_id: str
    question: str
    answer: dict
    sources: list[dict]
    matched_ids: list[str]
    feedback_id: str | None = None


class FeedbackStore:
    """Keep server-authored answer context and append bounded review records."""

    def __init__(
        self,
        path: Path | str,
        *,
        context_ttl_seconds: int = 3_600,
        max_contexts: int = 1_000,
        max_file_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self.path = Path(path)
        self.context_ttl_seconds = context_ttl_seconds
        self.max_contexts = max_contexts
        self.max_file_bytes = max_file_bytes
        self._contexts: dict[str, _FeedbackContext] = {}
        self._lock = Lock()

    def register(
        self,
        *,
        request_id: str,
        question: str,
        answer: AnswerContent,
        sources: list[Source],
        matched_ids: list[str],
    ) -> str:
        """Return an opaque server-owned id; persist context only after a report."""
        answer_id = uuid.uuid4().hex
        context = _FeedbackContext(
            expires_at=time.monotonic() + self.context_ttl_seconds,
            request_id=request_id,
            question=question,
            answer=answer.model_dump(mode="json"),
            sources=[source.model_dump(mode="json") for source in sources],
            matched_ids=list(matched_ids),
        )
        with self._lock:
            self._purge_locked()
            if len(self._contexts) >= self.max_contexts:
                oldest = min(
                    self._contexts,
                    key=lambda key: self._contexts[key].expires_at,
                )
                del self._contexts[oldest]
            self._contexts[answer_id] = context
        return answer_id

    def create(
        self, answer_id: str, payload: AnswerFeedbackRequest
    ) -> AnswerFeedbackResponse:
        comment = (payload.comment or "").strip() or None
        with self._lock:
            self._purge_locked()
            context = self._contexts.get(answer_id)
            if context is None:
                raise AnswerFeedbackNotFoundError()
            if context.feedback_id is not None:
                return AnswerFeedbackResponse(feedback_id=context.feedback_id)

            feedback_id = uuid.uuid4().hex
            response = AnswerFeedbackResponse(feedback_id=feedback_id)
            record = {
                "feedback_id": feedback_id,
                "answer_id": answer_id,
                "request_id": context.request_id,
                "question": context.question,
                "answer": context.answer,
                "sources": context.sources,
                "matched_ids": context.matched_ids,
                "rating": payload.rating,
                "comment": comment,
                "status": response.status,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            serialized = json.dumps(
                record, ensure_ascii=False, separators=(",", ":")
            ) + "\n"
            self._append_locked(serialized)
            context.feedback_id = feedback_id
            return response

    def _append_locked(self, serialized: str) -> None:
        encoded_size = len(serialized.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size + encoded_size > self.max_file_bytes:
            backup = self.path.with_name(f"{self.path.name}.1")
            if backup.exists():
                backup.unlink()
            self.path.replace(backup)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            # Windows ACLs and some network filesystems need deployment policy.
            pass

    def _purge_locked(self) -> None:
        now = time.monotonic()
        for answer_id in [
            key for key, value in self._contexts.items() if value.expires_at <= now
        ]:
            del self._contexts[answer_id]
