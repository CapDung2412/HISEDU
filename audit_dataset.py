from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
QUESTION_ROOT = ROOT / ("questions" if (ROOT / "questions").exists() else "question")
ANSWER_ROOT = ROOT / ("answers" if (ROOT / "answers").exists() else "answer")
SOURCE_ROOT = ROOT / (
    "source_documents" if (ROOT / "source_documents").exists() else "du_lieu"
)
REPORT_ROOT = ROOT / "reports"

EXPECTED_TOP_LEVEL = (
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
)

EXPECTED_TYPES: dict[str, type | tuple[type, ...]] = {
    "dataset_name": str,
    "version": str,
    "id": str,
    "chunk_id": str,
    "title": str,
    "question": str,
    "answer": str,
    "answer_type": str,
    "difficulty": str,
    "chapter": dict,
    "lesson": dict,
    "keywords": list,
    "source": dict,
    "review_status": str,
    "provenance_note": str,
    "paired_question_file": str,
}

WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class DuplicateJsonKey(ValueError):
    pass


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalized_hash(value: str) -> str:
    normalized = unicodedata.normalize("NFC", normalize_text(value).casefold())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def strict_constant(value: str) -> Any:
    raise ValueError(f"Non-standard JSON constant: {value}")


def reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise DuplicateJsonKey(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_utf8(path: Path) -> tuple[str | None, dict[str, Any]]:
    data = path.read_bytes()
    result: dict[str, Any] = {
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "has_utf8_bom": data.startswith(b"\xef\xbb\xbf"),
        "empty": not bool(data.strip()),
        "valid_utf8": False,
        "contains_replacement_character": False,
        "contains_nul": b"\x00" in data,
    }
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        result["decode_error"] = {
            "start": exc.start,
            "end": exc.end,
            "reason": exc.reason,
        }
        return None, result
    result["valid_utf8"] = True
    result["contains_replacement_character"] = "\ufffd" in text
    return text, result


def parse_question_text(text: str) -> tuple[str, dict[str, str], list[str]]:
    parts = re.split(r"\r?\n---\s*\r?\n", text, maxsplit=1)
    question = normalize_text(parts[0])
    metadata: dict[str, str] = {}
    warnings: list[str] = []
    if len(parts) == 1:
        warnings.append("missing_metadata_separator")
        return question, metadata, warnings
    for line_number, line in enumerate(parts[1].splitlines(), start=1):
        if not line.strip():
            continue
        if ":" not in line:
            warnings.append(f"metadata_line_without_colon:{line_number}")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in metadata:
            warnings.append(f"duplicate_metadata_key:{key}")
        metadata[key] = value.strip()
    return question, metadata, warnings


def add_issue(
    issues: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    pair_key: str | None = None,
    details: Any = None,
) -> None:
    item: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path is not None:
        item["path"] = path
    if pair_key is not None:
        item["pair_key"] = pair_key
    if details is not None:
        item["details"] = details
    issues.append(item)


def key_for(path: Path, base: Path) -> str:
    return path.relative_to(base).with_suffix("").as_posix()


def component_is_reserved(component: str) -> bool:
    stem = component.split(".", 1)[0].rstrip(" .").upper()
    return stem in WINDOWS_RESERVED


def proposed_dataset_path(path: Path, kind: str) -> str | None:
    base = QUESTION_ROOT if kind == "txt" else ANSWER_ROOT
    parts = path.relative_to(base).parts
    if len(parts) != 3:
        return None
    if base.name in {"questions", "answers"}:
        valid = (
            re.fullmatch(r"chapter_\d{2}", parts[0])
            and (
                re.fullmatch(r"lesson_\d{2}", parts[1])
                or re.fullmatch(r"review_lessons_\d{2}_\d{2}", parts[1])
            )
            and re.fullmatch(r"question_\d{3}\.(txt|json)", parts[2])
        )
        return relative(path) if valid else None
    chapter_match = re.fullmatch(r"Chương\s+(\d+)", parts[0])
    lesson_match = re.fullmatch(r"Bài\s+(\d+)", parts[1])
    review_match = re.fullmatch(r"Bài\s+tổng\s+hợp\s+(\d+)-(\d+)", parts[1])
    number_match = re.match(r"^(\d+)-", path.stem)
    if not chapter_match or not number_match or not (lesson_match or review_match):
        return None
    chapter = f"chapter_{int(chapter_match.group(1)):02d}"
    if lesson_match:
        lesson = f"lesson_{int(lesson_match.group(1)):02d}"
    else:
        assert review_match is not None
        lesson = (
            f"review_lessons_{int(review_match.group(1)):02d}_"
            f"{int(review_match.group(2)):02d}"
        )
    filename = f"question_{int(number_match.group(1)):03d}{path.suffix.lower()}"
    root_name = "questions" if kind == "txt" else "answers"
    return Path(root_name, chapter, lesson, filename).as_posix()


def proposed_source_path(path: Path) -> str:
    if SOURCE_ROOT.name == "source_documents":
        return relative(path)
    known = {
        "Chuong_1_20_cau.docx": "chapter_01_20_questions.docx",
        "Chuong_2_20_cau.docx": "chapter_02_20_questions.docx",
        "Chuong_3_20_cau.docx": "chapter_03_20_questions.docx",
        "LS_01_Cau_hoi.docx": "history_01_questions.docx",
        "LS_02_Cau_hoi.docx": "history_02_questions.docx",
        "LS_03_Cau_hoi.docx": "history_03_questions.docx",
        "LS_04_Cau_hoi.docx": "history_04_questions.docx",
        "LS_05_Cau_hoi.docx": "history_05_questions.docx",
        "LS_06_Cau_hoi.docx": "history_06_questions.docx",
        "LS_07_Cau_hoi.docx": "history_07_questions.docx",
        "Tom_tat_Lich_su_8_Ket_noi_tri_thuc_Bai_1-9.docx": (
            "history_8_summary_lessons_01_09.docx"
        ),
    }
    return Path("source_documents", known.get(path.name, path.name.lower())).as_posix()


def numeric_stats(values: list[int]) -> dict[str, float | int] | None:
    if not values:
        return None
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "p95": sorted(values)[max(0, math.ceil(len(values) * 0.95) - 1)],
    }


def proposed_schema() -> dict[str, Any]:
    id_pattern = r"^[A-Z0-9_]+$"
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://hisedu.local/schemas/answer.schema.json",
        "title": "HISEDU history question-answer record",
        "type": "object",
        "additionalProperties": False,
        "required": list(EXPECTED_TOP_LEVEL),
        "properties": {
            "dataset_name": {"type": "string", "minLength": 1},
            "version": {"type": "string", "minLength": 1},
            "id": {"type": "string", "pattern": id_pattern},
            "chunk_id": {"type": "string", "pattern": id_pattern},
            "title": {"type": "string", "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$"},
            "question": {"type": "string", "minLength": 1},
            "answer": {"type": "string", "minLength": 1},
            "answer_type": {"type": "string", "minLength": 1},
            "difficulty": {"type": "string", "minLength": 1},
            "chapter": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "folder", "title"],
                "properties": {
                    "id": {"type": "string", "pattern": id_pattern},
                    "folder": {"type": "string", "pattern": r"^chapter_\d{2}$"},
                    "title": {"type": "string", "minLength": 1},
                },
            },
            "lesson": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "folder", "title"],
                "properties": {
                    "id": {"type": "string", "pattern": id_pattern},
                    "folder": {
                        "type": "string",
                        "pattern": r"^(?:lesson_\d{2}|review_lessons_\d{2}_\d{2})$",
                    },
                    "title": {"type": "string", "minLength": 1},
                },
            },
            "keywords": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "source": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "url", "locator", "page_number"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "format": "uri"},
                    "locator": {"type": "string", "minLength": 1},
                    "page_number": {"type": ["integer", "null"], "minimum": 1},
                },
            },
            "review_status": {"type": "string", "minLength": 1},
            "provenance_note": {"type": "string", "minLength": 1},
            "paired_question_file": {
                "type": "string",
                "pattern": r"^[^/\\]+\.txt$",
            },
        },
    }


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    def clean(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    output = [
        "| " + " | ".join(clean(value) for value in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend(
        "| " + " | ".join(clean(value) for value in row) + " |" for row in rows
    )
    return "\n".join(output)


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    issues: list[dict[str, Any]] = []
    question_files = sorted(QUESTION_ROOT.rglob("*.txt")) if QUESTION_ROOT.exists() else []
    answer_files = sorted(ANSWER_ROOT.rglob("*.json")) if ANSWER_ROOT.exists() else []
    source_files = sorted(SOURCE_ROOT.rglob("*.docx")) if SOURCE_ROOT.exists() else []

    question_map: dict[str, list[Path]] = defaultdict(list)
    answer_map: dict[str, list[Path]] = defaultdict(list)
    for path in question_files:
        question_map[key_for(path, QUESTION_ROOT).casefold()].append(path)
    for path in answer_files:
        answer_map[key_for(path, ANSWER_ROOT).casefold()].append(path)

    all_keys = sorted(set(question_map) | set(answer_map))
    pair_records: list[dict[str, Any]] = []
    file_records: list[dict[str, Any]] = []
    parsed_answers: dict[str, dict[str, Any]] = {}
    question_hashes: dict[str, list[str]] = defaultdict(list)
    answer_hashes: dict[str, list[str]] = defaultdict(list)
    ids: dict[str, list[str]] = defaultdict(list)
    chunk_ids: dict[str, list[str]] = defaultdict(list)
    field_presence: Counter[str] = Counter()
    field_types: dict[str, Counter[str]] = defaultdict(Counter)
    nested_field_presence: dict[str, Counter[str]] = defaultdict(Counter)
    nested_field_types: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    question_lengths: list[int] = []
    question_words: list[int] = []
    answer_lengths: list[int] = []
    answer_words: list[int] = []
    json_sizes: list[int] = []
    exact_question_matches = 0
    metadata_id_matches = 0
    metadata_chunk_matches = 0
    paired_filename_matches = 0
    folder_matches = 0
    parseable_json_count = 0
    utf8_txt_count = 0
    utf8_json_count = 0
    bom_count = 0

    for pair_key in all_keys:
        q_candidates = question_map.get(pair_key, [])
        a_candidates = answer_map.get(pair_key, [])
        pair: dict[str, Any] = {
            "pair_key": pair_key,
            "question_paths": [relative(path) for path in q_candidates],
            "answer_paths": [relative(path) for path in a_candidates],
            "classification": None,
            "record_id": None,
            "checks": {},
        }
        if len(q_candidates) > 1 or len(a_candidates) > 1:
            pair["classification"] = "ambiguous_pair"
            add_issue(
                issues,
                "error",
                "ambiguous_pair",
                "More than one file maps to the same case-insensitive relative stem.",
                pair_key=pair_key,
                details={
                    "question_paths": pair["question_paths"],
                    "answer_paths": pair["answer_paths"],
                },
            )
            pair_records.append(pair)
            continue
        if not q_candidates:
            pair["classification"] = "orphan_json"
            add_issue(
                issues,
                "error",
                "orphan_json",
                "JSON file has no matching question file.",
                path=relative(a_candidates[0]),
                pair_key=pair_key,
            )
            pair_records.append(pair)
            continue
        if not a_candidates:
            pair["classification"] = "orphan_txt"
            add_issue(
                issues,
                "error",
                "orphan_txt",
                "Question file has no matching JSON file.",
                path=relative(q_candidates[0]),
                pair_key=pair_key,
            )
            pair_records.append(pair)
            continue

        question_path = q_candidates[0]
        answer_path = a_candidates[0]
        question_text_raw, question_encoding = read_utf8(question_path)
        answer_text_raw, answer_encoding = read_utf8(answer_path)
        pair["checks"]["question_encoding"] = question_encoding
        pair["checks"]["answer_encoding"] = answer_encoding
        if question_encoding["valid_utf8"]:
            utf8_txt_count += 1
        if answer_encoding["valid_utf8"]:
            utf8_json_count += 1
        bom_count += int(question_encoding["has_utf8_bom"])
        bom_count += int(answer_encoding["has_utf8_bom"])

        invalid_txt = False
        invalid_json = False
        if question_text_raw is None:
            invalid_txt = True
            add_issue(
                issues,
                "error",
                "invalid_utf8_txt",
                "Question file is not valid UTF-8.",
                path=relative(question_path),
                pair_key=pair_key,
                details=question_encoding.get("decode_error"),
            )
        elif question_encoding["empty"]:
            invalid_txt = True
            add_issue(
                issues,
                "error",
                "empty_txt",
                "Question file is empty.",
                path=relative(question_path),
                pair_key=pair_key,
            )
        if answer_text_raw is None:
            invalid_json = True
            add_issue(
                issues,
                "error",
                "invalid_utf8_json",
                "Answer file is not valid UTF-8.",
                path=relative(answer_path),
                pair_key=pair_key,
                details=answer_encoding.get("decode_error"),
            )
        elif answer_encoding["empty"]:
            invalid_json = True
            add_issue(
                issues,
                "error",
                "empty_json",
                "Answer file is empty.",
                path=relative(answer_path),
                pair_key=pair_key,
            )

        question = ""
        question_metadata: dict[str, str] = {}
        if question_text_raw is not None:
            question, question_metadata, metadata_warnings = parse_question_text(
                question_text_raw.lstrip("\ufeff")
            )
            pair["checks"]["question_metadata"] = question_metadata
            if not question:
                invalid_txt = True
                add_issue(
                    issues,
                    "error",
                    "empty_question_text",
                    "Question body before the metadata separator is empty.",
                    path=relative(question_path),
                    pair_key=pair_key,
                )
            for warning in metadata_warnings:
                add_issue(
                    issues,
                    "warning",
                    warning.split(":", 1)[0],
                    warning,
                    path=relative(question_path),
                    pair_key=pair_key,
                )

        answer_obj: dict[str, Any] | None = None
        if answer_text_raw is not None and not answer_encoding["empty"]:
            try:
                candidate = json.loads(
                    answer_text_raw.lstrip("\ufeff"),
                    parse_constant=strict_constant,
                    object_pairs_hook=reject_duplicate_keys,
                )
                if not isinstance(candidate, dict):
                    invalid_json = True
                    add_issue(
                        issues,
                        "error",
                        "json_root_not_object",
                        f"JSON root must be an object, got {json_type(candidate)}.",
                        path=relative(answer_path),
                        pair_key=pair_key,
                    )
                else:
                    answer_obj = candidate
                    parseable_json_count += 1
            except json.JSONDecodeError as exc:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "json_syntax_error",
                    exc.msg,
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details={"line": exc.lineno, "column": exc.colno, "position": exc.pos},
                )
            except (DuplicateJsonKey, ValueError) as exc:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "json_strict_validation_error",
                    str(exc),
                    path=relative(answer_path),
                    pair_key=pair_key,
                )

        if answer_obj is not None:
            parsed_answers[pair_key] = answer_obj
            json_sizes.append(answer_encoding["bytes"])
            record_id = answer_obj.get("id")
            pair["record_id"] = record_id if isinstance(record_id, str) else None
            for field, value in answer_obj.items():
                field_presence[field] += 1
                field_types[field][json_type(value)] += 1
                if isinstance(value, dict):
                    for nested_field, nested_value in value.items():
                        nested_field_presence[field][nested_field] += 1
                        nested_field_types[field][nested_field][json_type(nested_value)] += 1

            missing_fields = [field for field in EXPECTED_TOP_LEVEL if field not in answer_obj]
            unexpected_fields = [
                field for field in answer_obj if field not in EXPECTED_TOP_LEVEL
            ]
            wrong_types = {
                field: {
                    "expected": getattr(EXPECTED_TYPES[field], "__name__", str(EXPECTED_TYPES[field])),
                    "actual": type(answer_obj[field]).__name__,
                }
                for field in EXPECTED_TOP_LEVEL
                if field in answer_obj
                and not isinstance(answer_obj[field], EXPECTED_TYPES[field])
            }
            pair["checks"]["missing_fields"] = missing_fields
            pair["checks"]["unexpected_fields"] = unexpected_fields
            pair["checks"]["wrong_types"] = wrong_types
            if missing_fields or wrong_types:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "json_schema_shape_error",
                    "Required fields are missing or have an unexpected type.",
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details={"missing_fields": missing_fields, "wrong_types": wrong_types},
                )
            if unexpected_fields:
                add_issue(
                    issues,
                    "warning",
                    "unexpected_json_fields",
                    "JSON contains fields outside the observed canonical schema.",
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details=unexpected_fields,
                )

            empty_required_strings = [
                field
                for field in (
                    "dataset_name",
                    "version",
                    "id",
                    "chunk_id",
                    "title",
                    "question",
                    "answer",
                    "answer_type",
                    "difficulty",
                    "review_status",
                    "provenance_note",
                    "paired_question_file",
                )
                if isinstance(answer_obj.get(field), str) and not answer_obj[field].strip()
            ]
            if empty_required_strings:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "empty_required_json_fields",
                    "Required string fields must not be empty.",
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details=empty_required_strings,
                )

            json_question = normalize_text(str(answer_obj.get("question", "")))
            exact_match = bool(question) and question == json_question
            pair["checks"]["question_exact_match"] = exact_match
            if exact_match:
                exact_question_matches += 1
            else:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "question_content_mismatch",
                    "Question text does not exactly match JSON question after whitespace normalization.",
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details={"txt_question": question, "json_question": json_question},
                )

            id_match = question_metadata.get("question_id") == answer_obj.get("id")
            chunk_match = question_metadata.get("chunk_id") == answer_obj.get("chunk_id")
            pair["checks"]["metadata_id_match"] = id_match
            pair["checks"]["metadata_chunk_id_match"] = chunk_match
            if id_match:
                metadata_id_matches += 1
            else:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "question_id_mismatch",
                    "TXT question_id does not match JSON id.",
                    pair_key=pair_key,
                    details={
                        "txt": question_metadata.get("question_id"),
                        "json": answer_obj.get("id"),
                    },
                )
            if chunk_match:
                metadata_chunk_matches += 1
            else:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "chunk_id_mismatch",
                    "TXT chunk_id does not match JSON chunk_id.",
                    pair_key=pair_key,
                    details={
                        "txt": question_metadata.get("chunk_id"),
                        "json": answer_obj.get("chunk_id"),
                    },
                )

            paired_name_match = answer_obj.get("paired_question_file") == question_path.name
            pair["checks"]["paired_question_file_match"] = paired_name_match
            if paired_name_match:
                paired_filename_matches += 1
            else:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "paired_question_file_mismatch",
                    "paired_question_file does not name the matching TXT file.",
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details={
                        "declared": answer_obj.get("paired_question_file"),
                        "actual": question_path.name,
                    },
                )

            relative_parts = question_path.relative_to(QUESTION_ROOT).parts
            chapter_folder = (
                answer_obj.get("chapter", {}).get("folder")
                if isinstance(answer_obj.get("chapter"), dict)
                else None
            )
            lesson_folder = (
                answer_obj.get("lesson", {}).get("folder")
                if isinstance(answer_obj.get("lesson"), dict)
                else None
            )
            folder_match = (
                len(relative_parts) >= 3
                and chapter_folder == relative_parts[0]
                and lesson_folder == relative_parts[1]
            )
            pair["checks"]["json_folder_metadata_match"] = folder_match
            if folder_match:
                folder_matches += 1
            else:
                invalid_json = True
                add_issue(
                    issues,
                    "error",
                    "folder_metadata_mismatch",
                    "JSON chapter/lesson folder metadata does not match the filesystem.",
                    pair_key=pair_key,
                    details={
                        "json_chapter": chapter_folder,
                        "actual_chapter": relative_parts[0] if relative_parts else None,
                        "json_lesson": lesson_folder,
                        "actual_lesson": relative_parts[1] if len(relative_parts) > 1 else None,
                    },
                )

            if re.fullmatch(r"question_\d{3}", answer_path.stem):
                expected_title = "lowercase ASCII kebab-case"
                title_match = bool(
                    isinstance(answer_obj.get("title"), str)
                    and re.fullmatch(
                        r"[a-z0-9]+(?:-[a-z0-9]+)*", answer_obj["title"]
                    )
                )
                pair["checks"]["title_is_valid_slug"] = title_match
            else:
                expected_title = re.sub(r"^\d+-", "", answer_path.stem)
                title_match = answer_obj.get("title") == expected_title
                pair["checks"]["title_matches_filename_slug"] = title_match
            if not title_match:
                add_issue(
                    issues,
                    "warning",
                    "invalid_title_slug",
                    "JSON title is not a valid lowercase ASCII kebab-case slug.",
                    path=relative(answer_path),
                    pair_key=pair_key,
                    details={"json_title": answer_obj.get("title"), "expected": expected_title},
                )

            if isinstance(record_id, str):
                ids[record_id].append(pair_key)
            chunk_id = answer_obj.get("chunk_id")
            if isinstance(chunk_id, str):
                chunk_ids[chunk_id].append(pair_key)
            if question:
                question_hashes[normalized_hash(question)].append(pair_key)
                question_lengths.append(len(question))
                question_words.append(len(question.split()))
            answer_value = answer_obj.get("answer")
            if isinstance(answer_value, str):
                answer_hashes[normalized_hash(answer_value)].append(pair_key)
                answer_lengths.append(len(answer_value))
                answer_words.append(len(answer_value.split()))

            keywords = answer_obj.get("keywords")
            if isinstance(keywords, list):
                if not keywords or any(not isinstance(item, str) or not item.strip() for item in keywords):
                    invalid_json = True
                    add_issue(
                        issues,
                        "error",
                        "invalid_keywords",
                        "keywords must be a non-empty list of non-empty strings.",
                        path=relative(answer_path),
                        pair_key=pair_key,
                    )
                normalized_keywords = [
                    normalize_text(item).casefold() for item in keywords if isinstance(item, str)
                ]
                if len(set(normalized_keywords)) != len(normalized_keywords):
                    add_issue(
                        issues,
                        "warning",
                        "duplicate_keywords",
                        "keywords contains duplicates after case/whitespace normalization.",
                        path=relative(answer_path),
                        pair_key=pair_key,
                    )

        if invalid_txt:
            pair["classification"] = "invalid_txt"
        elif invalid_json:
            pair["classification"] = "invalid_json"
        else:
            pair["classification"] = "valid_pair"
        pair_records.append(pair)

    duplicate_pair_keys: set[str] = set()
    duplicate_id_groups = {key: values for key, values in ids.items() if len(values) > 1}
    duplicate_chunk_groups = {
        key: values for key, values in chunk_ids.items() if len(values) > 1
    }
    duplicate_question_groups = [
        values for values in question_hashes.values() if len(values) > 1
    ]
    duplicate_answer_groups = [
        values for values in answer_hashes.values() if len(values) > 1
    ]
    for values in duplicate_id_groups.values():
        duplicate_pair_keys.update(values)
    for values in duplicate_chunk_groups.values():
        duplicate_pair_keys.update(values)
    for values in duplicate_question_groups:
        duplicate_pair_keys.update(values)
    if duplicate_pair_keys:
        for pair in pair_records:
            if pair["pair_key"] in duplicate_pair_keys and pair["classification"] == "valid_pair":
                pair["classification"] = "duplicate"
        add_issue(
            issues,
            "error",
            "duplicate_records",
            "Duplicate IDs, chunk IDs, or normalized question bodies were found.",
            details={
                "duplicate_ids": duplicate_id_groups,
                "duplicate_chunk_ids": duplicate_chunk_groups,
                "duplicate_question_groups": duplicate_question_groups,
            },
        )

    pair_by_key = {pair["pair_key"]: pair for pair in pair_records}
    for path in question_files:
        pair_key = key_for(path, QUESTION_ROOT).casefold()
        pair = pair_by_key[pair_key]
        file_records.append(
            {
                "path": relative(path),
                "kind": "question_txt",
                "pair_key": pair_key,
                "record_id": pair.get("record_id"),
                "classification": pair["classification"],
            }
        )
    for path in answer_files:
        pair_key = key_for(path, ANSWER_ROOT).casefold()
        pair = pair_by_key[pair_key]
        file_records.append(
            {
                "path": relative(path),
                "kind": "answer_json",
                "pair_key": pair_key,
                "record_id": pair.get("record_id"),
                "classification": pair["classification"],
                "json_parseable": pair_key in parsed_answers,
            }
        )

    classification_counts = Counter(pair["classification"] for pair in pair_records)
    file_classification_counts = Counter(item["classification"] for item in file_records)

    path_files = question_files + answer_files + source_files
    path_inventory: list[dict[str, Any]] = []
    proposed_mapping: list[dict[str, Any]] = []
    proposed_targets: dict[str, list[str]] = defaultdict(list)
    already_compliant_paths = 0
    unresolved_path_targets = 0
    non_ascii_paths = 0
    paths_with_spaces = 0
    reserved_paths = 0
    uppercase_paths = 0
    over_260_paths = 0
    absolute_path_lengths: list[int] = []
    for path in path_files:
        rel = relative(path)
        components = Path(rel).parts
        abs_length = len(str(path.resolve()))
        absolute_path_lengths.append(abs_length)
        has_non_ascii = not rel.isascii()
        has_space = any(" " in component for component in components)
        has_reserved = any(component_is_reserved(component) for component in components)
        has_uppercase = any(component != component.lower() for component in components)
        non_ascii_paths += int(has_non_ascii)
        paths_with_spaces += int(has_space)
        reserved_paths += int(has_reserved)
        uppercase_paths += int(has_uppercase)
        over_260_paths += int(abs_length >= 260)
        path_inventory.append(
            {
                "path": rel,
                "ascii": not has_non_ascii,
                "has_spaces": has_space,
                "has_windows_reserved_component": has_reserved,
                "all_lowercase": not has_uppercase,
                "absolute_length": abs_length,
            }
        )
        if path.suffix.lower() == ".txt":
            target = proposed_dataset_path(path, "txt")
        elif path.suffix.lower() == ".json":
            target = proposed_dataset_path(path, "json")
        else:
            target = proposed_source_path(path)
        if target is None:
            unresolved_path_targets += 1
        elif target == rel:
            already_compliant_paths += 1
        else:
            proposed_mapping.append(
                {"old_path": rel, "new_path": target, "status": "planned_not_applied"}
            )
            proposed_targets[target.casefold()].append(rel)
    proposed_collisions = {
        target: sources for target, sources in proposed_targets.items() if len(sources) > 1
    }

    docx_inventory: list[dict[str, Any]] = []
    for path in source_files:
        item: dict[str, Any] = {
            "path": relative(path),
            "bytes": path.stat().st_size,
            "valid_docx_container": False,
        }
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                item["valid_docx_container"] = {
                    "[Content_Types].xml",
                    "word/document.xml",
                }.issubset(names)
                item["zip_test_error"] = archive.testzip()
        except (OSError, zipfile.BadZipFile) as exc:
            item["error"] = str(exc)
        docx_inventory.append(item)

    field_summary = {
        field: {
            "present": field_presence[field],
            "missing": len(parsed_answers) - field_presence[field],
            "types": dict(sorted(field_types[field].items())),
        }
        for field in sorted(field_presence)
    }
    nested_field_summary = {
        parent: {
            field: {
                "present": count,
                "types": dict(sorted(nested_field_types[parent][field].items())),
            }
            for field, count in sorted(fields.items())
        }
        for parent, fields in sorted(nested_field_presence.items())
    }
    severity_counts = Counter(issue["severity"] for issue in issues)

    report: dict[str, Any] = {
        "meta": {
            "generated_at_utc": generated_at,
            "workspace": str(ROOT),
            "phase": "phase_1_read_only_dataset_audit",
            "dataset_files_modified": False,
            "env_file_read": False,
            "audit_tool": relative(Path(__file__)),
        },
        "summary": {
            "question_txt_files": len(question_files),
            "answer_json_files": len(answer_files),
            "dataset_files_total": len(question_files) + len(answer_files),
            "dataset_files_classified": len(file_records),
            "relative_stems_total": len(all_keys),
            "pair_classifications": dict(sorted(classification_counts.items())),
            "file_classifications": dict(sorted(file_classification_counts.items())),
            "utf8_question_files": utf8_txt_count,
            "utf8_json_files": utf8_json_count,
            "json_files_parseable_strictly": parseable_json_count,
            "files_with_utf8_bom": bom_count,
            "exact_txt_json_question_matches": exact_question_matches,
            "txt_json_id_matches": metadata_id_matches,
            "txt_json_chunk_id_matches": metadata_chunk_matches,
            "paired_question_filename_matches": paired_filename_matches,
            "json_filesystem_folder_matches": folder_matches,
            "issues_by_severity": dict(sorted(severity_counts.items())),
            "source_docx_files": len(source_files),
            "valid_docx_containers": sum(
                bool(item["valid_docx_container"]) and item.get("zip_test_error") is None
                for item in docx_inventory
            ),
        },
        "content_statistics": {
            "question_characters": numeric_stats(question_lengths),
            "question_whitespace_words": numeric_stats(question_words),
            "answer_characters": numeric_stats(answer_lengths),
            "answer_whitespace_words": numeric_stats(answer_words),
            "json_file_bytes": numeric_stats(json_sizes),
            "note": (
                "Whitespace-word and character counts are not model token counts. "
                "Token truncation must be measured with the selected checkpoint tokenizer."
            ),
        },
        "pair_integrity": {
            "duplicate_ids": duplicate_id_groups,
            "duplicate_chunk_ids": duplicate_chunk_groups,
            "duplicate_question_groups": duplicate_question_groups,
            "duplicate_answer_groups": duplicate_answer_groups,
        },
        "schema_observation": {
            "parsed_object_count": len(parsed_answers),
            "top_level_fields": field_summary,
            "nested_fields": nested_field_summary,
            "proposed_schema_file": "reports/proposed_answer.schema.json",
        },
        "recommended_retrieval_record": {
            "search_text_fields": [
                "question",
                "chapter.title",
                "lesson.title",
                "keywords",
            ],
            "return_as_metadata_or_fetch_by_record_id": [
                "answer",
                "answer_type",
                "difficulty",
                "source",
                "review_status",
                "provenance_note",
            ],
            "do_not_embed_raw_json": True,
        },
        "path_audit": {
            "files_checked": len(path_files),
            "paths_containing_non_ascii": non_ascii_paths,
            "paths_containing_spaces": paths_with_spaces,
            "paths_with_windows_reserved_component": reserved_paths,
            "paths_not_all_lowercase": uppercase_paths,
            "absolute_paths_at_least_260_characters": over_260_paths,
            "absolute_path_length": numeric_stats(absolute_path_lengths),
            "semantic_language_observation": (
                "Dataset paths now use stable English ASCII identifiers. Vietnamese question "
                "content and semantic titles remain inside TXT/JSON."
            ),
            "proposed_strategy": (
                "Use questions|answers/chapter_NN/lesson_NN/question_NNN.ext; "
                "use review_lessons_AA_BB for synthesis folders; retain the full Vietnamese "
                "question and title inside TXT/JSON."
            ),
            "planned_mapping_entries": len(proposed_mapping),
            "already_compliant_paths": already_compliant_paths,
            "planned_mapping_unresolved": unresolved_path_targets,
            "planned_case_insensitive_collisions": proposed_collisions,
            "planned_mapping": proposed_mapping,
            "inventory": path_inventory,
        },
        "clip_ocr_assessment": {
            "dataset_contains_images": False,
            "pure_clip_recommendation": "not_sufficient_for_photographed_vietnamese_text",
            "reason": (
                "The indexed dataset is text-only and the target image is expected to contain a "
                "printed question. CLIP is not an OCR engine, and a generic CLIP text tower may "
                "truncate or weakly represent Vietnamese text."
            ),
            "recommended_query_flow": [
                "image quality/orientation normalization",
                "Vietnamese OCR",
                "text normalization",
                "multilingual text retrieval against question/search_text",
                "optional CLIP image-text score as a secondary signal",
                "fetch JSON answer by stable record_id",
            ],
            "evaluation_required": (
                "No image ground-truth set is present, so Recall@K and a confidence threshold "
                "cannot be measured in phase 1."
            ),
        },
        "source_documents": docx_inventory,
        "issues": issues,
        "pairs": pair_records,
        "files": file_records,
    }
    return report, proposed_schema()


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    class_counts = summary["pair_classifications"]
    stats = report["content_statistics"]
    path_audit = report["path_audit"]
    issues = report["issues"]
    top_fields = report["schema_observation"]["top_level_fields"]
    docx = report["source_documents"]
    mapping = path_audit["planned_mapping"]

    issue_rows = [
        [
            issue["severity"],
            issue["code"],
            issue.get("path", issue.get("pair_key", "-")),
            issue["message"],
        ]
        for issue in issues[:100]
    ]
    field_rows = [
        [field, values["present"], values["missing"], json.dumps(values["types"])]
        for field, values in top_fields.items()
    ]
    source_rows = [
        [
            item["path"],
            item["bytes"],
            item["valid_docx_container"],
            item.get("zip_test_error"),
        ]
        for item in docx
    ]
    mapping_rows = [
        [item["old_path"], item["new_path"]] for item in mapping[:12]
    ]
    classification_rows = [
        [name, class_counts.get(name, 0)]
        for name in (
            "valid_pair",
            "orphan_txt",
            "orphan_json",
            "duplicate",
            "invalid_txt",
            "invalid_json",
            "ambiguous_pair",
        )
    ]

    sections = [
        "# HISEDU Dataset Audit — Phase 1",
        "",
        f"Generated (UTC): `{report['meta']['generated_at_utc']}`",
        "",
        f"> Scope: read-only audit of `{QUESTION_ROOT.name}/**/*.txt`, "
        f"`{ANSWER_ROOT.name}/**/*.json`, and a basic DOCX-container health check for "
        f"`{SOURCE_ROOT.name}/*.docx`. Dataset files were not changed, "
        "renamed, or uploaded. `.env` was not read.",
        "",
        "## Kết luận nhanh",
        "",
        f"- TXT: **{summary['question_txt_files']}**; JSON: **{summary['answer_json_files']}**.",
        f"- JSON parse strict thành công: **{summary['json_files_parseable_strictly']}/"
        f"{summary['answer_json_files']}**.",
        f"- Cặp hợp lệ: **{class_counts.get('valid_pair', 0)}/"
        f"{summary['relative_stems_total']}**.",
        f"- Câu hỏi TXT khớp chính xác trường `question` JSON: **"
        f"{summary['exact_txt_json_question_matches']}/{summary['relative_stems_total']}**.",
        f"- ID và chunk ID khớp: **{summary['txt_json_id_matches']}** và **"
        f"{summary['txt_json_chunk_id_matches']}**.",
        f"- BOM UTF-8 phát hiện: **{summary['files_with_utf8_bom']}** file.",
        f"- DOCX có container hợp lệ: **{summary['valid_docx_containers']}/"
        f"{summary['source_docx_files']}**.",
        "- Kiểm tra này xác nhận cấu trúc và tính nhất quán dữ liệu, không thay thế việc giáo "
        "viên thẩm định độ chính xác lịch sử. Trường `review_status` trong dữ liệu vẫn phải "
        "được tôn trọng.",
        "",
        "## Phân loại toàn bộ cặp TXT/JSON",
        "",
        markdown_table(classification_rows, ["Classification", "Count"]),
        "",
        f"Tổng file dataset đã phân loại: **{summary['dataset_files_classified']}/"
        f"{summary['dataset_files_total']}**.",
        "",
        "## Khả năng đọc và schema JSON",
        "",
        "Mọi JSON được kiểm tra bằng UTF-8 strict, JSON syntax strict, từ chối `NaN`/"
        "`Infinity`, phát hiện duplicate key, kiểm tra root object, field bắt buộc và kiểu dữ liệu.",
        "",
        markdown_table(field_rows, ["Field", "Present", "Missing", "Observed types"]),
        "",
        "Schema đề xuất được lưu tại `reports/proposed_answer.schema.json`. Đây là schema "
        "suy ra từ dataset hiện tại, chưa phải hợp đồng production đã được phê duyệt.",
        "",
        "## Thống kê nội dung",
        "",
        f"- Độ dài câu hỏi (ký tự): `{json.dumps(stats['question_characters'], ensure_ascii=False)}`",
        f"- Độ dài câu hỏi (từ tách theo khoảng trắng): "
        f"`{json.dumps(stats['question_whitespace_words'], ensure_ascii=False)}`",
        f"- Độ dài câu trả lời (ký tự): `{json.dumps(stats['answer_characters'], ensure_ascii=False)}`",
        f"- Độ dài câu trả lời (từ tách theo khoảng trắng): "
        f"`{json.dumps(stats['answer_whitespace_words'], ensure_ascii=False)}`",
        f"- Kích thước JSON (bytes): `{json.dumps(stats['json_file_bytes'], ensure_ascii=False)}`",
        "",
        "Các số trên không phải token count. Cần đo lại bằng tokenizer đúng của checkpoint "
        "trước khi quyết định chunking hoặc truncation.",
        "",
        "## Trường dùng cho retrieval",
        "",
        "- Nên tạo `search_text` từ: `question`, `chapter.title`, `lesson.title`, `keywords`.",
        "- Không nên embed JSON thô. `answer` và các trường provenance/review nên được trả "
        "về dưới dạng metadata gọn hoặc tải theo `record_id`.",
        "- Không nên mặc định embed toàn bộ đáp án vì sẽ làm lệch mục tiêu tìm đúng câu hỏi.",
        "",
        "## Audit đường dẫn",
        "",
        f"- File path đã kiểm tra: **{path_audit['files_checked']}**.",
        f"- Path chứa non-ASCII: **{path_audit['paths_containing_non_ascii']}**.",
        f"- Path chứa khoảng trắng: **{path_audit['paths_containing_spaces']}**.",
        f"- Path chứa Windows reserved name: **"
        f"{path_audit['paths_with_windows_reserved_component']}**.",
        f"- Path tuyệt đối dài ít nhất 260 ký tự: **"
        f"{path_audit['absolute_paths_at_least_260_characters']}**.",
        f"- Độ dài path tuyệt đối: `{json.dumps(path_audit['absolute_path_length'])}`.",
        "",
        "Đường dẫn hiện dùng định danh tiếng Anh/ASCII ổn định; nội dung câu hỏi và title "
        "tiếng Việt vẫn được giữ trong TXT/JSON:",
        "",
        "`questions/chapter_NN/lesson_NN/question_NNN.txt`",
        "",
        "`answers/chapter_NN/lesson_NN/question_NNN.json`",
        "",
        "Mapping bên dưới chỉ xuất hiện nếu audit phát hiện path còn cần chuẩn hóa.",
        "",
        markdown_table(mapping_rows, ["Current path (sample)", "Proposed path"]),
        "",
        f"Dry-run mapping: **{path_audit['planned_mapping_entries']}** entry; unresolved: **"
        f"{path_audit['planned_mapping_unresolved']}**; collision không phân biệt hoa thường: **"
        f"{len(path_audit['planned_case_insensitive_collisions'])}**.",
        "",
        "## DOCX nguồn",
        "",
        markdown_table(source_rows, ["Path", "Bytes", "Valid DOCX container", "ZIP error"]),
        "",
        "Audit này chỉ xác nhận DOCX là container ZIP hợp lệ và có phần document chính; chưa "
        "đối chiếu toàn bộ nội dung DOCX với 327 câu hỏi.",
        "",
        "## CLIP và OCR",
        "",
        "Dataset hiện tại không có ảnh ground truth. Nếu đầu vào là ảnh chụp câu hỏi in trên "
        "giấy/màn hình, CLIP thuần không đủ tin cậy vì CLIP không phải OCR. Pipeline khuyến nghị:",
        "",
        "`ảnh → chỉnh hướng/chất lượng → OCR tiếng Việt → chuẩn hóa text → multilingual "
        "text retrieval → lấy answer JSON theo record_id`",
        "",
        "CLIP có thể được giữ làm tín hiệu ảnh–văn bản phụ, với cùng checkpoint/preprocessing "
        "ở lúc index và query. Cần tập ảnh thật để đo Recall@K và hiệu chỉnh threshold; hiện chưa "
        "có cơ sở tuyên bố độ chính xác.",
        "",
        "## Lỗi và cảnh báo",
        "",
    ]
    if issue_rows:
        sections.append(markdown_table(issue_rows, ["Severity", "Code", "Path/key", "Message"]))
        if len(issues) > len(issue_rows):
            sections.extend(
                [
                    "",
                    f"Markdown hiển thị 100/{len(issues)} issue đầu tiên; xem JSON report để có đủ dữ liệu.",
                ]
            )
    else:
        sections.append("Không phát hiện lỗi hoặc cảnh báo tự động.")
    sections.extend(
        [
            "",
            "## Trạng thái",
            "",
            "Giai đoạn 1 hoàn tất. Chưa đổi tên file, chưa viết pipeline CLIP/Pinecone, chưa đọc "
            "`.env`, và chưa gửi dữ liệu ra dịch vụ bên ngoài. Cần xác nhận `TIẾP TỤC` trước "
            "Giai đoạn 2.",
            "",
        ]
    )
    return "\n".join(sections)


def main() -> int:
    report, schema = run()
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "dataset_audit.json"
    markdown_path = REPORT_ROOT / "dataset_audit.md"
    schema_path = REPORT_ROOT / "proposed_answer.schema.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "report_json": relative(json_path),
                "report_markdown": relative(markdown_path),
                "schema": relative(schema_path),
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
