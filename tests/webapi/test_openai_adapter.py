from __future__ import annotations

import unittest

from hisedu.webapi.errors import AiServiceError
from hisedu.webapi.openai_adapter import OpenAIResponsesAdapter, WEB_SEARCH_DOMAINS
from hisedu.webapi.schemas import GeneratedLesson
from hisedu.webapi.settings import WebSettings

from .helpers import YOUTUBE_URL, generated_lesson


class FakeResponses:
    def __init__(self, response) -> None:
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, response) -> None:
        self.responses = FakeResponses(response)


class FakeResponse:
    status = "completed"

    def __init__(self, lesson: GeneratedLesson) -> None:
        self.output_text = lesson.model_dump_json()

    def model_dump(self):
        return {
            "status": "completed",
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "annotations": [
                                {"type": "url_citation", "url": YOUTUBE_URL}
                            ],
                        }
                    ]
                }
            ],
        }


class OpenAIAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_non_persistent_call_uses_strict_schema_and_one_web_tool(self) -> None:
        client = FakeClient(FakeResponse(generated_lesson()))
        adapter = OpenAIResponsesAdapter(
            WebSettings(chatgpt_api_key="server-only", enable_web_search=True),
            client=client,
        )
        result = await adapter.generate("Câu hỏi", [{"id": "1", "fields": {}}])
        self.assertEqual({YOUTUBE_URL}, result.web_urls)
        kwargs = client.responses.kwargs
        self.assertFalse(kwargs["store"])
        self.assertEqual(1, kwargs["max_tool_calls"])
        self.assertEqual(
            [
                {
                    "type": "web_search",
                    "search_context_size": "low",
                    "filters": {"allowed_domains": WEB_SEARCH_DOMAINS},
                }
            ],
            kwargs["tools"],
        )
        self.assertFalse(kwargs["parallel_tool_calls"])
        self.assertEqual(["web_search_call.action.sources"], kwargs["include"])
        self.assertTrue(kwargs["text"]["format"]["strict"])
        schema = kwargs["text"]["format"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(schema["required"]))

    async def test_incomplete_or_refusal_is_rejected(self) -> None:
        for response in (
            {"status": "incomplete", "output_text": "{}"},
            {"status": "completed", "output": [{"type": "refusal", "refusal": "no"}]},
        ):
            with self.subTest(response=response["status"]):
                adapter = OpenAIResponsesAdapter(
                    WebSettings(chatgpt_api_key="server-only"),
                    client=FakeClient(response),
                )
                with self.assertRaises(AiServiceError):
                    await adapter.generate("Câu hỏi", [])


if __name__ == "__main__":
    unittest.main()
