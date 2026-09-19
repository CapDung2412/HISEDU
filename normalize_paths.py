from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "reports" / "dataset_audit.json"
MAPPING_PATH = ROOT / "reports" / "path_rename_mapping.json"
BACKUP_PATH = ROOT / "backups" / "pre_path_normalization.zip"
OLD_ROOTS = (ROOT / "question", ROOT / "answer", ROOT / "du_lieu")


def inside_workspace(relative_path: str) -> Path:
    path = (ROOT / relative_path).resolve()
    path.relative_to(ROOT)
    return path


def load_plan() -> list[dict[str, str]]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    raw_entries = report["path_audit"]["planned_mapping"]
    entries: list[dict[str, str]] = []
    for raw in raw_entries:
        old_path = str(raw["old_path"])
        new_path = str(raw["new_path"])
        inside_workspace(old_path)
        inside_workspace(new_path)
        entries.append({"old_path": old_path, "new_path": new_path})
    return entries


def validate_plan(entries: list[dict[str, str]]) -> dict[str, Any]:
    old_paths = [inside_workspace(item["old_path"]) for item in entries]
    new_paths = [inside_workspace(item["new_path"]) for item in entries]
    missing_sources = [str(path.relative_to(ROOT)) for path in old_paths if not path.is_file()]
    existing_targets = [str(path.relative_to(ROOT)) for path in new_paths if path.exists()]
    duplicate_targets = sorted(
        {
            str(path.relative_to(ROOT)).casefold()
            for path in new_paths
            if sum(candidate == path for candidate in new_paths) > 1
        }
    )
    current_files = sorted(
        path.resolve()
        for old_root in OLD_ROOTS
        if old_root.exists()
        for path in old_root.rglob("*")
        if path.is_file()
    )
    planned_sources = sorted(path.resolve() for path in old_paths)
    unplanned_sources = [
        str(path.relative_to(ROOT)) for path in current_files if path not in planned_sources
    ]
    return {
        "entries": len(entries),
        "missing_sources": missing_sources,
        "existing_targets": existing_targets,
        "duplicate_targets": duplicate_targets,
        "unplanned_sources": unplanned_sources,
        "valid": not (
            missing_sources or existing_targets or duplicate_targets or unplanned_sources
        ),
    }


def create_backup(entries: list[dict[str, str]]) -> None:
    if BACKUP_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite backup: {BACKUP_PATH}")
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        BACKUP_PATH, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for item in entries:
            source = inside_workspace(item["old_path"])
            archive.write(source, arcname=item["old_path"])
    with zipfile.ZipFile(BACKUP_PATH) as archive:
        bad_member = archive.testzip()
        expected = {item["old_path"].replace("\\", "/") for item in entries}
        actual = {name.rstrip("/") for name in archive.namelist() if not name.endswith("/")}
    if bad_member is not None or actual != expected:
        raise RuntimeError(
            f"Backup verification failed: bad_member={bad_member!r}, "
            f"expected={len(expected)}, actual={len(actual)}"
        )


def update_txt(path: Path) -> None:
    parts = path.relative_to(ROOT).parts
    chapter_folder = parts[1]
    lesson_folder = parts[2]
    text = path.read_text(encoding="utf-8")
    text, chapter_count = re.subn(
        r"(?m)^chapter:\s*.*$", f"chapter: {chapter_folder}", text, count=1
    )
    text, lesson_count = re.subn(
        r"(?m)^lesson:\s*.*$", f"lesson: {lesson_folder}", text, count=1
    )
    if chapter_count != 1 or lesson_count != 1:
        raise ValueError(f"Expected chapter/lesson metadata in {path}")
    path.write_text(text, encoding="utf-8", newline="\n")


def update_json(path: Path) -> None:
    parts = path.relative_to(ROOT).parts
    chapter_folder = parts[1]
    lesson_folder = parts[2]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["chapter"]["folder"] = chapter_folder
    data["lesson"]["folder"] = lesson_folder
    data["paired_question_file"] = path.with_suffix(".txt").name
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verify_normalized(entries: list[dict[str, str]]) -> dict[str, Any]:
    missing_targets: list[str] = []
    remaining_sources: list[str] = []
    invalid_pairs: list[dict[str, str]] = []
    for item in entries:
        source = inside_workspace(item["old_path"])
        target = inside_workspace(item["new_path"])
        if not target.is_file():
            missing_targets.append(item["new_path"])
        if source.exists():
            remaining_sources.append(item["old_path"])
    json_files = sorted((ROOT / "answers").rglob("*.json"))
    for json_path in json_files:
        txt_path = ROOT / "questions" / json_path.relative_to(ROOT / "answers").with_suffix(
            ".txt"
        )
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            txt = txt_path.read_text(encoding="utf-8")
            question = re.split(r"\r?\n---\s*\r?\n", txt, maxsplit=1)[0].strip()
            rel_parts = json_path.relative_to(ROOT).parts
            checks = {
                "txt_exists": txt_path.is_file(),
                "question_match": data.get("question") == question,
                "paired_filename": data.get("paired_question_file") == txt_path.name,
                "chapter_folder": data.get("chapter", {}).get("folder") == rel_parts[1],
                "lesson_folder": data.get("lesson", {}).get("folder") == rel_parts[2],
            }
            if not all(checks.values()):
                invalid_pairs.append(
                    {"path": str(json_path.relative_to(ROOT)), "checks": str(checks)}
                )
        except Exception as exc:  # verification must report any malformed record
            invalid_pairs.append(
                {"path": str(json_path.relative_to(ROOT)), "error": str(exc)}
            )
    return {
        "targets_expected": len(entries),
        "targets_present": len(entries) - len(missing_targets),
        "missing_targets": missing_targets,
        "remaining_sources": remaining_sources,
        "json_pairs_checked": len(json_files),
        "invalid_pairs": invalid_pairs,
        "valid": not (missing_targets or remaining_sources or invalid_pairs),
    }


def remove_empty_old_directories() -> None:
    for old_root in OLD_ROOTS:
        if not old_root.exists():
            continue
        directories = sorted(
            (path for path in old_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            directory.rmdir()
        old_root.rmdir()


def restore_backup_after_failure(moved: list[tuple[Path, Path]]) -> None:
    for source, target in reversed(moved):
        if target.exists() and not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(source))
    if BACKUP_PATH.exists():
        with zipfile.ZipFile(BACKUP_PATH) as archive:
            archive.extractall(ROOT)
    for root_name in ("questions", "answers", "source_documents"):
        normalized_root = ROOT / root_name
        if not normalized_root.exists():
            continue
        for directory in sorted(
            (path for path in normalized_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()
        if normalized_root.exists() and not any(normalized_root.iterdir()):
            normalized_root.rmdir()


def archive_phase_one_reports() -> None:
    copies = {
        ROOT / "reports" / "dataset_audit.md": ROOT
        / "reports"
        / "dataset_audit_phase1_pre_normalization.md",
        ROOT / "reports" / "dataset_audit.json": ROOT
        / "reports"
        / "dataset_audit_phase1_pre_normalization.json",
    }
    for source, target in copies.items():
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def apply(entries: list[dict[str, str]]) -> dict[str, Any]:
    validation = validate_plan(entries)
    if not validation["valid"]:
        raise RuntimeError(f"Normalization plan is unsafe: {validation}")
    archive_phase_one_reports()
    create_backup(entries)
    moved: list[tuple[Path, Path]] = []
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        for item in entries:
            source = inside_workspace(item["old_path"])
            target = inside_workspace(item["new_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            moved.append((source, target))
        for _, target in moved:
            if target.suffix.lower() == ".txt":
                update_txt(target)
            elif target.suffix.lower() == ".json":
                update_json(target)
        verification = verify_normalized(entries)
        if not verification["valid"]:
            raise RuntimeError(f"Post-normalization verification failed: {verification}")
        remove_empty_old_directories()
    except Exception:
        restore_backup_after_failure(moved)
        raise

    completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    result = {
        "status": "applied_and_verified",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "workspace": str(ROOT),
        "backup": str(BACKUP_PATH.relative_to(ROOT)).replace("\\", "/"),
        "entries": [
            {**item, "status": "applied"}
            for item in entries
        ],
        "preflight": validation,
        "verification": verification,
        "rollback": (
            "Use the backup and reverse old_path/new_path mapping. "
            "Do not overwrite newer data without an explicit recovery decision."
        ),
    }
    MAPPING_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely normalize HISEDU dataset paths.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the already-audited mapping. Without this flag, only validate it.",
    )
    args = parser.parse_args()
    entries = load_plan()
    if not args.apply:
        print(json.dumps(validate_plan(entries), ensure_ascii=False, indent=2))
        return 0
    result = apply(entries)
    print(
        json.dumps(
            {
                "status": result["status"],
                "entries": len(result["entries"]),
                "backup": result["backup"],
                "verification": result["verification"],
                "mapping": str(MAPPING_PATH.relative_to(ROOT)).replace("\\", "/"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
