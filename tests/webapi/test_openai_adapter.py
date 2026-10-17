from __future__ import annotations

import asyncio
import unittest

from hisedu.webapi.errors import AiServiceError
from hisedu.webapi.openai_adapter import (
    QUIZ_DEGRADED_LIMITATION,
    OpenAIResponsesAdapter,
    WEB_SEARCH_DOMAINS,
    _citation_urls,
)
from hisedu.webapi.schemas import GeneratedLessonCore, GeneratedQuizBatch, Mindmap
from hisedu.webapi.settings import WebSettings

from .helpers import YOUTUBE_URL, generated_lesson


class FakeResponses:
    def __init__(self, responses, *, delay: float = 0.0) -> None:
        self.responses = responses
        self.delay = delay
        self.calls: list[dict] = []
        self.active = 0
        self.max_active = 0

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            name = kwargs["text"]["format"]["name"]
            if isinstance(self.responses, dict) and name in self.responses:
                return self.responses[name]
            return self.responses
        finally:
            self.active -= 1


class FakeClient:
    def __init__(self, responses, *, delay: float = 0.0) -> None:
        self.responses = FakeResponses(responses, delay=delay)


class CoreFirstResponses(FakeResponses):
    """Quiz cannot finish until the core-ready callback releases it."""

    def __init__(self, responses) -> None:
        super().__init__(responses)
        self.release_quiz = asyncio.Event()

    async def create(self, **kwargs):
        name = kwargs["text"]["format"]["name"]
        self.calls.append(kwargs)
        if name == "hisedu_quiz":
            await self.release_quiz.wait()
        return self.responses[name]


class CoreFirstClient:
    def __init__(self, responses) -> None:
        self.responses = CoreFirstResponses(responses)


class FakeResponse:
    status = "completed"

    def __init__(self, payload, *, citation_url: str | None = None) -> None:
        self.output_text = payload.model_dump_json()
        self.citation_url = citation_url

    def model_dump(self):
        annotations = []
        if self.citation_url:
            annotations.append({"type": "url_citation", "url": self.citation_url})
        return {
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "annotations": annotations}]}],
        }


def split_responses():
    lesson = generated_lesson()
    core = GeneratedLessonCore.model_validate(lesson.model_dump(exclude={"quiz"}))
    quiz = GeneratedQuizBatch(quiz=lesson.quiz)
    return {
        "hisedu_lesson_core": FakeResponse(core, citation_url=YOUTUBE_URL),
        "hisedu_quiz": FakeResponse(quiz),
    }


class OpenAIAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_core_callback_runs_before_waiting_for_quiz(self) -> None:
        client = CoreFirstClient(split_responses())
        adapter = OpenAIResponsesAdapter(
            WebSettings(
                chatgpt_api_key="server-only",
                openai_quiz_grace_seconds=0.2,
            ),
            client=client,
        )
        observed: list[tuple[str, set[str]]] = []

        async def on_core_ready(core, web_urls) -> None:
            observed.append((core.answer.summary, web_urls))
            client.responses.release_quiz.set()

        result = await asyncio.wait_for(
            adapter.generate_with_core_progress(
                "Câu hỏi",
                [{"id": "1", "fields": {}}],
                on_core_ready=on_core_ready,
            ),
            timeout=1.0,
        )

        self.assertEqual(
            [("Cách mạng tư sản Anh bùng nổ năm 1642.", {YOUTUBE_URL})],
            observed,
        )
        self.assertEqual(5, len(result.lesson.quiz))

    async def test_citation_walker_ignores_non_string_type_values(self) -> None:
        response = {
            "type": {"kind": "response"},
            "output": [
                {"type": "url_citation", "url": YOUTUBE_URL},
                {"type": ["unexpected"], "url": "https://example.com"},
            ],
        }
        self.assertEqual({YOUTUBE_URL}, _citation_urls(response))

    async def test_unreachable_mindmap_is_repaired_instead_of_rejecting_lesson(self) -> None:
        mindmap = Mindmap.model_validate(
            {
                "title": "Bài học",
                "nodes": [
                    {
                        "id": "root",
                        "label": "Gốc",
                        "description": "Chủ đề",
                        "type": "root",
                    },
                    *[
                        {
                            "id": f"n{index}",
                            "label": f"Nhánh {index}",
                            "description": f"Ý {index}",
                            "type": "event",
                        }
                        for index in range(1, 6)
                    ],
                ],
                "edges": [{"source": "n1", "target": "root"}],
            }
        )

        self.assertEqual(
            {("root", f"n{index}") for index in range(1, 6)},
            {(edge.source, edge.target) for edge in mindmap.edges},
        )

    async def test_mindmap_repair_preserves_valid_multilevel_branches(self) -> None:
        mindmap = Mindmap.model_validate(
            {
                "title": "Bài học",
                "nodes": [
                    {
                        "id": "root",
                        "label": "Gốc",
                        "description": "Chủ đề",
                        "type": "root",
                    },
                    *[
                        {
                            "id": f"n{index}",
                            "label": f"Nhánh {index}",
                            "description": f"Ý {index}",
                            "type": "event",
                        }
                        for index in range(1, 6)
                    ],
                ],
                "edges": [
                    {"source": "root", "target": "n1"},
                    {"source": "n1", "target": "n2"},
                    {"source": "n3", "target": "n4"},
                ],
            }
        )

        pairs = {(edge.source, edge.target) for edge in mindmap.edges}
        self.assertIn(("root", "n1"), pairs)
        self.assertIn(("n1", "n2"), pairs)
        self.assertIn(("n3", "n4"), pairs)
        self.assertIn(("root", "n3"), pairs)
        self.assertIn(("root", "n5"), pairs)

    async def test_mindmap_normalizes_duplicate_ids_roots_and_type_aliases(self) -> None:
        mindmap = Mindmap.model_validate(
            {
                "title": "Bài học",
                "nodes": [
                    {
                        "id": "chủ đề",
                        "label": "Chủ đề",
                        "description": "Nội dung chính",
                        "type": "root",
                        "unexpected": "ignored",
                    },
                    {
                        "id": "chủ đề",
                        "label": "Nút gốc dư",
                        "description": "Vẫn giữ nội dung",
                        "type": "root",
                    },
                    {
                        "id": "mốc thời gian",
                        "label": "Mốc năm",
                        "description": "Một mốc quan trọng",
                        "type": "timeline",
                    },
                ],
                "edges": [
                    {"source": "chủ đề", "target": "mốc thời gian"},
                    {"source": "không tồn tại", "target": "chủ đề"},
                ],
            }
        )

        self.assertEqual(3, len({node.id for node in mindmap.nodes}))
        self.assertEqual(1, sum(node.type == "root" for node in mindmap.nodes))
        self.assertEqual("time", mindmap.nodes[2].type)
        self.assertTrue(all(" " not in node.id for node in mindmap.nodes))
        self.assertNotIn(
            "không tồn tại", {edge.source for edge in mindmap.edges}
        )

    async def test_partial_one_node_mindmap_is_usable_instead_of_failing_lesson(self) -> None:
        mindmap = Mindmap.model_validate(
            {
                "title": "Bài học",
                "nodes": [
                    {
                        "id": "topic",
                        "label": "Chủ đề",
                        "description": "Nội dung đang có",
                        "type": "event",
                    }
                ],
                "edges": [],
            }
        )

        self.assertEqual("root", mindmap.nodes[0].type)

        empty = Mindmap.model_validate(
            {"title": "Bài học chưa đủ nhánh", "nodes": [], "edges": []}
        )
        self.assertEqual("root", empty.nodes[0].type)
        self.assertEqual("Bài học chưa đủ nhánh", empty.nodes[0].label)

    async def test_adapter_accepts_repairable_core_mindmap(self) -> None:
        responses = split_responses()
        core_payload = generated_lesson().model_dump(exclude={"quiz"})
        core_payload["mindmap"]["nodes"][0]["id"] = "chủ đề"
        core_payload["mindmap"]["nodes"][1]["id"] = "chủ đề"
        core_payload["mindmap"]["nodes"][1]["type"] = "root"
        core_payload["mindmap"]["nodes"][2]["type"] = "timeline"
        core_payload["mindmap"]["edges"].append(
            {"source": "missing", "target": "chủ đề"}
        )
        responses["hisedu_lesson_core"] = {
            "status": "completed",
            "output_parsed": core_payload,
        }
        adapter = OpenAIResponsesAdapter(
            WebSettings(chatgpt_api_key="server-only"),
            client=FakeClient(responses),
        )

        result = await adapter.generate("Câu hỏi", [{"id": "1", "fields": {}}])

        self.assertEqual(1, sum(node.type == "root" for node in result.lesson.mindmap.nodes))
        self.assertEqual(
            len(result.lesson.mindmap.nodes),
            len({node.id for node in result.lesson.mindmap.nodes}),
        )

    async def test_parallel_calls_use_strict_schemas_and_web_only_for_core(self) -> None:
        client = FakeClient(split_responses(), delay=0.01)
        adapter = OpenAIResponsesAdapter(
            WebSettings(chatgpt_api_key="server-only", enable_web_search=True),
            client=client,
        )

        result = await adapter.generate(
            "Cách mạng tư sản Anh",
            [
                {
                    "id": "1",
                    "fields": {
                        "question": "Cách mạng tư sản Anh",
                        "answer": "Nội chiến bùng nổ năm 1642.",
                    },
                },
                {
                    "id": "2",
                    "fields": {
                        "question": "Cách mạng tư sản Pháp",
                        "answer": "Cách mạng bùng nổ năm 1789.",
                    },
                },
            ],
        )

        self.assertEqual({YOUTUBE_URL}, result.web_urls)
        self.assertEqual(5, len(result.lesson.quiz))
        self.assertEqual(2, client.responses.max_active)
        self.assertEqual(2, len(client.responses.calls))
        calls = {
            call["text"]["format"]["name"]: call for call in client.responses.calls
        }
        core = calls["hisedu_lesson_core"]
        quiz = calls["hisedu_quiz"]
        self.assertFalse(core["store"])
        self.assertFalse(quiz["store"])
        self.assertEqual(2_200, core["max_output_tokens"])
        self.assertEqual(1_200, quiz["max_output_tokens"])
        self.assertEqual(1, core["max_tool_calls"])
        self.assertEqual(
            [
                {
                    "type": "web_search",
                    "search_context_size": "low",
                }
            ],
            core["tools"],
        )
        self.assertNotIn("filters", core["tools"][0])
        for domain in WEB_SEARCH_DOMAINS:
            self.assertIn(domain, core["instructions"])
        self.assertFalse(core["parallel_tool_calls"])
        self.assertEqual(["web_search_call.action.sources"], core["include"])
        self.assertNotIn("tools", quiz)
        self.assertIn('"source_id": "S1"', core["input"])
        self.assertIn('"source_id": "S2"', core["input"])
        self.assertNotIn('"source_id": "S2"', quiz["input"])
        self.assertNotIn("Cách mạng tư sản Pháp", quiz["input"])
        for call in calls.values():
            output_format = call["text"]["format"]
            self.assertTrue(output_format["strict"])
            schema = output_format["schema"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["properties"]), set(schema["required"]))

    async def test_quiz_failure_returns_main_lesson_instead_of_failing_all(self) -> None:
        responses = split_responses()
        responses["hisedu_quiz"] = {"status": "incomplete", "output_text": "{}"}
        adapter = OpenAIResponsesAdapter(
            WebSettings(chatgpt_api_key="server-only"),
            client=FakeClient(responses),
        )

        result = await adapter.generate("Câu hỏi", [{"id": "1", "fields": {}}])

        self.assertEqual([], result.lesson.quiz)
        self.assertIn(QUIZ_DEGRADED_LIMITATION, result.lesson.limitations)

    async def test_core_incomplete_or_refusal_is_rejected(self) -> None:
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
