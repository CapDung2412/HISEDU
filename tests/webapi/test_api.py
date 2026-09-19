from __future__ import annotations

import unittest
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from hisedu.webapi.app import create_app
from hisedu.webapi.errors import AiServiceError, AiTimeoutError
from hisedu.webapi.settings import WebSettings

from .helpers import FakeAI, FakeRetrieval, YOUTUBE_URL, generated_lesson


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
    def make_client(self, retrieval=None, ai=None, **setting_changes) -> TestClient:
        self.retrieval = retrieval or FakeRetrieval()
        self.ai = ai or FakeAI()
        app = create_app(
            retrieval_service=self.retrieval,
            ai_service=self.ai,
            settings=settings(**setting_changes),
        )
        return TestClient(app, raise_server_exceptions=False)

    def test_health_is_local_and_does_not_call_services(self) -> None:
        client = self.make_client()
        response = client.get("/api/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])
        self.assertEqual(0, self.retrieval.text_calls)
        self.assertEqual(0, self.ai.calls)

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
        self.assertIsNone(body["sources"][0]["page"])
        self.assertIn("chưa ghi nhận số trang", " ".join(body["limitations"]))
        self.assertEqual(YOUTUBE_URL, body["videos"][0]["url"])
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

    def test_no_retrieval_result_returns_standard_404_without_ai_call(self) -> None:
        client = self.make_client(retrieval=FakeRetrieval(matches=[]))
        response = client.post(
            "/api/questions/ask", json={"question": "Một câu hỏi không có dữ liệu"}
        )
        self.assertEqual(404, response.status_code)
        self.assertEqual("KNOWLEDGE_NOT_FOUND", response.json()["error"]["code"])
        self.assertEqual(0, self.ai.calls)

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
        response = client.post(
            "/api/questions/ask-image",
            files={"file": ("photo.png", png_bytes(), "image/png")},
            data={"mode": "clip", "top_k": "3"},
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(1, self.retrieval.image_calls)

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


if __name__ == "__main__":
    unittest.main()
