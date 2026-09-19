from __future__ import annotations

from typing import Any

from hisedu.webapi.schemas import GeneratedLesson
from hisedu.webapi.services import GenerationResult, RetrievalResult


YOUTUBE_URL = "https://www.youtube.com/watch?v=history-test"


def generated_lesson(*, source_page: int | None = 99) -> GeneratedLesson:
    return GeneratedLesson.model_validate(
        {
            "answer": {
                "summary": "Cách mạng tư sản Anh bùng nổ năm 1642.",
                "sections": [
                    {
                        "heading": "Diễn biến",
                        "content": "Nội chiến bắt đầu năm 1642.",
                        "citation_ids": ["S1"],
                    }
                ],
                "key_points": ["Năm 1642"],
                "citation_ids": ["S1"],
            },
            "mindmap": {
                "title": "Cách mạng tư sản Anh",
                "nodes": [
                    {
                        "id": "root",
                        "label": "Cách mạng Anh",
                        "description": "Sự kiện lịch sử",
                        "type": "root",
                    },
                    *[
                        {
                            "id": f"node-{index}",
                            "label": f"Nhánh {index}",
                            "description": f"Kiến thức {index}",
                            "type": "event",
                        }
                        for index in range(1, 6)
                    ],
                ],
                "edges": [
                    {"source": "root", "target": f"node-{index}"}
                    for index in range(1, 6)
                ],
            },
            "videos": [
                {
                    "title": "Diễn biến cách mạng Anh",
                    "url": YOUTUBE_URL,
                    "publisher": "Kênh giáo dục",
                    "relevance": "Tóm tắt diễn biến",
                    "label": "event",
                }
            ],
            "sources": [
                {
                    "id": "S1",
                    "title": "Bài 1",
                    "publisher": "SGK Lịch sử",
                    "type": "sgk",
                    "url": None,
                    "page": source_page,
                    "locator": "Bài 1",
                    "accessed_at": None,
                    "supports": ["Mốc năm 1642"],
                }
            ],
            "quiz": [
                {
                    "id": f"q{index}",
                    "prompt": f"Câu hỏi {index}?",
                    "options": [
                        {"id": f"q{index}_{letter}", "text": f"Lựa chọn {letter}"}
                        for letter in "abcd"
                    ],
                    "correct_option_id": f"q{index}_a",
                    "explanation": "Đáp án A đúng.",
                    "source_ids": ["S1"],
                }
                for index in range(1, 6)
            ],
            "limitations": [],
        }
    )


class FakeRetrieval:
    def __init__(self, *, matches: list[dict[str, Any]] | None = None) -> None:
        self.matches = matches if matches is not None else [
            {
                "id": "chunk-1",
                "score": 0.95,
                "fields": {
                    "dataset_version": "1.0.0",
                    "question": "Cách mạng tư sản Anh bùng nổ năm nào?",
                    "answer": "Năm 1642.",
                    "source_name": "SGK Lịch sử",
                    "source_locator": "Bài 1",
                },
            }
        ]
        self.text_calls = 0
        self.image_calls = 0

    async def search_text(self, question: str, *, top_k: int) -> RetrievalResult:
        self.text_calls += 1
        return RetrievalResult(query=question, matches=self.matches[:top_k])

    async def search_image(self, data: bytes, **kwargs) -> RetrievalResult:
        self.image_calls += 1
        question = kwargs.get("question") or "Câu hỏi đọc từ ảnh"
        return RetrievalResult(query=question, matches=self.matches, score_kind="cosine")


class FakeAI:
    def __init__(
        self,
        lesson: GeneratedLesson | None = None,
        *,
        error: Exception | None = None,
        web_urls: set[str] | None = None,
    ) -> None:
        self.lesson = lesson or generated_lesson()
        self.error = error
        self.web_urls = web_urls if web_urls is not None else {YOUTUBE_URL}
        self.calls = 0

    async def generate(self, question: str, matches: list[dict[str, Any]]):
        self.calls += 1
        if self.error:
            raise self.error
        return GenerationResult(lesson=self.lesson, web_urls=self.web_urls)
