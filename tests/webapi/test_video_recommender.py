from __future__ import annotations

import asyncio
import unittest
from typing import Any

from fastapi.testclient import TestClient

from hisedu.webapi.app import create_app
from hisedu.webapi.schemas import Video
from hisedu.webapi.settings import WebSettings
from hisedu.webapi.video_recommender import (
    ALLOWED_YOUTUBE_CHANNELS,
    MAX_RECOMMENDED_VIDEOS,
    YOUTUBE_SEARCH_URL,
    YouTubeVideoRecommender,
    normalize_vietnamese,
)

from .helpers import FakeAI, FakeRetrieval, YOUTUBE_URL, generated_lesson


EZ_SU_ID = "UCpaQwg8wZRAkFJe3mo1VKSA"
SU_LUOC_ID = "UCJDueHzfSEXmgMhmKIa9esQ"


def search_item(
    video_id: str,
    *,
    channel_id: str = EZ_SU_ID,
    title: str = "Tóm tắt Cách mạng công nghiệp",
    description: str = "Diễn biến và tác động của Cách mạng công nghiệp",
) -> dict[str, Any]:
    return {
        "id": {"kind": "youtube#video", "videoId": video_id},
        "snippet": {
            "channelId": channel_id,
            "channelTitle": "Tên từ API không được tin cậy",
            "title": title,
            "description": description,
        },
    }


class YouTubeVideoRecommenderTests(unittest.IsolatedAsyncioTestCase):
    def test_normalization_is_accent_insensitive_and_handles_d_stroke(self) -> None:
        self.assertEqual(
            "cach mang cong nghiep dong duong",
            normalize_vietnamese("CÁCH MẠNG công nghiệp Đông Dương"),
        )

    def test_allowlist_contains_exactly_the_five_requested_channels(self) -> None:
        self.assertEqual(
            {
                "EZ Sử",
                "HTV Tin Tức",
                "VTV24",
                "Sử Lược - Tóm Tắt Lịch Sử",
                "Dòng Máu Việt",
            },
            set(ALLOWED_YOUTUBE_CHANNELS.values()),
        )

    async def test_missing_key_returns_empty_without_network(self) -> None:
        calls = 0

        async def transport(*args):
            nonlocal calls
            calls += 1
            return {"items": []}

        service = YouTubeVideoRecommender(None, transport=transport)

        self.assertEqual(
            [],
            await service.recommend(question="Cách mạng công nghiệp"),
        )
        self.assertEqual(0, calls)

    async def test_one_api_call_filters_by_channel_id_and_builds_safe_url(self) -> None:
        calls: list[tuple[str, dict[str, str], dict[str, str], float]] = []

        async def transport(url, params, headers, timeout):
            calls.append((url, dict(params), dict(headers), timeout))
            return {
                "items": [
                    search_item(
                        "abcDEF12345",
                        title="Cách mạng &amp; công nghiệp",
                    ),
                    search_item(
                        "badCHAN1234",
                        channel_id="UC0000000000000000000000",
                    ),
                    search_item("not-a-valid-video-id"),
                ]
            }

        service = YouTubeVideoRecommender("server-secret", transport=transport)
        videos = await service.recommend(
            question="Cách mạng công nghiệp bắt đầu ở đâu?",
            topics=["Cách mạng công nghiệp"],
            limit=1,
        )

        self.assertEqual(1, len(calls))
        url, params, headers, timeout = calls[0]
        self.assertEqual(YOUTUBE_SEARCH_URL, url)
        self.assertNotIn("key", params)
        self.assertEqual("server-secret", headers["X-Goog-Api-Key"])
        self.assertEqual("video", params["type"])
        self.assertEqual("50", params["maxResults"])
        self.assertEqual("strict", params["safeSearch"])
        self.assertEqual("Cách mạng công nghiệp", params["q"])
        self.assertEqual(5.0, timeout)
        self.assertEqual(1, len(videos))
        self.assertEqual("Cách mạng & công nghiệp", videos[0].title)
        self.assertEqual("EZ Sử", videos[0].publisher)
        self.assertEqual(
            "https://www.youtube.com/watch?v=abcDEF12345", videos[0].url
        )

    async def test_search_uses_one_concise_question_aligned_topic(self) -> None:
        calls: list[dict[str, str]] = []

        async def transport(url, params, headers, timeout):
            calls.append(dict(params))
            return {
                "items": [
                    search_item(
                        "topicqry001",
                        title="Cách mạng tư sản Anh thế kỷ XVII",
                        description="Nguyên nhân và diễn biến cách mạng.",
                    )
                ]
            }

        service = YouTubeVideoRecommender("key", transport=transport)
        await service.recommend(
            question="Vì sao Cách mạng tư sản Anh bùng nổ giữa thế kỷ XVII?",
            topics=[
                "Vì sao Cách mạng tư sản Anh bùng nổ giữa thế kỷ XVII?",
                "Châu Âu và Bắc Mỹ từ nửa sau thế kỷ XVI",
                "Cách mạng tư sản Anh và chiến tranh giành độc lập của 13 thuộc địa Anh ở Bắc Mỹ",
            ],
            limit=1,
        )

        self.assertEqual(1, len(calls))
        self.assertEqual("Cách mạng tư sản Anh", calls[0]["q"])
        self.assertNotIn("Vì sao", calls[0]["q"])

    async def test_verified_ez_su_video_fills_french_revolution_api_gap(self) -> None:
        async def transport(*args):
            return {"items": []}

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Vì sao Cách mạng tư sản Pháp bùng nổ?",
            topics=["Cách mạng tư sản Pháp cuối thế kỷ XVIII"],
        )

        self.assertEqual(1, len(videos))
        self.assertEqual("EZ Sử", videos[0].publisher)
        self.assertEqual(
            "https://www.youtube.com/watch?v=t5fahfNM67w",
            videos[0].url,
        )

    async def test_sparse_search_backfills_specialist_channels_and_returns_more(self) -> None:
        calls: list[dict[str, str]] = []

        async def transport(url, params, headers, timeout):
            request = dict(params)
            calls.append(request)
            channel_id = request.get("channelId")
            if channel_id == EZ_SU_ID:
                return {
                    "items": [
                        search_item(
                            "ezIndustr01",
                            title="Cách mạng công nghiệp lần thứ nhất",
                            description="Khởi đầu, diễn biến và tác động.",
                        ),
                        search_item(
                            "ezIndustr02",
                            title="Máy hơi nước trong Cách mạng công nghiệp",
                            description="James Watt và thay đổi trong sản xuất.",
                        ),
                    ]
                }
            if channel_id == SU_LUOC_ID:
                return {
                    "items": [
                        search_item(
                            "suIndustr01",
                            channel_id=SU_LUOC_ID,
                            title="Tóm tắt Cách mạng công nghiệp",
                            description="Nguyên nhân, thành tựu và hệ quả.",
                        )
                    ]
                }
            # A broad YouTube result from a look-alike channel is not trusted.
            return {
                "items": [
                    search_item(
                        "fakeChannel1",
                        channel_id="UC0000000000000000000000",
                    )
                ]
            }

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Cách mạng công nghiệp bắt đầu như thế nào?",
            topics=["Cách mạng công nghiệp"],
        )

        self.assertEqual(3, len(calls))
        self.assertNotIn("channelId", calls[0])
        self.assertEqual(
            {EZ_SU_ID, SU_LUOC_ID},
            {call["channelId"] for call in calls[1:]},
        )
        self.assertEqual(3, len(videos))
        self.assertEqual(
            {
                "https://www.youtube.com/watch?v=ezIndustr01",
                "https://www.youtube.com/watch?v=ezIndustr02",
                "https://www.youtube.com/watch?v=suIndustr01",
            },
            {video.url for video in videos},
        )
        self.assertTrue(
            all(video.publisher in ALLOWED_YOUTUBE_CHANNELS.values() for video in videos)
        )

    async def test_rank_uses_title_before_description_for_same_topic(self) -> None:
        async def transport(*args):
            return {
                "items": [
                    search_item(
                        "descOnly001",
                        title="Bài giảng lịch sử thế giới",
                        description="Cách mạng công nghiệp và máy hơi nước.",
                    ),
                    search_item(
                        "titleHit001",
                        title="Cách mạng công nghiệp",
                        description="Bài học lớp 8.",
                    ),
                ]
            }

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Cách mạng công nghiệp là gì?",
            limit=2,
        )

        self.assertEqual(2, len(videos))
        self.assertEqual("titleHit001", videos[0].url.rsplit("=", 1)[-1])

    async def test_curated_video_cannot_bypass_custom_channel_allowlist(self) -> None:
        calls = 0

        async def transport(*args):
            nonlocal calls
            calls += 1
            return {"items": []}

        service = YouTubeVideoRecommender(
            "key",
            allowed_channels={SU_LUOC_ID: "Sử Lược - Tóm Tắt Lịch Sử"},
            transport=transport,
        )
        videos = await service.recommend(
            question="Cách mạng tư sản Pháp bùng nổ vì sao?",
            limit=1,
        )

        self.assertEqual([], videos)
        self.assertEqual(2, calls)

    async def test_generic_topic_fails_closed_without_spending_api_quota(self) -> None:
        calls = 0

        async def transport(*args):
            nonlocal calls
            calls += 1
            return {"items": []}

        service = YouTubeVideoRecommender("key", transport=transport)

        self.assertEqual([], await service.recommend(question="Lịch sử"))
        self.assertEqual(0, calls)

    async def test_common_words_do_not_create_false_country_entities(self) -> None:
        cases = (
            (
                "Anh hùng Quang Trung có vai trò gì?",
                "Quang Trung - người anh hùng áo vải",
                "heroViet001",
            ),
            (
                "Nhà Nguyễn dùng biện pháp nào để củng cố chính quyền?",
                "Nhà Nguyễn củng cố chính quyền",
                "measure0001",
            ),
        )
        for question, title, video_id in cases:
            with self.subTest(question=question):
                async def transport(*args):
                    return {
                        "items": [search_item(video_id, title=title, description="")]
                    }

                service = YouTubeVideoRecommender("key", transport=transport)
                videos = await service.recommend(question=question, limit=1)

                self.assertEqual(1, len(videos))
                self.assertEqual(video_id, videos[0].url.rsplit("=", 1)[-1])

    async def test_cache_reuses_accent_insensitive_query_and_caches_empty(self) -> None:
        calls = 0

        async def transport(*args):
            nonlocal calls
            calls += 1
            return {"items": []}

        service = YouTubeVideoRecommender("key", transport=transport)
        first = await service.recommend(question="Cách mạng công nghiệp")
        second = await service.recommend(question="CACH MANG CONG NGHIEP")

        self.assertEqual([], first)
        self.assertEqual([], second)
        # One broad search plus two allowlisted specialist searches; the
        # second equivalent query is served entirely from the local TTL cache.
        self.assertEqual(3, calls)

    async def test_api_failure_is_cached_and_fails_closed(self) -> None:
        calls = 0

        async def transport(*args):
            nonlocal calls
            calls += 1
            raise RuntimeError("request URL could contain a secret")

        service = YouTubeVideoRecommender("secret", transport=transport)

        self.assertEqual([], await service.recommend(question="Phong trào Tây Sơn"))
        self.assertEqual([], await service.recommend(question="Phong trào Tây Sơn"))
        self.assertEqual(1, calls)

    async def test_results_are_deduplicated_and_capped_at_six(self) -> None:
        async def transport(*args):
            return {
                "items": [
                    search_item("videoID0001", title="Tây Sơn và Nguyễn Huệ"),
                    search_item("videoID0001", title="Bản trùng"),
                    search_item("videoID0002", title="Diễn biến phong trào Tây Sơn"),
                    search_item("videoID0003", title="Kết quả phong trào Tây Sơn"),
                    search_item("videoID0004", title="Ý nghĩa phong trào Tây Sơn"),
                    search_item("videoID0005", title="Nhân vật phong trào Tây Sơn"),
                    search_item("videoID0006", title="Bối cảnh phong trào Tây Sơn"),
                    search_item("videoID0007", title="Bài học phong trào Tây Sơn"),
                ]
            }

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Phong trào Tây Sơn", limit=10
        )

        self.assertEqual(MAX_RECOMMENDED_VIDEOS, len(videos))
        self.assertEqual(MAX_RECOMMENDED_VIDEOS, len({video.url for video in videos}))

    async def test_english_revolution_rejects_france_and_industrial_revolution(self) -> None:
        async def transport(*args):
            return {
                "items": [
                    search_item(
                        "franceVID01",
                        title="Cách mạng Tư sản Pháp và ảnh hưởng | Tóm tắt nhanh",
                        description="Lịch sử nước Pháp cuối thế kỷ XVIII.",
                    ),
                    search_item(
                        "industry001",
                        title="Tóm tắt nhanh 4 cuộc Cách mạng Công nghiệp",
                        description="Cuộc cách mạng đầu tiên bắt đầu ở Anh.",
                    ),
                    search_item(
                        "england0001",
                        title="Cách mạng tư sản Anh thế kỷ XVII",
                        description="Nguyên nhân, diễn biến và ý nghĩa.",
                    ),
                    search_item(
                        "britempire1",
                        title="Lịch sử Đế quốc Anh | Tóm tắt nhanh",
                        description="Khái quát lịch sử nước Anh.",
                    ),
                ]
            }

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Nguyên nhân Cách mạng tư sản Anh là gì?",
            topics=["Cách mạng tư sản Anh thế kỷ XVII"],
        )

        ids = [video.url.rsplit("=", 1)[-1] for video in videos]
        self.assertEqual(["england0001"], ids)
        self.assertNotIn("franceVID01", ids)
        self.assertNotIn("industry001", ids)

    async def test_same_country_context_is_used_only_when_no_exact_event_exists(self) -> None:
        async def transport(*args):
            return {
                "items": [
                    search_item(
                        "franceVID01",
                        title="Cách mạng Tư sản Pháp và ảnh hưởng",
                        description="Lịch sử nước Pháp cuối thế kỷ XVIII.",
                    ),
                    search_item(
                        "industry001",
                        title="Cách mạng Công nghiệp lần thứ nhất",
                        description="Khởi đầu tại nước Anh.",
                    ),
                    search_item(
                        "britempire1",
                        title="Lịch sử Đế quốc Anh | Tóm tắt nhanh",
                        description="Khái quát lịch sử nước Anh.",
                    ),
                ]
            }

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Nguyên nhân Cách mạng tư sản Anh là gì?",
            topics=["Cách mạng tư sản Anh thế kỷ XVII"],
        )

        self.assertEqual(
            ["britempire1"],
            [video.url.rsplit("=", 1)[-1] for video in videos],
        )

    async def test_no_outside_channel_fallback_for_english_revolution(self) -> None:
        calls = 0

        async def transport(*args):
            nonlocal calls
            calls += 1
            return {"items": []}

        service = YouTubeVideoRecommender("key", transport=transport)
        videos = await service.recommend(
            question="Vì sao Cách mạng tư sản Anh bùng nổ?",
            topics=["Cách mạng tư sản Anh thế kỷ XVII"],
        )

        self.assertEqual(3, calls)
        self.assertEqual([], videos)

    def test_api_key_is_hidden_from_settings_repr(self) -> None:
        value = repr(WebSettings(youtube_api_key="top-secret"))
        self.assertNotIn("top-secret", value)


class YouTubeVideoApiIntegrationTests(unittest.TestCase):
    @staticmethod
    def _settings() -> WebSettings:
        return WebSettings(
            chatgpt_api_key=None,
            youtube_api_key=None,
            enable_web_search=False,
            rate_limit_requests=100,
        )

    def test_api_uses_only_provider_video_and_discards_ai_video(self) -> None:
        provider_url = "https://www.youtube.com/watch?v=abcDEF12345"

        class FakeRecommender:
            provider_version = "fake-youtube-v1"

            async def recommend(self, **kwargs):
                return [
                    Video(
                        title="Cách mạng công nghiệp",
                        url=provider_url,
                        publisher="EZ Sử",
                        relevance="Đúng chủ đề bài học.",
                        label="event",
                    )
                ]

        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=FakeAI(generated_lesson()),
            settings=self._settings(),
            video_recommender=FakeRecommender(),
        )
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/questions/ask",
            json={"question": "Cách mạng công nghiệp bắt đầu ở đâu?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([provider_url], [item["url"] for item in response.json()["videos"]])
        self.assertNotIn(YOUTUBE_URL, response.text)

    def test_video_lookup_runs_while_ai_is_generating(self) -> None:
        events: list[str] = []

        class SlowAI(FakeAI):
            async def generate(self, question, matches):
                events.append("ai-start")
                await asyncio.sleep(0.04)
                events.append("ai-end")
                return await super().generate(question, matches)

        class ConcurrentRecommender:
            provider_version = "concurrent-test-v1"

            async def recommend(self, **kwargs):
                events.append("video-start")
                await asyncio.sleep(0.01)
                events.append("video-end")
                return []

        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=SlowAI(),
            settings=self._settings(),
            video_recommender=ConcurrentRecommender(),
        )
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/questions/ask",
            json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertLess(events.index("video-start"), events.index("ai-end"))

    def test_missing_key_discards_ai_video_without_calling_network(self) -> None:
        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=FakeAI(),
            settings=self._settings(),
        )

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/questions/ask",
            json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([], response.json()["videos"])

    def test_provider_error_does_not_break_lesson_and_fails_closed(self) -> None:
        class BrokenRecommender:
            provider_version = "broken"

            async def recommend(self, **kwargs):
                raise RuntimeError("broken API")

        app = create_app(
            retrieval_service=FakeRetrieval(),
            ai_service=FakeAI(),
            settings=self._settings(),
            video_recommender=BrokenRecommender(),
        )
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/questions/ask",
            json={"question": "Cách mạng tư sản Anh bùng nổ năm nào?"},
        )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual([], response.json()["videos"])


if __name__ == "__main__":
    unittest.main()
