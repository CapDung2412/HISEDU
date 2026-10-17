from __future__ import annotations

import asyncio
import json
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from PIL import Image

from hisedu.webapi.app import _KeyedLockPool, create_app
from hisedu.webapi.errors import AiServiceError, AiTimeoutError
from hisedu.webapi.feedback_store import FeedbackStore
from hisedu.webapi.settings import WebSettings

from .helpers import FakeAI, FakeRetrieval, generated_lesson


def settings(**changes) -> WebSettings:
    values = {
        "chatgpt_api_key": None,
        "enable_web_search": False,
        "rate_limit_requests": 100,
        "max_image_bytes": 1024 * 1024,
    }
    values.update(changes)
    return WebSettings(**values)


def png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, format="PNG")
    return stream.getvalue()


class WebApiTests(unittest.TestCase):
    def make_client(
        self, retrieval=None, ai=None, feedback_store=None, **setting_changes
    ) -> TestClient:
        self.retrieval = retrieval or FakeRetrieval()
        self.ai = ai or FakeAI()
        app = create_app(
            retrieval_service=self.retrieval,
            ai_service=self.ai,
            settings=settings(**setting_changes),
            feedback_store=feedback_store,
        )
        return TestClient(app, raise_server_exceptions=False)

    def test_health_is_local_and_does_not_call_services(self) -> None:
        client = self.make_client()
        response = client.get("/api/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])
        self.assertEqual(0, self.retrieval.text_calls)
        self.assertEqual(0, self.ai.calls)

    def test_response_exposes_stage_timings_without_question_content(self) -> None:
        client = self.make_client()
        response = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        )

        self.assertEqual(200, response.status_code, response.text)
        timing = response.headers["server-timing"]
        self.assertIn("retrieval;dur=", timing)
        self.assertIn("openai;dur=", timing)
        self.assertIn("total;dur=", timing)
        self.assertNotIn("Cách mạng", timing)

    def test_total_deadline_returns_json_before_frontend_abort(self) -> None:
        class SlowRetrieval(FakeRetrieval):
            async def search_text(self, question: str, *, top_k: int):
                await asyncio.sleep(0.05)
                return await super().search_text(question, top_k=top_k)

        client = self.make_client(
            retrieval=SlowRetrieval(), request_timeout_seconds=0.01
        )
        response = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        )

        self.assertEqual(504, response.status_code, response.text)
        self.assertEqual("REQUEST_TIMEOUT", response.json()["error"]["code"])

    def test_ask_hides_answers_strips_fake_page_and_uses_cache_template(self) -> None:
        client = self.make_client()
        payload = {"question": "Cách mạng tư sản Anh bùng nổ năm nào?"}
        first = client.post("/api/questions/ask", json=payload)
        second = client.post("/api/questions/ask", json=payload)
        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(200, second.status_code, second.text)
        body = first.json()
        self.assertNotIn("correct_option_id", first.text)
        self.assertEqual(5, len(body["quiz"]["questions"]))
        self.assertEqual("dataset", body["sources"][0]["type"])
        self.assertIsNone(body["sources"][0]["page"])
        self.assertEqual("unverified", body["sources"][0]["page_status"])
        self.assertEqual("Năm 1642.", body["sources"][0]["evidence_excerpt"])
        self.assertRegex(body["answer_id"], r"^[a-f0-9]{32}$")
        self.assertEqual(
            "Chờ giáo viên duyệt", body["sources"][0]["review_status"]
        )
        self.assertIn(
            "không phải trích dẫn nguyên văn",
            body["sources"][0]["provenance_note"],
        )
        self.assertIn("chưa ghi nhận số trang", " ".join(body["limitations"]))
        # Model-produced video URLs are ignored; without a YouTube API key the
        # allowlisted provider fails closed and returns no videos.
        self.assertEqual([], body["videos"])
        self.assertEqual(1, self.retrieval.text_calls)
        self.assertEqual(1, self.ai.calls)
        self.assertNotEqual(body["quiz"]["quiz_id"], second.json()["quiz"]["quiz_id"])

    def test_quiz_submit_scores_and_reveals_answers_only_after_submit(self) -> None:
        client = self.make_client()
        lesson = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        ).json()
        quiz = lesson["quiz"]
        answers = {
            question["id"]: question["options"][0 if index == 0 else 1]["id"]
            for index, question in enumerate(quiz["questions"])
        }
        response = client.post(
            f"/api/quizzes/{quiz['quiz_id']}/submit", json={"answers": answers}
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(1, response.json()["score"])
        self.assertEqual(5, response.json()["max_score"])
        self.assertTrue(all("correct_option_id" in item for item in response.json()["results"]))

    def test_adaptive_quiz_checks_one_answer_and_selects_next_level(self) -> None:
        client = self.make_client()
        quiz = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        ).json()["quiz"]
        first = quiz["questions"][0]

        response = client.post(
            f"/api/quizzes/{quiz['quiz_id']}/answer",
            json={
                "question_id": first["id"],
                "option_id": first["options"][0]["id"],
            },
        )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertTrue(body["result"]["correct"])
        self.assertEqual("understand", body["next_question"]["difficulty"])
        self.assertEqual(1, body["score_so_far"])
        self.assertNotIn("correct_option_id", json.dumps(body["next_question"]))

        reset = client.post(f"/api/quizzes/{quiz['quiz_id']}/reset")
        self.assertEqual(200, reset.status_code, reset.text)
        self.assertEqual(first["id"], reset.json()["questions"][0]["id"])

    def test_slow_optional_quiz_can_return_a_usable_partial_lesson(self) -> None:
        lesson = generated_lesson().model_copy(update={"quiz": []})
        client = self.make_client(ai=FakeAI(lesson))

        response = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertTrue(body["answer"]["summary"])
        self.assertEqual("quiz-unavailable", body["quiz"]["quiz_id"])
        self.assertEqual([], body["quiz"]["questions"])

    def test_no_retrieval_result_returns_standard_404_without_ai_call(self) -> None:
        client = self.make_client(retrieval=FakeRetrieval(matches=[]))
        response = client.post(
            "/api/questions/ask", json={"question": "Một câu hỏi không có dữ liệu"}
        )
        self.assertEqual(404, response.status_code)
        self.assertEqual("KNOWLEDGE_NOT_FOUND", response.json()["error"]["code"])
        self.assertEqual(0, self.ai.calls)

    def test_calibrated_low_confidence_stops_before_ai_call(self) -> None:
        matches = FakeRetrieval().matches
        matches[0]["confidence_status"] = "below_threshold"
        client = self.make_client(retrieval=FakeRetrieval(matches=matches))

        response = client.post(
            "/api/questions/ask", json={"question": "Một câu hỏi ngoài dữ liệu"}
        )

        self.assertEqual(404, response.status_code, response.text)
        self.assertEqual("KNOWLEDGE_NOT_FOUND", response.json()["error"]["code"])
        self.assertEqual(0, self.ai.calls)

    def test_answer_feedback_is_validated_and_persisted_for_teacher_review(self) -> None:
        with TemporaryDirectory() as temp_dir:
            feedback_path = Path(temp_dir) / "nested" / "feedback.jsonl"
            client = self.make_client(
                feedback_store=FeedbackStore(feedback_path)
            )

            lesson = client.post(
                "/api/questions/ask",
                json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
            ).json()
            answer_id = lesson["answer_id"]

            response = client.post(
                f"/api/answers/{answer_id}/feedback",
                json={"rating": "not_helpful", "comment": "  Sai mốc thời gian.  "},
            )

            self.assertEqual(201, response.status_code, response.text)
            self.assertEqual("pending_teacher_review", response.json()["status"])
            record = json.loads(feedback_path.read_text(encoding="utf-8"))
            self.assertEqual(response.json()["feedback_id"], record["feedback_id"])
            self.assertEqual(answer_id, record["answer_id"])
            self.assertEqual(lesson["question"], record["question"])
            self.assertEqual(lesson["answer"], record["answer"])
            self.assertEqual(lesson["sources"], record["sources"])
            self.assertEqual(lesson["retrieval"]["matched_ids"], record["matched_ids"])
            self.assertEqual("not_helpful", record["rating"])
            self.assertEqual("Sai mốc thời gian.", record["comment"])
            self.assertEqual("pending_teacher_review", record["status"])
            self.assertIn("created_at", record)

            injected_answer = client.post(
                f"/api/answers/{answer_id}/feedback",
                json={
                    "rating": "not_helpful",
                    "answer": "must not be accepted",
                },
            )
            oversized = client.post(
                f"/api/answers/{answer_id}/feedback",
                json={"rating": "not_helpful", "comment": "x" * 2_001},
            )
            self.assertEqual(422, injected_answer.status_code, injected_answer.text)
            self.assertEqual(422, oversized.status_code, oversized.text)
            persisted_lines = feedback_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(persisted_lines))

            duplicate = client.post(
                f"/api/answers/{answer_id}/feedback",
                json={"rating": "not_helpful", "comment": "Gửi lại."},
            )
            self.assertEqual(201, duplicate.status_code, duplicate.text)
            self.assertEqual(response.json(), duplicate.json())
            self.assertEqual(
                1, len(feedback_path.read_text(encoding="utf-8").splitlines())
            )

            orphan = client.post(
                f"/api/answers/{'0' * 32}/feedback",
                json={"rating": "not_helpful"},
            )
            self.assertEqual(404, orphan.status_code, orphan.text)
            self.assertEqual(
                "ANSWER_FEEDBACK_NOT_FOUND", orphan.json()["error"]["code"]
            )

    def test_ai_errors_have_safe_status_codes(self) -> None:
        for error, expected_status, expected_code in (
            (AiServiceError(), 502, "AI_SERVICE_ERROR"),
            (AiTimeoutError(), 504, "AI_TIMEOUT"),
        ):
            with self.subTest(expected_code):
                client = self.make_client(ai=FakeAI(error=error))
                response = client.post(
                    "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
                )
                self.assertEqual(expected_status, response.status_code)
                self.assertEqual(expected_code, response.json()["error"]["code"])

    def test_invalid_or_oversized_image_is_rejected_before_retrieval(self) -> None:
        client = self.make_client(max_image_bytes=100)
        wrong_mime = client.post(
            "/api/questions/ask-image",
            files={"file": ("photo.jpg", png_bytes(), "image/jpeg")},
        )
        self.assertEqual(415, wrong_mime.status_code, wrong_mime.text)
        too_large = client.post(
            "/api/questions/ask-image",
            files={"file": ("photo.png", b"x" * 101, "image/png")},
        )
        self.assertEqual(413, too_large.status_code)
        self.assertEqual(0, self.retrieval.image_calls)

    def test_valid_image_uses_injected_retrieval_without_real_services(self) -> None:
        client = self.make_client()
        payload = png_bytes()
        response = client.post(
            "/api/questions/ask-image",
            files={"file": ("photo.png", payload, "image/png")},
            data={"mode": "clip", "top_k": "3"},
        )
        repeated = client.post(
            "/api/questions/ask-image",
            files={"file": ("renamed.png", payload, "image/png")},
            data={"mode": "clip", "top_k": "3"},
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(200, repeated.status_code, repeated.text)
        self.assertEqual(1, self.retrieval.image_calls)
        self.assertEqual(1, self.ai.calls)
        self.assertNotEqual(
            response.json()["quiz"]["quiz_id"],
            repeated.json()["quiz"]["quiz_id"],
        )

    def test_ocr_preview_returns_editable_text_without_search_or_ai(self) -> None:
        client = self.make_client()

        response = client.post(
            "/api/questions/ocr",
            files={"file": ("question.png", png_bytes(), "image/png")},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(
            "Cách mạng tư sản Anh bùng nổ vào năm nào?",
            response.json()["text"],
        )
        self.assertEqual(2, response.json()["line_count"])
        self.assertEqual(0.91, response.json()["mean_score"])
        self.assertFalse(response.json()["needs_review"])
        self.assertIn("ocr;dur=", response.headers["server-timing"])
        self.assertEqual(1, self.retrieval.ocr_calls)
        self.assertEqual(0, self.retrieval.text_calls)
        self.assertEqual(0, self.retrieval.image_calls)
        self.assertEqual(0, self.ai.calls)

    def test_unreturned_or_untrusted_video_url_is_removed(self) -> None:
        lesson = generated_lesson()
        bad = lesson.model_dump()
        bad["videos"][0]["url"] = "https://example.com/fake-video"
        client = self.make_client(
            ai=FakeAI(generated_lesson().model_validate(bad), web_urls={"https://example.com/fake-video"})
        )
        response = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([], response.json()["videos"])

    def test_channel_or_broadcaster_homepage_is_not_presented_as_video(self) -> None:
        for url in ("https://www.youtube.com/@ezsu", "https://htv.com.vn/"):
            with self.subTest(url=url):
                bad = generated_lesson().model_dump()
                bad["videos"][0]["url"] = url
                client = self.make_client(
                    ai=FakeAI(
                        generated_lesson().model_validate(bad), web_urls={url}
                    )
                )
                response = client.post(
                    "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
                )
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual([], response.json()["videos"])

    def test_verified_textbook_page_is_shown_with_book_identity(self) -> None:
        retrieval = FakeRetrieval(
            matches=[
                {
                    "id": "chunk-1",
                    "score": 0.95,
                    "fields": {
                        "dataset_version": "1.0.0",
                        "question": "Cách mạng tư sản Anh bùng nổ năm nào?",
                        "answer": "Năm 1642.",
                        "lesson_title": "Bài 1",
                        "source_name": "SGK Lịch sử và Địa lí 8 - Kết nối tri thức với cuộc sống",
                        "source_locator": "Bài 1",
                        "source_page_number": 7,
                        "source_grade": 8,
                        "source_book_series": "Kết nối tri thức với cuộc sống",
                    },
                }
            ]
        )
        client = self.make_client(
            retrieval=retrieval, ai=FakeAI(generated_lesson(source_page=7))
        )

        response = client.post(
            "/api/questions/ask", json={"question": "Cách mạng Anh năm nào?"}
        )

        self.assertEqual(200, response.status_code, response.text)
        source = response.json()["sources"][0]
        self.assertEqual("sgk", source["type"])
        self.assertEqual(8, source["grade"])
        self.assertEqual("Kết nối tri thức với cuộc sống", source["book_series"])
        self.assertEqual(7, source["page"])
        self.assertEqual("verified", source["page_status"])


class KeyedLockPoolTests(unittest.IsolatedAsyncioTestCase):
    async def test_different_questions_do_not_wait_for_one_global_lock(self) -> None:
        pool = _KeyedLockPool()
        active = 0
        max_active = 0

        async def worker(key: str) -> None:
            nonlocal active, max_active
            async with pool.hold(key):
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.01)
                active -= 1

        await asyncio.gather(worker("question-a"), worker("question-b"))
        self.assertEqual(2, max_active)


class RetrievalSingleflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_duplicate_text_requests_share_one_retrieval(self) -> None:
        class SlowRetrieval(FakeRetrieval):
            async def search_text(self, question: str, *, top_k: int):
                await asyncio.sleep(0.03)
                return await super().search_text(question, top_k=top_k)

        retrieval = SlowRetrieval()
        ai = FakeAI()
        app = create_app(
            retrieval_service=retrieval,
            ai_service=ai,
            settings=settings(),
        )
        transport = ASGITransport(app=app)
        payload = {"question": "Cách mạng tư sản Anh bùng nổ năm nào?"}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first, second = await asyncio.gather(
                client.post("/api/questions/ask", json=payload),
                client.post("/api/questions/ask", json=payload),
            )

        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(200, second.status_code, second.text)
        self.assertEqual(1, retrieval.text_calls)
        self.assertEqual(1, ai.calls)
        self.assertNotEqual(
            first.json()["quiz"]["quiz_id"], second.json()["quiz"]["quiz_id"]
        )


if __name__ == "__main__":
    unittest.main()
