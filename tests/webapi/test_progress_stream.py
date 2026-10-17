from __future__ import annotations

import asyncio
import json
import unittest
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from hisedu.webapi.app import create_app
from hisedu.webapi.errors import KnowledgeNotFoundError
from hisedu.webapi.progress_stream import ProgressChannel, publish_progress
from hisedu.webapi.settings import WebSettings

from .helpers import FakeAI, FakeRetrieval


def _events(body: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def _png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, format="PNG")
    return stream.getvalue()


class ProgressStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_channel_emits_utf8_progress_then_result(self) -> None:
        channel = ProgressChannel()
        await channel.publish("retrieval", "Đang tìm sử liệu phù hợp…")
        await channel.publish_partial(
            {"request_id": "request-1", "answer": {"summary": "Năm 1642"}}
        )
        await channel.finish({"request_id": "request-1", "answer": "Năm 1642"})

        chunks = [chunk async for chunk in channel.events()]
        body = b"".join(chunks).decode("utf-8")
        data_lines = [
            json.loads(line.removeprefix("data: "))
            for line in body.splitlines()
            if line.startswith("data: ")
        ]

        self.assertEqual("progress", data_lines[0]["type"])
        self.assertEqual("retrieval", data_lines[0]["stage"])
        self.assertEqual("Đang tìm sử liệu phù hợp…", data_lines[0]["message"])
        self.assertEqual("partial_result", data_lines[1]["type"])
        self.assertEqual("Năm 1642", data_lines[1]["data"]["answer"]["summary"])
        self.assertEqual("result", data_lines[2]["type"])
        self.assertEqual("request-1", data_lines[2]["data"]["request_id"])

    async def test_publish_is_noop_for_regular_json_request(self) -> None:
        request = SimpleNamespace(state=SimpleNamespace())
        await asyncio.wait_for(
            publish_progress(request, "generation", "Đang biên soạn bài học…"),
            timeout=0.1,
        )

    async def test_domain_error_can_be_sent_as_terminal_event(self) -> None:
        channel = ProgressChannel()
        error = KnowledgeNotFoundError()
        await channel.fail(
            code=error.code,
            message=error.message,
            request_id="request-2",
            status=error.status_code,
        )

        body = b"".join([chunk async for chunk in channel.events()]).decode("utf-8")
        payload = json.loads(
            next(line for line in body.splitlines() if line.startswith("data: "))[6:]
        )

        self.assertEqual("error", payload["type"])
        self.assertEqual("KNOWLEDGE_NOT_FOUND", payload["error"]["code"])
        self.assertEqual(404, payload["error"]["status"])


class ProgressEndpointTests(unittest.TestCase):
    def make_client(self, *, retrieval: FakeRetrieval | None = None) -> TestClient:
        app = create_app(
            retrieval_service=retrieval or FakeRetrieval(),
            ai_service=FakeAI(),
            settings=WebSettings(
                chatgpt_api_key=None,
                enable_web_search=False,
                rate_limit_requests=100,
            ),
        )
        return TestClient(app, raise_server_exceptions=False)

    def test_text_stream_reports_real_stages_and_keeps_json_result(self) -> None:
        response = self.make_client().post(
            "/api/questions/ask-stream",
            json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = _events(response.text)
        stages = [event["stage"] for event in events if event["type"] == "progress"]
        self.assertEqual(
            ["received", "retrieval", "generation", "enrichment", "finalizing"],
            stages,
        )
        result = next(event["data"] for event in events if event["type"] == "result")
        partial = next(
            event["data"] for event in events if event["type"] == "partial_result"
        )
        partial_index = next(
            index for index, event in enumerate(events) if event["type"] == "partial_result"
        )
        result_index = next(
            index for index, event in enumerate(events) if event["type"] == "result"
        )
        self.assertLess(partial_index, result_index)
        self.assertEqual(result["request_id"], partial["request_id"])
        self.assertEqual(result["question"], partial["question"])
        self.assertEqual(result["answer"], partial["answer"])
        self.assertEqual(result["mindmap"], partial["mindmap"])
        self.assertEqual(result["sources"], partial["sources"])
        self.assertNotIn("quiz", partial)
        self.assertNotIn("videos", partial)
        self.assertNotIn("historical_images", partial)
        self.assertNotIn("answer_id", partial)
        self.assertEqual("Cách mạng tư sản Anh bùng nổ năm nào?", result["question"])
        self.assertEqual(5, len(result["quiz"]["questions"]))

    def test_image_stream_keeps_upload_available_until_processing_finishes(self) -> None:
        response = self.make_client().post(
            "/api/questions/ask-image-stream",
            files={"file": ("question.png", _png_bytes(), "image/png")},
            data={"mode": "hybrid", "top_k": "3"},
        )

        self.assertEqual(200, response.status_code, response.text)
        events = _events(response.text)
        image_stage = next(
            event for event in events if event.get("stage") == "retrieval"
        )
        self.assertIn("nhận dạng ảnh", image_stage["message"])
        self.assertEqual("result", events[-1]["type"])

    def test_domain_failure_is_a_terminal_stream_event(self) -> None:
        response = self.make_client(retrieval=FakeRetrieval(matches=[])).post(
            "/api/questions/ask-stream",
            json={"question": "Câu hỏi chưa có trong kho dữ liệu"},
        )

        self.assertEqual(200, response.status_code)
        error = _events(response.text)[-1]
        self.assertEqual("error", error["type"])
        self.assertEqual("KNOWLEDGE_NOT_FOUND", error["error"]["code"])
        self.assertEqual(404, error["error"]["status"])


if __name__ == "__main__":
    unittest.main()
