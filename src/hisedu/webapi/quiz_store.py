from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock

from .errors import InvalidQuizSubmissionError, QuizNotFoundError
from .schemas import (
    GeneratedQuizQuestion,
    Quiz,
    QuizAnswerResponse,
    QuizQuestion,
    QuizResult,
    QuizSubmitResponse,
)


@dataclass(slots=True)
class _StoredQuiz:
    expires_at: float
    questions: list[GeneratedQuizQuestion]
    answers: dict[str, str] = field(default_factory=dict)
    current_question_id: str | None = None


_DIFFICULTY_RANK = {"remember": 0, "understand": 1, "apply": 2}


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
        # Start with foundational recall and let each submitted answer steer
        # the next level. Sorting is stable, so equally difficult questions
        # keep the pedagogical order produced by the model.
        ordered_questions = sorted(
            questions, key=lambda item: _DIFFICULTY_RANK[item.difficulty]
        )
        quiz_id = uuid.uuid4().hex
        with self._lock:
            self._purge_locked()
            if len(self._items) >= self.max_items:
                oldest = min(self._items, key=lambda key: self._items[key].expires_at)
                del self._items[oldest]
            self._items[quiz_id] = _StoredQuiz(
                expires_at=time.monotonic() + self.ttl_seconds,
                questions=[question.model_copy(deep=True) for question in ordered_questions],
                current_question_id=ordered_questions[0].id,
            )
        return self._public_quiz(quiz_id, ordered_questions)

    def answer_one(
        self, quiz_id: str, *, question_id: str, option_id: str
    ) -> QuizAnswerResponse:
        with self._lock:
            self._purge_locked()
            stored = self._items.get(quiz_id)
            if stored is None:
                raise QuizNotFoundError()

            by_id = {question.id: question for question in stored.questions}
            question = by_id.get(question_id)
            if question is None or option_id not in {item.id for item in question.options}:
                raise InvalidQuizSubmissionError()

            previous_option = stored.answers.get(question_id)
            if previous_option is not None:
                if previous_option != option_id:
                    raise InvalidQuizSubmissionError()
            else:
                if stored.current_question_id != question_id:
                    raise InvalidQuizSubmissionError()
                stored.answers[question_id] = option_id
                remaining = [
                    item for item in stored.questions if item.id not in stored.answers
                ]
                stored.current_question_id = self._choose_next(question, option_id, remaining)

            correct = option_id == question.correct_option_id
            result = QuizResult(
                question_id=question.id,
                selected_option_id=option_id,
                correct=correct,
                correct_option_id=question.correct_option_id,
                explanation=question.explanation,
                source_ids=question.source_ids,
            )
            next_question = by_id.get(stored.current_question_id or "")
            score = sum(
                selected == by_id[item_id].correct_option_id
                for item_id, selected in stored.answers.items()
            )
            answered_count = len(stored.answers)

        return QuizAnswerResponse(
            quiz_id=quiz_id,
            result=result,
            next_question=self._public_question(next_question) if next_question else None,
            answered_count=answered_count,
            score_so_far=score,
            completed=next_question is None,
            adaptive_message=self._adaptive_message(
                question.difficulty,
                next_question.difficulty if next_question else None,
                correct=correct,
            ),
        )

    def reset(self, quiz_id: str) -> Quiz:
        with self._lock:
            self._purge_locked()
            stored = self._items.get(quiz_id)
            if stored is None:
                raise QuizNotFoundError()
            stored.answers.clear()
            stored.current_question_id = stored.questions[0].id
            stored.expires_at = time.monotonic() + self.ttl_seconds
            questions = [item.model_copy(deep=True) for item in stored.questions]
        return self._public_quiz(quiz_id, questions)

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

    @staticmethod
    def _public_question(question: GeneratedQuizQuestion) -> QuizQuestion:
        return QuizQuestion(
            id=question.id,
            prompt=question.prompt,
            options=question.options,
            difficulty=question.difficulty,
        )

    @classmethod
    def _public_quiz(
        cls, quiz_id: str, questions: list[GeneratedQuizQuestion]
    ) -> Quiz:
        return Quiz(
            quiz_id=quiz_id,
            questions=[cls._public_question(item) for item in questions],
        )

    @staticmethod
    def _choose_next(
        current: GeneratedQuizQuestion,
        selected_option_id: str,
        remaining: list[GeneratedQuizQuestion],
    ) -> str | None:
        if not remaining:
            return None
        current_rank = _DIFFICULTY_RANK[current.difficulty]
        correct = selected_option_id == current.correct_option_id
        desired_rank = min(2, current_rank + 1) if correct else max(0, current_rank - 1)
        ranked = sorted(
            enumerate(remaining),
            key=lambda pair: (
                abs(_DIFFICULTY_RANK[pair[1].difficulty] - desired_rank),
                -_DIFFICULTY_RANK[pair[1].difficulty]
                if correct
                else _DIFFICULTY_RANK[pair[1].difficulty],
                pair[0],
            ),
        )
        return ranked[0][1].id

    @staticmethod
    def _adaptive_message(
        current_difficulty: str,
        next_difficulty: str | None,
        *,
        correct: bool,
    ) -> str:
        if next_difficulty is None:
            return "Em đã hoàn thành 5 câu. Hãy xem lại giải thích để ghi nhớ lâu hơn."
        current_rank = _DIFFICULTY_RANK[current_difficulty]
        next_rank = _DIFFICULTY_RANK[next_difficulty]
        if correct and next_rank > current_rank:
            return "Chính xác! Câu tiếp theo sẽ nâng độ khó thêm một mức."
        if not correct and next_rank <= current_rank:
            return "Chưa đúng. Câu tiếp theo sẽ củng cố kiến thức nền trước."
        return "Hệ thống đã chọn câu tiếp theo phù hợp với kết quả vừa rồi."
