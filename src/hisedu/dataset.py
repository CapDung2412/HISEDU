from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


class DatasetError(ValueError):
    """Raised when a dataset record violates a cross-file invariant."""


def _reject_json_constant(value: str) -> Any:
    raise DatasetError(f"Non-standard JSON constant: {value}")


def _reject_duplicate_json_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise DatasetError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip()


def is_textbook_source_name(value: str) -> bool:
    """Return whether a source explicitly identifies itself as a textbook."""
    folded = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode().lower()
    return "sgk" in folded or "sach giao khoa" in folded


def textbook_source_metadata(
    source: Mapping[str, Any],
) -> tuple[int | None, str | None]:
    """Read grade/book series from explicit metadata, then from the verified title.

    Older HISEDU records encode these two values in ``source.name``. Parsing that
    field is safe because the returned values still originate in dataset metadata;
    no model-generated value is accepted here.
    """
    name = normalize_text(str(source.get("name") or source.get("source_name") or ""))
    if not is_textbook_source_name(name):
        return None, None

    raw_grade = source.get("grade", source.get("source_grade"))
    grade: int | None = None
    if not isinstance(raw_grade, bool):
        try:
            candidate = int(raw_grade) if raw_grade is not None else None
            grade = candidate if candidate is not None and 1 <= candidate <= 12 else None
        except (TypeError, ValueError):
            pass

    raw_series = source.get("book_series", source.get("source_book_series"))
    series = normalize_text(str(raw_series)) if raw_series else None

    # Example: "SGK Lịch sử và Địa lí 8 - Kết nối tri thức ... (Phần Lịch sử)".
    title_match = re.search(
        r"\b(?P<grade>[1-9]|1[0-2])\s*[-\u2013\u2014]\s*(?P<series>[^()]+)",
        name,
    )
    if title_match:
        if grade is None:
            grade = int(title_match.group("grade"))
        if not series:
            series = normalize_text(title_match.group("series"))
    return grade, series


def source_page_number(source: Mapping[str, Any]) -> int | None:
    """Return a valid page carried by source metadata, never a guessed page."""
    raw_page = source.get("page_number", source.get("source_page_number"))
    if raw_page is None or isinstance(raw_page, bool):
        return None
    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return None
    return page if 1 <= page <= 10_000 else None


def question_body(text: str) -> str:
    return normalize_text(re.split(r"\r?\n---\s*\r?\n", text, maxsplit=1)[0])


def chunks(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for start in range(0, len(values), size):
        yield values[start : start + size]


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    record_id: str
    chunk_id: str
    question: str
    answer: str
    answer_type: str
    difficulty: str
    title: str
    dataset_name: str
    dataset_version: str
    chapter: dict[str, Any]
    lesson: dict[str, Any]
    keywords: tuple[str, ...]
    source: dict[str, Any]
    review_status: str
    provenance_note: str
    source_txt: str
    source_json: str
    content_checksum: str

    @property
    def search_text(self) -> str:
        # CLIP input stays short; lesson context and answer remain retrievable metadata.
        return self.question

    def pinecone_document(
        self, embedding: Sequence[float], *, embedding_model: str
    ) -> dict[str, Any]:
        vector = [float(value) for value in embedding]
        document: dict[str, Any] = {
            "_id": self.chunk_id,
            "embedding": vector,
            "record_id": self.record_id,
            "chunk_id": self.chunk_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "title": self.title,
            "question": self.question,
            "answer": self.answer,
            "answer_type": self.answer_type,
            "difficulty": self.difficulty,
            "chapter_id": str(self.chapter["id"]),
            "chapter_folder": str(self.chapter["folder"]),
            "chapter_title": str(self.chapter["title"]),
            "lesson_id": str(self.lesson["id"]),
            "lesson_folder": str(self.lesson["folder"]),
            "lesson_title": str(self.lesson["title"]),
            "keywords": list(self.keywords),
            "source_name": str(self.source["name"]),
            "source_url": str(self.source["url"]),
            "source_locator": str(self.source["locator"]),
            "review_status": self.review_status,
            "provenance_note": self.provenance_note,
            "source_txt": self.source_txt,
            "source_json": self.source_json,
            "content_checksum": self.content_checksum,
            "embedding_model": embedding_model,
            "embedding_dimension": len(vector),
        }
        grade, book_series = textbook_source_metadata(self.source)
        if grade is not None:
            document["source_grade"] = grade
        if book_series is not None:
            document["source_book_series"] = book_series
        page_number = source_page_number(self.source)
        if page_number is not None:
            document["source_page_number"] = page_number
            document["source_page_status"] = "verified"
        elif is_textbook_source_name(str(self.source.get("name") or "")):
            document["source_page_status"] = "unverified"
        else:
            document["source_page_status"] = "not_applicable"
        return document


class HISEduDataset:
    def __init__(self, questions_dir: Path, answers_dir: Path) -> None:
        self.questions_dir = questions_dir.resolve()
        self.answers_dir = answers_dir.resolve()

    def __iter__(self) -> Iterator[DatasetRecord]:
        yield from self.load()

    def load(self) -> list[DatasetRecord]:
        if not self.questions_dir.is_dir() or not self.answers_dir.is_dir():
            raise DatasetError(
                f"Expected dataset directories: {self.questions_dir} and {self.answers_dir}"
            )
        answer_paths = sorted(self.answers_dir.rglob("*.json"))
        records = [self._load_record(path) for path in answer_paths]
        ids = [record.record_id for record in records]
        chunk_ids = [record.chunk_id for record in records]
        if len(ids) != len(set(ids)):
            raise DatasetError("Duplicate record_id detected")
        if len(chunk_ids) != len(set(chunk_ids)):
            raise DatasetError("Duplicate chunk_id detected")
        question_count = sum(1 for _ in self.questions_dir.rglob("*.txt"))
        if question_count != len(records):
            raise DatasetError(
                f"Question/answer count mismatch: {question_count} TXT vs {len(records)} JSON"
            )
        return records

    def _load_record(self, answer_path: Path) -> DatasetRecord:
        relative_answer = answer_path.relative_to(self.answers_dir)
        question_path = self.questions_dir / relative_answer.with_suffix(".txt")
        if not question_path.is_file():
            raise DatasetError(f"Missing paired TXT for {answer_path}")
        try:
            data = json.loads(
                answer_path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, DatasetError) as exc:
            raise DatasetError(f"Cannot parse {answer_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise DatasetError(f"JSON root must be an object: {answer_path}")
        required = {
            "dataset_name",
            "version",
            "id",
            "chunk_id",
            "title",
            "question",
            "answer",
            "answer_type",
            "difficulty",
            "chapter",
            "lesson",
            "keywords",
            "source",
            "review_status",
            "provenance_note",
            "paired_question_file",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise DatasetError(f"Missing fields in {answer_path}: {missing}")
        for field in ("chapter", "lesson", "source"):
            if not isinstance(data[field], dict):
                raise DatasetError(f"{field} must be an object: {answer_path}")
        source = data["source"]
        missing_source_fields = sorted(
            {"name", "url", "locator", "page_number"} - source.keys()
        )
        if missing_source_fields:
            raise DatasetError(
                f"Missing source fields in {answer_path}: {missing_source_fields}"
            )
        raw_page = source.get("page_number")
        if raw_page is not None and source_page_number(source) is None:
            raise DatasetError(f"source.page_number must be 1..10000: {answer_path}")
        if is_textbook_source_name(str(source.get("name") or "")):
            grade, book_series = textbook_source_metadata(source)
            if grade is None or not book_series:
                raise DatasetError(
                    "Textbook source must identify grade and book series: "
                    f"{answer_path}"
                )
        if not isinstance(data["keywords"], list) or not all(
            isinstance(item, str) and item.strip() for item in data["keywords"]
        ):
            raise DatasetError(f"keywords must be non-empty strings: {answer_path}")
        txt_question = question_body(question_path.read_text(encoding="utf-8"))
        json_question = normalize_text(str(data["question"]))
        if txt_question != json_question:
            raise DatasetError(f"TXT/JSON question mismatch: {relative_answer}")
        if data["paired_question_file"] != question_path.name:
            raise DatasetError(f"paired_question_file mismatch: {relative_answer}")
        relative_parts = relative_answer.parts
        if data["chapter"]["folder"] != relative_parts[0]:
            raise DatasetError(f"chapter.folder mismatch: {relative_answer}")
        if data["lesson"]["folder"] != relative_parts[1]:
            raise DatasetError(f"lesson.folder mismatch: {relative_answer}")
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        checksum = hashlib.sha256(
            (txt_question + "\n" + canonical).encode("utf-8")
        ).hexdigest()
        project_root = self.answers_dir.parent
        return DatasetRecord(
            record_id=str(data["id"]),
            chunk_id=str(data["chunk_id"]),
            question=json_question,
            answer=normalize_text(str(data["answer"])),
            answer_type=str(data["answer_type"]),
            difficulty=str(data["difficulty"]),
            title=str(data["title"]),
            dataset_name=str(data["dataset_name"]),
            dataset_version=str(data["version"]),
            chapter=dict(data["chapter"]),
            lesson=dict(data["lesson"]),
            keywords=tuple(str(item) for item in data["keywords"]),
            source=dict(data["source"]),
            review_status=str(data["review_status"]),
            provenance_note=str(data["provenance_note"]),
            source_txt=question_path.relative_to(project_root).as_posix(),
            source_json=answer_path.relative_to(project_root).as_posix(),
            content_checksum=checksum,
        )
