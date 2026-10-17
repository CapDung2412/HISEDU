from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .cache import TTLCache
from .schemas import Video


logger = logging.getLogger("uvicorn.error")

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
MAX_RECOMMENDED_VIDEOS = 6
TARGET_RECOMMENDED_VIDEOS = 3
MAX_TARGETED_CHANNEL_SEARCHES = 2

# IDs are pinned so a look-alike channel name can never enter the result set.
# The HTV entry is the official HTV Tin Tức channel.
ALLOWED_YOUTUBE_CHANNELS: dict[str, str] = {
    "UCpaQwg8wZRAkFJe3mo1VKSA": "EZ Sử",  # @ezsu
    "UCZYKmEA2iQOSbyKc6xj5Vfw": "HTV Tin Tức",  # @HTVTinTuc
    "UCabsTV34JwALXKGMqHpvUiA": "VTV24",  # @VTV24
    "UCJDueHzfSEXmgMhmKIa9esQ": "Sử Lược - Tóm Tắt Lịch Sử",  # @suluoc
    "UCpXhSnIKT-oxLAU4B-76GRg": "Dòng Máu Việt",  # @dongmauviet
}

_EZ_SU_CHANNEL_ID = "UCpaQwg8wZRAkFJe3mo1VKSA"
_VTV24_CHANNEL_ID = "UCabsTV34JwALXKGMqHpvUiA"
_SU_LUOC_CHANNEL_ID = "UCJDueHzfSEXmgMhmKIa9esQ"
_DONG_MAU_VIET_CHANNEL_ID = "UCpXhSnIKT-oxLAU4B-76GRg"

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SPACE_RE = re.compile(r"\s+")
_UNICODE_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)
_TOPIC_SPLIT_RE = re.compile(r"\s*(?:;|\||—)\s*|\s+và\s+", re.IGNORECASE)
_STOP_WORDS = {
    "ai",
    "bai",
    "cac",
    "cau",
    "cho",
    "co",
    "cua",
    "da",
    "de",
    "den",
    "duoc",
    "gi",
    "hay",
    "khi",
    "la",
    "lich",
    "mot",
    "nao",
    "nay",
    "nhung",
    "noi",
    "su",
    "tai",
    "theo",
    "thi",
    "tom",
    "trong",
    "tu",
    "va",
    "ve",
    "video",
    "voi",
}

# Generic lesson words must not make two different revolutions look relevant.
# At least one non-generic token must occur in the video title.
_GENERIC_TOPIC_TOKENS = {
    "cach",
    "mang",
    "cuoc",
    "giai",
    "gioi",
    "ket",
    "lich",
    "nghia",
    "nguyen",
    "nhan",
    "noi",
    "phan",
    "qua",
    "san",
    "su",
    "tat",
    "the",
    "tich",
    "tom",
    "trinh",
}

_ENTITY_ALIASES = {
    # Ambiguous standalone Vietnamese words ("anh", "pháp") are handled with
    # historical context in ``_entities``. This prevents "anh hùng" and
    # "biện pháp" from being mistaken for England and France.
    "anh": ("nước anh", "nuoc anh", "england", "britain", "united kingdom"),
    "phap": ("nước pháp", "nuoc phap", "france", "napoleon"),
    "hoa-ky": (
        "hoa kỳ",
        "hoa ky",
        "nước mỹ",
        "nuoc my",
        "mỹ",
        "my",
        "13 thuộc địa",
        "13 thuoc dia",
        "united states",
    ),
    "nga": ("nga", "nước nga", "nuoc nga", "liên xô", "lien xo", "russia", "soviet"),
    "nhat-ban": ("nhật bản", "nhat ban", "minh trị", "minh tri", "japan"),
    "trung-quoc": ("trung quốc", "trung quoc", "nhà thanh", "nha thanh", "china"),
    "an-do": ("ấn độ", "an do", "india"),
    "duc": ("nước đức", "nuoc duc", "đế quốc đức", "de quoc duc", "germany"),
    "viet-nam": ("việt nam", "viet nam", "đại việt", "dai viet", "đại nam", "dai nam"),
}

_EVENT_ALIASES = {
    "bourgeois-revolution": (
        "cách mạng tư sản",
        "cach mang tu san",
        "cách mạng anh",
        "cach mang anh",
        "nội chiến anh",
        "noi chien anh",
        "bourgeois revolution",
        "english revolution",
        "english civil war",
    ),
    "industrial-revolution": ("cách mạng công nghiệp", "cach mang cong nghiep", "industrial revolution"),
    "october-revolution": ("cách mạng tháng mười", "cach mang thang muoi", "october revolution"),
    "august-revolution": ("cách mạng tháng tám", "cach mang thang tam", "august revolution"),
}


@dataclass(frozen=True, slots=True)
class _CuratedVideo:
    """A manually verified fallback for a curriculum topic with poor API recall."""

    video_id: str
    channel_id: str
    title: str
    entities: frozenset[str]
    events: frozenset[str]
    relevance: str


# YouTube search does not always surface an exact result from the five preferred
# channels. These entries are reviewed, direct videos from institutional
# education/broadcast channels and are used only for an exact entity + event.
_CURATED_VIDEOS: tuple[_CuratedVideo, ...] = (
    _CuratedVideo(
        video_id="t5fahfNM67w",
        channel_id=_EZ_SU_CHANNEL_ID,
        title="Cách mạng Tư sản Pháp | Tóm tắt nhanh lịch sử thế giới - EZ Sử",
        entities=frozenset({"phap"}),
        events=frozenset({"bourgeois-revolution"}),
        relevance=(
            "Video của EZ Sử trình bày trực tiếp Cách mạng tư sản Pháp, phù hợp để "
            "ôn lại nguyên nhân, diễn biến, kết quả và ý nghĩa của sự kiện."
        ),
    ),
)

YouTubeTransport = Callable[
    [str, Mapping[str, str], Mapping[str, str], float],
    Awaitable[Mapping[str, Any]],
]


def normalize_vietnamese(value: str) -> str:
    """Return stable, accent-insensitive Vietnamese text for cache/ranking."""
    text = unicodedata.normalize("NFD", str(value).casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d")
    return " ".join(_TOKEN_RE.findall(text))


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_vietnamese(value).split()
        if (len(token) >= 3 or token.isdigit()) and token not in _STOP_WORDS
    }


def _entities(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFC", str(value).casefold())
    normalized = f" {' '.join(_UNICODE_WORD_RE.sub(' ', normalized).split())} "
    entities = {
        entity
        for entity, aliases in _ENTITY_ALIASES.items()
        if any(f" {alias} " in normalized for alias in aliases)
    }
    normalized_ascii = f" {normalize_vietnamese(value)} "
    england_context = (
        " cach mang anh ",
        " tu san anh ",
        " de quoc anh ",
        " thuoc dia anh ",
        " kinh te anh ",
        " xa hoi anh ",
        " quoc hoi anh ",
        " quan chu anh ",
        " o anh ",
        " cua anh ",
        " anh la nuoc ",
        " anh the ky ",
        " anh truoc ",
        " anh sau ",
    )
    france_context = (
        " cach mang phap ",
        " tu san phap ",
        " xa hoi phap ",
        " nhan dan phap ",
        " vua phap ",
        " de quoc phap ",
        " thuc dan phap ",
        " quan phap ",
        " o phap ",
        " cua phap ",
        " chong phap ",
        " phap xam ",
        " phap thuoc ",
        " phap truoc ",
        " phap sau ",
        " phap cuoi ",
        " phap nam ",
    )
    if any(phrase in normalized_ascii for phrase in england_context):
        entities.add("anh")
    if any(phrase in normalized_ascii for phrase in france_context):
        entities.add("phap")
    return entities


def _events(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFC", str(value).casefold())
    normalized = f" {' '.join(_UNICODE_WORD_RE.sub(' ', normalized).split())} "
    return {
        event
        for event, aliases in _EVENT_ALIASES.items()
        if any(f" {alias} " in normalized for alias in aliases)
    }


def _clean_text(value: object, *, limit: int) -> str:
    return _SPACE_RE.sub(" ", html.unescape(str(value))).strip()[:limit]


def _topic_subject(question: str, topics: Iterable[str]) -> str:
    """Choose one concise, question-aligned topic for search and ranking.

    Retrieval metadata often contains the student's full question before the
    lesson title. Ranking all candidates avoids blindly repeating a very narrow
    interrogative query, while clause splitting prevents compound lesson titles
    (for example England *and* the thirteen colonies) from widening the search.
    """
    cleaned_question = _clean_text(question, limit=220)
    question_tokens = _meaningful_tokens(cleaned_question)
    question_specific = question_tokens - _GENERIC_TOPIC_TOKENS
    question_entities = _entities(cleaned_question)
    question_events = _events(cleaned_question)
    normalized_question = normalize_vietnamese(cleaned_question)
    ranked: list[tuple[int, int, int, str]] = []
    order = 0
    for raw in topics:
        candidate = _clean_text(raw, limit=160)
        if not candidate:
            continue
        clauses = [candidate, *(_TOPIC_SPLIT_RE.split(candidate))]
        seen_clauses: set[str] = set()
        for clause in clauses:
            clause = _clean_text(clause, limit=160)
            normalized_clause = normalize_vietnamese(clause)
            if (
                not clause
                or normalized_clause == normalized_question
                or normalized_clause in seen_clauses
            ):
                continue
            seen_clauses.add(normalized_clause)
            candidate_tokens = _meaningful_tokens(clause)
            candidate_entities = _entities(clause)
            candidate_events = _events(clause)
            if question_entities:
                if not candidate_entities or question_entities.isdisjoint(
                    candidate_entities
                ):
                    continue
                # Prefer the clause that stays inside the student's scope.
                if candidate_entities - question_entities:
                    continue
            if (
                question_events
                and candidate_events
                and question_events.isdisjoint(candidate_events)
            ):
                continue
            token_overlap = len(question_tokens & candidate_tokens)
            specific_overlap = len(question_specific & candidate_tokens)
            event_overlap = len(question_events & candidate_events)
            entity_overlap = len(question_entities & candidate_entities)
            supplies_event_context = bool(
                question_entities and entity_overlap and candidate_events
            )
            if not (
                token_overlap >= 2
                or event_overlap
                or supplies_event_context
            ):
                continue
            score = (
                14 * event_overlap
                + 10 * entity_overlap
                + 4 * specific_overlap
                + 2 * token_overlap
                + 3 * int(supplies_event_context)
            )
            # On equal relevance, a short clause is a safer YouTube query.
            ranked.append((score, -len(candidate_tokens), -order, clause))
            order += 1
    if ranked:
        ranked.sort(reverse=True)
        return ranked[0][3]
    return cleaned_question


def _topic_query(question: str, topics: Iterable[str]) -> str:
    # One compact subject materially improves recall over concatenating the
    # full question, mind-map title and node labels into an AND-like query.
    # Channel names are deliberately omitted: YouTube does not treat ``|`` as
    # a reliable channel filter. Results are securely allowlisted by channel
    # ID after retrieval instead.
    return _topic_subject(question, topics)


def _infer_label(value: str) -> str:
    normalized = f" {normalize_vietnamese(value)} "
    if any(term in normalized for term in (" nguyen nhan ", " vi sao ", " boi canh ")):
        return "cause"
    if any(term in normalized for term in (" ket qua ", " hau qua ")):
        return "result"
    if any(
        term in normalized
        for term in (" y nghia ", " vai tro ", " tac dong ", " anh huong ")
    ):
        return "meaning"
    return "event"


def _curated_videos(
    subject: str,
    *,
    limit: int,
    allowed_channels: Mapping[str, str],
) -> list[Video]:
    query_entities = _entities(subject)
    query_events = _events(subject)
    selected: list[Video] = []
    for item in _CURATED_VIDEOS:
        publisher = allowed_channels.get(item.channel_id)
        if not publisher:
            continue
        if not item.entities.issubset(query_entities):
            continue
        if not item.events.issubset(query_events):
            continue
        selected.append(
            Video(
                title=item.title,
                url=f"https://www.youtube.com/watch?v={item.video_id}",
                publisher=publisher,
                relevance=item.relevance,
                label=_infer_label(subject),  # type: ignore[arg-type]
            )
        )
        if len(selected) >= min(limit, MAX_RECOMMENDED_VIDEOS):
            break
    return selected


def _has_topic_signal(subject: str) -> bool:
    tokens = _meaningful_tokens(subject)
    specific = tokens - _GENERIC_TOPIC_TOKENS
    return bool(specific or _entities(subject) or _events(subject))


def _priority_channel_ids(
    subject: str,
    allowed_channels: Mapping[str, str],
) -> list[str]:
    """Return specialist channels ordered for a sparse-result backfill."""
    normalized = f" {normalize_vietnamese(subject)} "
    vietnamese_markers = (
        " viet nam ",
        " tay son ",
        " quang trung ",
        " nguyen hue ",
        " hai ba trung ",
        " ngo quyen ",
        " dien bien ",
        " khang chien ",
        " nha ly ",
        " nha tran ",
        " nha le ",
        " nha nguyen ",
    )
    if "viet-nam" in _entities(subject) or any(
        marker in normalized for marker in vietnamese_markers
    ):
        preferred = (
            _DONG_MAU_VIET_CHANNEL_ID,
            _SU_LUOC_CHANNEL_ID,
            _VTV24_CHANNEL_ID,
        )
    else:
        preferred = (
            _EZ_SU_CHANNEL_ID,
            _SU_LUOC_CHANNEL_ID,
            _VTV24_CHANNEL_ID,
        )
    selected = [channel_id for channel_id in preferred if channel_id in allowed_channels]
    return selected


def _merge_videos(*groups: Iterable[Video], limit: int) -> list[Video]:
    merged: list[Video] = []
    seen_urls: set[str] = set()
    for group in groups:
        for video in group:
            if video.url in seen_urls:
                continue
            seen_urls.add(video.url)
            merged.append(video)
            if len(merged) >= min(limit, MAX_RECOMMENDED_VIDEOS):
                return merged
    return merged


def _combine_search_payloads(
    payloads: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any]:
    items: list[Any] = []
    for payload in payloads:
        raw_items = payload.get("items")
        if isinstance(raw_items, list):
            items.extend(raw_items)
    return {"items": items}


async def _httpx_transport(
    url: str,
    params: Mapping[str, str],
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> Mapping[str, Any]:
    import httpx

    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.get(
            url, params=dict(params), headers=dict(headers)
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("YouTube API returned a non-object response")
    return payload


class VideoRecommendationService(Protocol):
    @property
    def provider_version(self) -> str: ...

    async def recommend(
        self,
        *,
        question: str,
        answer: str = "",
        topics: Iterable[str] = (),
        limit: int = MAX_RECOMMENDED_VIDEOS,
    ) -> list[Video]: ...


class YouTubeVideoRecommender:
    """Quota-conscious YouTube search with an immutable channel allowlist."""

    def __init__(
        self,
        api_key: str | None,
        *,
        timeout_seconds: float = 5.0,
        cache_ttl_seconds: int = 86_400,
        allowed_channels: Mapping[str, str] | None = None,
        transport: YouTubeTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self._api_key = (api_key or "").strip()
        self._timeout_seconds = float(timeout_seconds)
        self._allowed_channels = dict(
            ALLOWED_YOUTUBE_CHANNELS if allowed_channels is None else allowed_channels
        )
        self._transport = transport or _httpx_transport
        self._cache: TTLCache[list[Video]] = TTLCache(
            ttl_seconds=cache_ttl_seconds, max_items=256
        )
        version_material = "youtube-v7-ranked-allowlist-backfill\n" + "\n".join(
            [
                *(
                    f"{channel_id}:{title}"
                    for channel_id, title in sorted(self._allowed_channels.items())
                ),
                *(
                    f"curated:{item.channel_id}:{item.video_id}:{item.title}"
                    for item in _CURATED_VIDEOS
                ),
            ]
        )
        self._provider_version = hashlib.sha256(
            version_material.encode("utf-8")
        ).hexdigest()[:16]

    @property
    def provider_version(self) -> str:
        return self._provider_version

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _parse_items(
        self,
        payload: Mapping[str, Any],
        *,
        subject: str,
        limit: int,
    ) -> list[Video]:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            return []
        query_tokens = _meaningful_tokens(subject)
        query_specific = query_tokens - _GENERIC_TOPIC_TOKENS
        query_entities = _entities(subject)
        query_events = _events(subject)
        strong: list[tuple[int, int, Video]] = []
        contextual: list[tuple[int, int, Video]] = []
        seen_ids: set[str] = set()
        for position, raw in enumerate(raw_items):
            if not isinstance(raw, Mapping):
                continue
            identity = raw.get("id")
            snippet = raw.get("snippet")
            if not isinstance(identity, Mapping) or not isinstance(snippet, Mapping):
                continue
            video_id = str(identity.get("videoId") or "")
            channel_id = str(snippet.get("channelId") or "")
            publisher = self._allowed_channels.get(channel_id)
            if (
                identity.get("kind") != "youtube#video"
                or not publisher
                or video_id in seen_ids
                or not _VIDEO_ID_RE.fullmatch(video_id)
            ):
                continue
            title = _clean_text(snippet.get("title") or "", limit=500)
            description = _clean_text(snippet.get("description") or "", limit=2_000)
            if not title:
                continue
            title_tokens = _meaningful_tokens(title)
            candidate_tokens = _meaningful_tokens(f"{title} {description}")
            title_entities = _entities(title)
            candidate_entities = _entities(f"{title} {description}")
            candidate_events = _events(f"{title} {description}")
            # Country/person scope is a hard gate. A video about France must
            # never satisfy a question about England, even if both titles say
            # "cách mạng tư sản". All detected foreign entities are rejected.
            if query_entities:
                if title_entities:
                    if not (query_entities & title_entities):
                        continue
                    # An exact title remains valid when its description merely
                    # compares the event with another country.
                    if title_entities - query_entities:
                        continue
                elif (
                    not (query_entities & candidate_entities)
                    or bool(candidate_entities - query_entities)
                ):
                    continue
            # Likewise, do not substitute the Industrial Revolution for a
            # bourgeois revolution merely because both happened in England.
            if query_events and candidate_events and query_events.isdisjoint(candidate_events):
                continue
            specific_title_overlap = len(query_specific & title_tokens)
            specific_any_overlap = len(query_specific & candidate_tokens)
            title_overlap = len(query_tokens & title_tokens)
            description_overlap = len(query_tokens & candidate_tokens)
            event_match = bool(query_events & candidate_events)
            entity_match = bool(query_entities & candidate_entities)
            title_entity_match = bool(query_entities & title_entities)
            numeric_title_match = any(
                token.isdigit() and token in title_tokens for token in query_tokens
            )
            is_strong = (
                event_match
                or title_overlap >= 2
                or specific_title_overlap >= 2
                or numeric_title_match
            )
            # A same-country video with at least one distinctive term is a
            # safe contextual fallback when YouTube has no exact-title hit.
            is_contextual = title_entity_match and (
                specific_title_overlap >= 1 or specific_any_overlap >= 2
            )
            if not is_strong and not is_contextual:
                continue
            score = (
                12 * int(event_match)
                + 8 * int(entity_match)
                + 4 * specific_title_overlap
                + 2 * title_overlap
                + specific_any_overlap
                + description_overlap
            )
            seen_ids.add(video_id)
            label = _infer_label(f"{subject} {title}")
            relevance_subject = _clean_text(subject, limit=180)
            if is_strong:
                relevance = (
                    f"Video của {publisher} khớp với chủ đề “{relevance_subject}”."
                    if relevance_subject
                    else f"Video lịch sử do {publisher} xuất bản."
                )
            else:
                relevance = (
                    f"Tư liệu bối cảnh cùng quốc gia cho chủ đề “{relevance_subject}”; "
                    "dùng để hiểu thêm, không thay thế nội dung chính."
                )
            target = strong if is_strong else contextual
            target.append(
                (
                    score,
                    position,
                    Video(
                        title=title,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        publisher=publisher,
                        relevance=relevance,
                        label=label,  # type: ignore[arg-type]
                    ),
                )
            )
        strong.sort(key=lambda item: (-item[0], item[1]))
        contextual.sort(key=lambda item: (-item[0], item[1]))
        # Exact matches are intentionally never padded with merely same-country
        # documentaries. When there is no exact hit, expose at most two vetted
        # contextual results instead of leaving the lesson needlessly empty.
        selected = strong if strong else contextual[:2]
        return [item[2] for item in selected[: min(limit, MAX_RECOMMENDED_VIDEOS)]]

    async def recommend(
        self,
        *,
        question: str,
        answer: str = "",
        topics: Iterable[str] = (),
        limit: int = MAX_RECOMMENDED_VIDEOS,
    ) -> list[Video]:
        del answer  # Search concise topic text, never long generated prose.
        if limit <= 0 or not self._api_key or not self._allowed_channels:
            return []
        topic_values = tuple(str(value) for value in topics)
        subject = _topic_subject(question, topic_values)
        query = _topic_query(question, topic_values)
        if not query or not _has_topic_signal(subject):
            return []
        requested_limit = min(limit, MAX_RECOMMENDED_VIDEOS)
        cache_key = hashlib.sha256(
            f"{normalize_vietnamese(query)}\nlimit={requested_limit}".encode("utf-8")
        ).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached[:requested_limit]
        params: dict[str, str] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": "50",
            "order": "relevance",
            "relevanceLanguage": "vi",
            "regionCode": "VN",
            "safeSearch": "strict",
            "videoEmbeddable": "true",
            "fields": "items(id(kind,videoId),snippet(channelId,title,description))",
        }
        curated = _curated_videos(
            subject,
            limit=limit,
            allowed_channels=self._allowed_channels,
        )
        try:
            primary_payload = await self._transport(
                YOUTUBE_SEARCH_URL,
                params,
                {"X-Goog-Api-Key": self._api_key},
                self._timeout_seconds,
            )
        except Exception as exc:
            # Never log the exception text: transports may include sensitive
            # request details in exception messages.
            logger.warning("hisedu_youtube_error error_type=%s", type(exc).__name__)
            videos = curated
        else:
            payloads: list[Mapping[str, Any]] = [primary_payload]
            primary_videos = self._parse_items(
                primary_payload,
                subject=subject,
                limit=limit,
            )
            initial = _merge_videos(curated, primary_videos, limit=limit)
            target_count = min(
                max(0, limit),
                TARGET_RECOMMENDED_VIDEOS,
                MAX_RECOMMENDED_VIDEOS,
            )
            if len(initial) < target_count:
                represented_publishers = {video.publisher for video in initial}
                fallback_channels = [
                    channel_id
                    for channel_id in _priority_channel_ids(
                        subject, self._allowed_channels
                    )
                    if self._allowed_channels[channel_id]
                    not in represented_publishers
                ][:MAX_TARGETED_CHANNEL_SEARCHES]

                async def search_channel(channel_id: str) -> Mapping[str, Any]:
                    targeted_params = dict(params)
                    targeted_params.update(
                        {"channelId": channel_id, "maxResults": "12"}
                    )
                    return await self._transport(
                        YOUTUBE_SEARCH_URL,
                        targeted_params,
                        {"X-Goog-Api-Key": self._api_key},
                        self._timeout_seconds,
                    )

                fallback_results = await asyncio.gather(
                    *(search_channel(channel_id) for channel_id in fallback_channels),
                    return_exceptions=True,
                )
                for fallback_result in fallback_results:
                    if isinstance(fallback_result, BaseException):
                        logger.warning(
                            "hisedu_youtube_backfill_error error_type=%s",
                            type(fallback_result).__name__,
                        )
                        continue
                    payloads.append(fallback_result)
            ranked = self._parse_items(
                _combine_search_payloads(payloads),
                subject=subject,
                limit=limit,
            )
            videos = _merge_videos(curated, ranked, limit=limit)
        self._cache.set(cache_key, videos)
        return videos[:requested_limit]
