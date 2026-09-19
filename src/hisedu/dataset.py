from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


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
        page_number = self.source.get("page_number")
        if page_number is not None:
            document["source_page_number"] = int(page_number)
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
