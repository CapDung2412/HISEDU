from __future__ import annotations

import ipaddress
from datetime import date
from io import BytesIO
from urllib.parse import parse_qs, urlparse

from PIL import Image, UnidentifiedImageError
from hisedu.dataset import is_textbook_source_name, textbook_source_metadata

from .errors import InvalidImageError
from .schemas import GeneratedLesson, GeneratedSource, Source, Video


TRUSTED_EXACT_HOSTS = {
    "wikipedia.org",
    "vi.wikipedia.org",
    "tuoitre.vn",
    "muctim.tuoitre.vn",
    "nhandan.vn",
    "vtv.vn",
    "htv.vn",
    "www.htv.vn",
    "htv.com.vn",
    "www.htv.com.vn",
    "vietnamplus.vn",
    "baotanglichsu.vn",
    "hanhtrangso.nxbgd.vn",
    "nxbgd.vn",
}
TRUSTED_SUFFIXES = (
    ".gov.vn",
    ".edu.vn",
    ".wikipedia.org",
    ".vtv.vn",
    ".htv.vn",
    ".htv.com.vn",
)
VIDEO_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vtv.vn",
    "vtvgo.vn",
    "www.vtvgo.vn",
    "htv.vn",
    "www.htv.vn",
    "htv.com.vn",
    "www.htv.com.vn",
}
VIDEO_HOST_SUFFIXES = (".vtv.vn", ".htv.vn", ".htv.com.vn")
MIME_TO_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
KNOWN_PUBLISHERS = {
    "vi.wikipedia.org": "Wikipedia tiếng Việt",
    "tuoitre.vn": "Tuổi Trẻ",
    "muctim.tuoitre.vn": "Mực Tím",
    "nhandan.vn": "Nhân Dân",
    "vtv.vn": "VTV",
    "htv.vn": "HTV",
    "www.htv.vn": "HTV",
    "htv.com.vn": "HTV",
    "www.htv.com.vn": "HTV",
    "vtvgo.vn": "VTVgo",
    "www.vtvgo.vn": "VTVgo",
    "vietnamplus.vn": "VietnamPlus",
    "baotanglichsu.vn": "Bảo tàng Lịch sử Quốc gia",
    "hanhtrangso.nxbgd.vn": "Nhà xuất bản Giáo dục Việt Nam",
    "youtube.com": "YouTube",
    "www.youtube.com": "YouTube",
    "youtu.be": "YouTube",
}


def _is_direct_video_page(value: str, host: str) -> bool:
    parsed = urlparse(value)
    path = parsed.path.rstrip("/")
    if host == "youtu.be":
        return bool(path and path != "/")
    if host in {"youtube.com", "www.youtube.com"}:
        if path == "/watch":
            return bool(parse_qs(parsed.query).get("v", [""])[0])
        return path.startswith(("/shorts/", "/live/")) and len(path.split("/")) >= 3
    # Broadcaster homepages are not videos. Their direct video/article routes
    # must contain a non-root path.
    return bool(path) and (
        host in VIDEO_HOSTS or any(host.endswith(suffix) for suffix in VIDEO_HOST_SUFFIXES)
    )


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
            known_video_host = host in VIDEO_HOSTS or any(
                host.endswith(suffix) for suffix in VIDEO_HOST_SUFFIXES
            )
            return value if known_video_host and _is_direct_video_page(value, host) else None
        trusted = host in TRUSTED_EXACT_HOSTS or any(host.endswith(suffix) for suffix in TRUSTED_SUFFIXES)
        return value if trusted else None
    except (TypeError, ValueError):
        return None


def publisher_for_url(value: str) -> str:
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    if host.endswith(".vtv.vn"):
        return "VTV"
    if host.endswith((".htv.vn", ".htv.com.vn")):
        return "HTV"
    return KNOWN_PUBLISHERS.get(host, host or "Nguồn web")


def video_publisher_for_url(value: str, claimed_publisher: str) -> str:
    """Keep a searched YouTube uploader name; normalize official broadcaster sites."""
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    if host in {"youtube.com", "www.youtube.com", "youtu.be"}:
        claimed = " ".join(claimed_publisher.split())[:500]
        if claimed and claimed.casefold() not in {"youtube", "youtube.com", "youtu.be"}:
            return claimed
    return publisher_for_url(value)


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
        grade, book_series = textbook_source_metadata(fields)
        is_textbook = is_textbook_source_name(name)
        page_status = "verified" if page is not None else (
            "unverified" if is_textbook else "not_applicable"
        )
        # Never present an unverified textbook page as an SGK citation. It
        # remains a local HISEDU dataset source until exact page metadata exists.
        source_type = (
            "sgk"
            if is_textbook and page is not None and grade is not None and book_series
            else "dataset"
        )
        output.append(
            Source(
                id=f"S{index}",
                title=str(fields.get("lesson_title") or fields.get("question") or "Nguồn HISEDU")[:500],
                publisher=name[:500],
                type=source_type,
                url=safe_https_url(str(fields.get("source_url") or "")),
                grade=grade,
                book_series=book_series,
                page=page,
                page_status=page_status,
                locator=str(fields.get("source_locator") or "")[:500] or None,
                accessed_at=None,
                evidence_excerpt=str(fields.get("answer") or "")[:1_000] or None,
                review_status=str(fields.get("review_status") or "")[:500] or None,
                provenance_note=str(fields.get("provenance_note") or "")[:1_000] or None,
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
        source_type = raw.type
        grade = raw.grade
        book_series = raw.book_series
        page_status = raw.page_status
        evidence_excerpt = None
        review_status = None
        provenance_note = None
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
            evidence_excerpt = str(first.get("answer") or "")[:1_000] or None
            review_status = str(first.get("review_status") or "")[:500] or None
            provenance_note = str(first.get("provenance_note") or "")[:1_000] or None
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
            grade = None
            book_series = None
            page_status = "not_applicable"
        else:
            first = local_fields[0]
            is_textbook = is_textbook_source_name(
                str(first.get("source_name") or "")
            )
            grade, book_series = textbook_source_metadata(first)
            page_status = "verified" if page is not None else (
                "unverified" if is_textbook else "not_applicable"
            )
            source_type = (
                "sgk"
                if is_textbook
                and page is not None
                and grade is not None
                and book_series
                else "dataset"
            )
        sources.append(
            Source(
                id=raw.id,
                title=title,
                publisher=publisher,
                type=source_type,
                url=url,
                grade=grade,
                book_series=book_series,
                page=page,
                page_status=page_status,
                locator=locator,
                accessed_at=date.today().isoformat() if url else None,
                evidence_excerpt=evidence_excerpt,
                review_status=review_status,
                provenance_note=provenance_note,
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
                    update={
                        "url": url,
                        "publisher": video_publisher_for_url(url, raw_video.publisher),
                    }
                )
            )
            seen_video_urls.add(url)
    cleaned = lesson.model_copy(
        update={
            "answer": answer,
            "sources": [
                GeneratedSource(
                    **source.model_dump(include=set(GeneratedSource.model_fields))
                )
                for source in sources
            ],
            "quiz": quiz,
            "videos": videos,
        }
    )
    return cleaned, sources, videos
