from __future__ import annotations

import ipaddress
from datetime import date
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

from .errors import InvalidImageError
from .schemas import GeneratedLesson, GeneratedSource, Source, Video


TRUSTED_EXACT_HOSTS = {
    "wikipedia.org",
    "vi.wikipedia.org",
    "tuoitre.vn",
    "muctim.tuoitre.vn",
    "nhandan.vn",
    "vtv.vn",
    "vietnamplus.vn",
    "baotanglichsu.vn",
    "hanhtrangso.nxbgd.vn",
    "nxbgd.vn",
}
TRUSTED_SUFFIXES = (".gov.vn", ".edu.vn", ".wikipedia.org")
VIDEO_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vtv.vn",
    "vtvgo.vn",
    "www.vtvgo.vn",
}
MIME_TO_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
KNOWN_PUBLISHERS = {
    "vi.wikipedia.org": "Wikipedia tiếng Việt",
    "tuoitre.vn": "Tuổi Trẻ",
    "muctim.tuoitre.vn": "Mực Tím",
    "nhandan.vn": "Nhân Dân",
    "vtv.vn": "VTV",
    "vtvgo.vn": "VTVgo",
    "www.vtvgo.vn": "VTVgo",
    "vietnamplus.vn": "VietnamPlus",
    "baotanglichsu.vn": "Bảo tàng Lịch sử Quốc gia",
    "hanhtrangso.nxbgd.vn": "Nhà xuất bản Giáo dục Việt Nam",
    "youtube.com": "YouTube",
    "www.youtube.com": "YouTube",
    "youtu.be": "YouTube",
}


def safe_https_url(value: str | None, *, video: bool = False) -> str | None:
    if not value:
        return None
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (address.is_private or address.is_loopback or address.is_reserved):
            return None
        if video:
            return value if host in VIDEO_HOSTS else None
        trusted = host in TRUSTED_EXACT_HOSTS or any(host.endswith(suffix) for suffix in TRUSTED_SUFFIXES)
        return value if trusted else None
    except (TypeError, ValueError):
        return None


def publisher_for_url(value: str) -> str:
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    return KNOWN_PUBLISHERS.get(host, host or "Nguồn web")


def validate_image(data: bytes, claimed_mime: str, *, max_pixels: int) -> str:
    expected_format = MIME_TO_FORMAT.get((claimed_mime or "").lower())
    if expected_format is None:
        raise InvalidImageError()
    try:
        with Image.open(BytesIO(data)) as image:
            actual_format = image.format
            width, height = image.size
            frames = int(getattr(image, "n_frames", 1))
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError() from exc
    if (
        actual_format != expected_format
        or frames != 1
        or width <= 0
        or height <= 0
        or width * height > max_pixels
    ):
        raise InvalidImageError()
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError() from exc
    return claimed_mime.lower()


def _fallback_sources(matches: list[dict]) -> list[Source]:
    output: list[Source] = []
    for index, match in enumerate(matches[:5], start=1):
        fields = match.get("fields") or {}
        name = str(fields.get("source_name") or "Dữ liệu HISEDU")
        page = fields.get("source_page_number")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        source_type = "sgk" if "sách giáo khoa" in name.lower() or "sgk" in name.lower() else "dataset"
        output.append(
            Source(
                id=f"S{index}",
                title=str(fields.get("lesson_title") or fields.get("question") or "Nguồn HISEDU")[:500],
                publisher=name[:500],
                type=source_type,
                url=safe_https_url(str(fields.get("source_url") or "")),
                page=page,
                locator=str(fields.get("source_locator") or "")[:500] or None,
                accessed_at=None,
                supports=[str(fields.get("question") or "Kiến thức trong câu trả lời")[:500]],
            )
        )
    return output


def _matching_local_fields(raw: GeneratedSource, matches: list[dict]) -> list[dict]:
    """Tie an AI local-source claim to exact retrieval metadata, conservatively."""
    candidates: list[dict] = []
    for match in matches:
        fields = match.get("fields") or {}
        exact_markers = (
            raw.url and raw.url == fields.get("source_url"),
            raw.locator and raw.locator == fields.get("source_locator"),
            raw.title and raw.title == fields.get("lesson_title"),
        )
        if any(exact_markers):
            candidates.append(fields)
    return candidates


def sanitize_lesson(
    lesson: GeneratedLesson,
    matches: list[dict],
    *,
    returned_web_urls: set[str] | None = None,
) -> tuple[GeneratedLesson, list[Source], list[Video]]:
    """Remove unverifiable links/pages and repair dangling citation references."""
    returned_web_urls = returned_web_urls or set()
    sources: list[Source] = []
    seen_ids: set[str] = set()
    for raw in lesson.sources:
        if raw.id in seen_ids:
            continue
        url = safe_https_url(raw.url)
        local_fields = _matching_local_fields(raw, matches)
        title = raw.title
        publisher = raw.publisher
        if raw.type in {"dataset", "sgk"}:
            if not local_fields:
                # A local/SGK citation must resolve to an exact retrieved record;
                # otherwise even its title and publisher are unverified.
                continue
            known_urls = {
                clean
                for fields in local_fields
                if (clean := safe_https_url(str(fields.get("source_url") or "")))
            }
            if url not in known_urls:
                url = None
            first = local_fields[0]
            title = str(
                first.get("lesson_title")
                or first.get("question")
                or "Nguồn HISEDU"
            )[:500]
            publisher = str(first.get("source_name") or "Dữ liệu HISEDU")[:500]
        if raw.type not in {"dataset", "sgk"}:
            if url not in returned_web_urls:
                continue
            publisher = publisher_for_url(url)
        known_pages: set[int] = set()
        for fields in local_fields:
            value = fields.get("source_page_number")
            try:
                if value is not None:
                    known_pages.add(int(value))
            except (TypeError, ValueError):
                continue
        known_locators = {
            str(fields["source_locator"])
            for fields in local_fields
            if fields.get("source_locator")
        }
        page = raw.page if raw.page in known_pages else None
        locator = raw.locator if raw.locator in known_locators else None
        if raw.type not in {"dataset", "sgk"}:
            page = None
            locator = None
        sources.append(
            Source(
                id=raw.id,
                title=title,
                publisher=publisher,
                type=raw.type,
                url=url,
                page=page,
                locator=locator,
                accessed_at=date.today().isoformat() if url else None,
                supports=raw.supports,
            )
        )
        seen_ids.add(raw.id)
    if not sources:
        sources = _fallback_sources(matches)
    valid_source_ids = {source.id for source in sources}
    answer = lesson.answer.model_copy(deep=True)
    answer.citation_ids = [value for value in answer.citation_ids if value in valid_source_ids]
    for section in answer.sections:
        section.citation_ids = [value for value in section.citation_ids if value in valid_source_ids]
    quiz = [item.model_copy(deep=True) for item in lesson.quiz]
    for question in quiz:
        question.source_ids = [value for value in question.source_ids if value in valid_source_ids]
    videos: list[Video] = []
    seen_video_urls: set[str] = set()
    for raw_video in lesson.videos:
        url = safe_https_url(raw_video.url, video=True)
        if url and url in returned_web_urls and url not in seen_video_urls:
            videos.append(
                raw_video.model_copy(
                    update={"url": url, "publisher": publisher_for_url(url)}
                )
            )
            seen_video_urls.add(url)
    cleaned = lesson.model_copy(
        update={
            "answer": answer,
            "sources": [GeneratedSource(**source.model_dump()) for source in sources],
            "quiz": quiz,
            "videos": videos,
        }
    )
    return cleaned, sources, videos
