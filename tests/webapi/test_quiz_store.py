from __future__ import annotations

import unittest

from hisedu.webapi.quiz_store import QuizStore
from hisedu.webapi.schemas import GeneratedQuizQuestion


def question(identifier: str, difficulty: str) -> GeneratedQuizQuestion:
    return GeneratedQuizQuestion.model_validate(
        {
            "id": identifier,
            "prompt": f"Câu hỏi {identifier}?",
            "difficulty": difficulty,
            "options": [
                {"id": f"{identifier}_{letter}", "text": f"Phương án {letter}"}
                for letter in "abcd"
            ],
            "correct_option_id": f"{identifier}_a",
            "explanation": "Đáp án được xác nhận từ nguồn S1.",
            "source_ids": ["S1"],
        }
    )


class AdaptiveQuizStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = QuizStore()
        self.questions = [
            question("remember-1", "remember"),
            question("remember-2", "remember"),
            question("understand-1", "understand"),
            question("understand-2", "understand"),
            question("apply-1", "apply"),
        ]

    def test_correct_answer_moves_to_a_harder_question(self) -> None:
        quiz = self.store.create(self.questions)
        response = self.store.answer_one(
            quiz.quiz_id,
            question_id="remember-1",
            option_id="remember-1_a",
        )

        self.assertTrue(response.result.correct)
        self.assertEqual("understand", response.next_question.difficulty)
        self.assertIn("nâng độ khó", response.adaptive_message)

    def test_wrong_answer_keeps_a_foundational_question(self) -> None:
        quiz = self.store.create(self.questions)
        response = self.store.answer_one(
            quiz.quiz_id,
            question_id="remember-1",
            option_id="remember-1_b",
        )

        self.assertFalse(response.result.correct)
        self.assertEqual("remember-2", response.next_question.id)
        self.assertIn("củng cố kiến thức nền", response.adaptive_message)

    def test_reset_starts_a_fresh_attempt(self) -> None:
        quiz = self.store.create(self.questions)
        self.store.answer_one(
            quiz.quiz_id,
            question_id="remember-1",
            option_id="remember-1_a",
        )

        reset = self.store.reset(quiz.quiz_id)
        response = self.store.answer_one(
            reset.quiz_id,
            question_id=reset.questions[0].id,
            option_id=f"{reset.questions[0].id}_a",
        )

        self.assertEqual(1, response.answered_count)
        self.assertEqual(1, response.score_so_far)


if __name__ == "__main__":
    unittest.main()
