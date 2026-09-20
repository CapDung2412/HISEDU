from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from threading import Lock

from .errors import InvalidQuizSubmissionError, QuizNotFoundError
from .schemas import (
    GeneratedQuizQuestion,
    Quiz,
    QuizQuestion,
    QuizResult,
    QuizSubmitResponse,
)


@dataclass(slots=True)
class _StoredQuiz:
    expires_at: float
    questions: list[GeneratedQuizQuestion]


class QuizStore:
    def __init__(self, *, ttl_seconds: int = 1_800, max_items: int = 1_000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: dict[str, _StoredQuiz] = {}
        self._lock = Lock()

    def create(self, questions: list[GeneratedQuizQuestion]) -> Quiz:
        if not questions:
            return Quiz(quiz_id="quiz-unavailable", questions=[])
        if len(questions) != 5:
            raise ValueError("a lesson quiz must contain exactly five questions")
        quiz_id = uuid.uuid4().hex
        with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_items:
                oldest = min(self._items, key=lambda key: self._items[key].expires_at)
                del self._items[oldest]
            self._items[quiz_id] = _StoredQuiz(
                expires_at=time.monotonic() + self.ttl_seconds,
                questions=[question.model_copy(deep=True) for question in questions],
            )
        return Quiz(
            quiz_id=quiz_id,
            questions=[
                QuizQuestion(id=item.id, prompt=item.prompt, options=item.options)
                for item in questions
            ],
        )

    def submit(self, quiz_id: str, answers: dict[str, str]) -> QuizSubmitResponse:
        with self._lock:
            self._purge_locked()
            stored = self._items.get(quiz_id)
            if stored is None:
                raise QuizNotFoundError()
            questions = [item.model_copy(deep=True) for item in stored.questions]
        expected_ids = {question.id for question in questions}
        if set(answers) != expected_ids:
            raise InvalidQuizSubmissionError()
        results: list[QuizResult] = []
        for question in questions:
            option_ids = {option.id for option in question.options}
            selected = answers.get(question.id)
            if selected not in option_ids:
                raise InvalidQuizSubmissionError()
            results.append(
                QuizResult(
                    question_id=question.id,
                    selected_option_id=selected,
                    correct=selected == question.correct_option_id,
                    correct_option_id=question.correct_option_id,
                    explanation=question.explanation,
                    source_ids=question.source_ids,
                )
            )
        return QuizSubmitResponse(
            quiz_id=quiz_id,
            score=sum(result.correct for result in results),
            results=results,
        )

    def _purge_locked(self) -> None:
        now = time.monotonic()
        for quiz_id in [key for key, value in self._items.items() if value.expires_at <= now]:
            del self._items[quiz_id]
