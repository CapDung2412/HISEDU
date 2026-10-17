from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from hisedu.webapi.app import create_app
from hisedu.webapi.historical_image_recommender import (
    CuratedHistoricalImageRecommender,
    _CATALOG,
)
from hisedu.webapi.schemas import HistoricalImage
from hisedu.webapi.services import GenerationResult
from hisedu.webapi.settings import WebSettings

from .helpers import FakeAI, FakeRetrieval, generated_lesson


def _settings() -> WebSettings:
    return WebSettings(
        chatgpt_api_key=None,
        enable_web_search=False,
        rate_limit_requests=100,
    )


class CuratedHistoricalImageRecommenderTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_catalog_image_exists_in_the_frontend_archive(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]

        for item in _CATALOG:
            with self.subTest(image_id=item.image.id):
                relative_path = item.image.image_url.removeprefix("/")
                self.assertTrue(
                    (repository_root / "web" / "public" / relative_path).is_file(),
                    item.image.image_url,
                )

    async def test_accentless_query_ranks_exact_french_subject_first(self) -> None:
        provider = CuratedHistoricalImageRecommender()

        images = await provider.recommend(
            question="Vi sao nhan dan Paris danh chiem nguc Bastille nam 1789?",
            topics=["Cach mang tu san Phap"],
            limit=4,
        )

        self.assertEqual(2, len(images))
        self.assertEqual("/historical/storming-of-bastille.jpg", images[0].image_url)
        self.assertTrue(all(image.source_url.startswith("https://") for image in images))
        self.assertTrue(all(image.alt and image.observation_prompt for image in images))

    async def test_unrelated_question_has_no_decorative_fallback(self) -> None:
        provider = CuratedHistoricalImageRecommender()

        images = await provider.recommend(
            question="Nhà Trần ba lần kháng chiến chống Mông Nguyên như thế nào?",
            topics=["Lịch sử Việt Nam thế kỷ XIII"],
        )

        self.assertEqual([], images)

    async def test_phrase_matching_does_not_confuse_charles_i_with_charles_ii(self) -> None:
        provider = CuratedHistoricalImageRecommender()

        images = await provider.recommend(
            question="Charles II cai trị nước Anh trong giai đoạn nào?",
        )

        self.assertEqual([], images)

    async def test_question_scope_beats_noisy_cross_country_topic(self) -> None:
        provider = CuratedHistoricalImageRecommender()

        images = await provider.recommend(
            question="Vai trò của Cromwell trong Cách mạng tư sản Anh là gì?",
            topics=["Cách mạng tư sản Pháp", "Bastille"],
        )

        self.assertEqual(2, len(images))
        self.assertEqual("/historical/oliver-cromwell-1649.jpg", images[0].image_url)
        self.assertTrue(all("bastille" not in image.image_url for image in images))

    async def test_retrieved_lesson_title_cannot_introduce_a_different_event(self) -> None:
        provider = CuratedHistoricalImageRecommender()

        images = await provider.recommend(
            question="Cách mạng tháng Mười Nga năm 1917 có ý nghĩa gì?",
            topics=[
                "Chiến tranh thế giới thứ nhất (1914 - 1918) và "
                "Cách mạng tháng Mười Nga năm 1917"
            ],
        )

        self.assertEqual([], images)

    async def test_provider_version_is_stable_and_content_derived(self) -> None:
        first = CuratedHistoricalImageRecommender().provider_version
        second = CuratedHistoricalImageRecommender().provider_version

        self.assertEqual(first, second)
        self.assertRegex(first, r"^curated-historical-images-v1-[a-f0-9]{16}$")

    async def test_additional_grade_eight_topics_have_reviewed_materials(self) -> None:
        provider = CuratedHistoricalImageRecommender()
        cases = (
            ("Sự kiện chè Boston có ý nghĩa gì?", "boston-tea-party"),
            ("Máy kéo sợi Gien-ni làm thay đổi sản xuất như thế nào?", "spinning-jenny"),
            ("Công xã Pa-ri năm 1871 ra đời trong hoàn cảnh nào?", "paris-commune-barricade"),
            ("Cuộc Duy tân Minh Trị bắt đầu trong hoàn cảnh nào?", "emperor-meiji"),
            ("Chiến tranh thế giới thứ nhất diễn ra qua những giai đoạn nào?", "world-war-one-trench"),
        )

        for question, expected_id in cases:
            with self.subTest(question=question):
                images = await provider.recommend(question=question)
                self.assertGreaterEqual(len(images), 1)
                self.assertEqual(expected_id, images[0].id)


class HistoricalImageApiTests(unittest.TestCase):
    def test_api_returns_curated_images_only_in_final_response_and_caches_them(self) -> None:
        class CountingProvider:
            provider_version = "counting-images-v1"

            def __init__(self) -> None:
                self.calls = 0

            async def recommend(self, **kwargs):
                self.calls += 1
                return [
                    HistoricalImage(
                        id="test-historical-image",
                        title="Tư liệu thử nghiệm",
                        description="Mô tả tư liệu đã được kiểm duyệt.",
                        image_url="/historical/battle-of-naseby.jpg",
                        source_url="https://commons.wikimedia.org/wiki/File:Example.jpg",
                        institution="Bảo tàng thử nghiệm",
                        license="Public domain",
                        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
                        creator="Tác giả",
                        date="Năm 1645",
                        media_type="engraving",
                        alt="Bản khắc lịch sử.",
                        observation_prompt="Em quan sát thấy những lực lượng nào?",
                        relevance="Tư liệu liên quan trực tiếp đến câu hỏi.",
                    )
                ]

        provider = CountingProvider()
        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=FakeAI(),
            settings=_settings(),
            historical_image_recommender=provider,
        )
        client = TestClient(app, raise_server_exceptions=False)
        payload = {"question": "Cách mạng tư sản Anh bùng nổ năm nào?"}

        first = client.post("/api/questions/ask", json=payload)
        second = client.post("/api/questions/ask", json=payload)

        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(1, len(first.json()["historical_images"]))
        self.assertEqual(first.json()["historical_images"], second.json()["historical_images"])
        self.assertEqual(1, provider.calls)
        self.assertIn("historical_images;dur=", first.headers["server-timing"])
        # Cache hits do not rerun enrichment and therefore add no fake timing.
        self.assertNotIn("historical_images;dur=", second.headers["server-timing"])

    def test_provider_version_change_invalidates_response_cache(self) -> None:
        class VersionedProvider:
            provider_version = "images-v1"

            def __init__(self) -> None:
                self.calls = 0

            async def recommend(self, **kwargs):
                self.calls += 1
                return []

        provider = VersionedProvider()
        ai = FakeAI()
        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=ai,
            settings=_settings(),
            historical_image_recommender=provider,
        )
        client = TestClient(app, raise_server_exceptions=False)
        payload = {"question": "Cách mạng tư sản Anh bùng nổ năm nào?"}

        self.assertEqual(200, client.post("/api/questions/ask", json=payload).status_code)
        provider.provider_version = "images-v2"
        self.assertEqual(200, client.post("/api/questions/ask", json=payload).status_code)

        self.assertEqual(2, provider.calls)
        self.assertEqual(2, ai.calls)

    def test_invalid_provider_result_fails_closed(self) -> None:
        class InvalidProvider:
            provider_version = "invalid-images-v1"

            async def recommend(self, **kwargs):
                return [{"image_url": "https://remote.example/image.jpg"}]

        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=FakeAI(),
            settings=_settings(),
            historical_image_recommender=InvalidProvider(),
        )

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/questions/ask",
            json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([], response.json()["historical_images"])

    def test_image_lookup_starts_while_ai_is_generating(self) -> None:
        events: list[str] = []

        class SlowAI(FakeAI):
            async def generate(self, question, matches):
                events.append("ai-start")
                await asyncio.sleep(0.02)
                events.append("ai-end")
                return GenerationResult(lesson=generated_lesson(), web_urls=set())

        class ConcurrentProvider:
            provider_version = "concurrent-images-v1"

            async def recommend(self, **kwargs):
                events.append("image-start")
                await asyncio.sleep(0)
                events.append("image-end")
                return []

        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=SlowAI(),
            settings=_settings(),
            historical_image_recommender=ConcurrentProvider(),
        )

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/questions/ask",
            json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertLess(events.index("image-start"), events.index("ai-end"))


if __name__ == "__main__":
    unittest.main()
