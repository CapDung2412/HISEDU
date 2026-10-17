from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
LESSONS = {
    1: "lesson_01",
    2: "lesson_04",
    3: "lesson_05",
    4: "lesson_10",
    5: "lesson_13",
    6: "lesson_14",
    7: "lesson_16",
}
MAX_QUESTION = {1: 9, 2: 9, 3: 9, 4: 9, 5: 8, 6: 9, 7: 7}
STOPWORDS = {
    "ai", "bi", "boi", "cac", "cho", "co", "cua", "da", "de", "den",
    "do", "duoc", "gi", "giua", "khi", "la", "lam", "mot", "nao",
    "nhung", "o", "ra", "sau", "su", "the", "thi", "trong", "tu",
    "va", "vao", "ve", "vi", "voi",
}


BASELINE = [
    (1, 1, 200, 33.839, True),
    (2, 1, 200, 22.900, True),
    (3, 1, 200, 15.339, True),
    (4, 1, 502, 43.380, False),
    (5, 1, 200, 32.415, True),
    (6, 1, 200, 35.458, True),
    (7, 1, 200, 17.824, True),
]


def read_pair(chapter: int, question_number: int) -> dict[str, Any]:
    lesson = LESSONS[chapter]
    stem = f"question_{question_number:03d}"
    question_path = ROOT / "questions" / f"chapter_{chapter:02d}" / lesson / f"{stem}.txt"
    answer_path = ROOT / "answers" / f"chapter_{chapter:02d}" / lesson / f"{stem}.json"
    question = question_path.read_text(encoding="utf-8").split("\n---", 1)[0].strip()
    reference = json.loads(answer_path.read_text(encoding="utf-8"))
    return {
        "chapter": chapter,
        "question_number": question_number,
        "question": question,
        "expected_id": reference["chunk_id"],
        "reference_answer": reference["answer"],
    }


def normalized_tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFD", text.casefold())
    folded = "".join(char for char in folded if unicodedata.category(char) != "Mn")
    return {
        token
        for token in re.findall(r"[a-z0-9]+", folded)
        if len(token) > 1 and token not in STOPWORDS
    }


def factual_coverage(reference: str, generated: str) -> tuple[float, bool]:
    reference_tokens = normalized_tokens(reference)
    generated_tokens = normalized_tokens(generated)
    coverage = (
        len(reference_tokens & generated_tokens) / len(reference_tokens)
        if reference_tokens
        else 0.0
    )
    reference_numbers = set(re.findall(r"\b\d{3,4}\b", reference))
    generated_numbers = set(re.findall(r"\b\d{3,4}\b", generated))
    return coverage, reference_numbers <= generated_numbers


def run_case(base_url: str, case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/questions/ask",
            json={"question": case["question"], "top_k": 3},
            timeout=240.0,
        )
        elapsed = time.perf_counter() - started
        if response.status_code != 200:
            return {
                **case,
                "status": response.status_code,
                "elapsed_seconds": round(elapsed, 3),
                "passed": False,
                "error": response.text[:1000],
            }
        data = response.json()
        sources = data.get("sources", [])
        source_ids = {str(source.get("id")) for source in sources}
        citation_ids = list(data.get("answer", {}).get("citation_ids", []))
        for section in data.get("answer", {}).get("sections", []):
            citation_ids.extend(section.get("citation_ids", []))
        citation_ids = [str(item) for item in citation_ids if item]
        citations_valid = bool(citation_ids) and all(
            citation_id in source_ids for citation_id in citation_ids
        )
        answer = data.get("answer", {})
        generated_parts = [answer.get("summary", "")]
        generated_parts.extend(answer.get("key_points", []))
        generated_parts.extend(
            section.get("content", "") for section in answer.get("sections", [])
        )
        generated_text = " ".join(str(part) for part in generated_parts if part)
        coverage, numbers_ok = factual_coverage(
            case["reference_answer"], generated_text
        )
        matched_ids = [str(item) for item in data.get("retrieval", {}).get("matched_ids", [])]
        expected_match = case["expected_id"] in matched_ids
        passed = (
            expected_match
            and bool(sources)
            and citations_valid
            and numbers_ok
            and coverage >= 0.32
        )
        return {
            **case,
            "status": response.status_code,
            "elapsed_seconds": round(elapsed, 3),
            "server_timing": response.headers.get("server-timing"),
            "expected_match": expected_match,
            "matched_ids": matched_ids,
            "source_count": len(sources),
            "source_types": sorted({str(source.get("type")) for source in sources}),
            "page_statuses": sorted(
                {str(source.get("page_status")) for source in sources}
            ),
            "citations_valid": citations_valid,
            "factual_coverage": round(coverage, 4),
            "reference_numbers_present": numbers_ok,
            "summary": answer.get("summary", ""),
            "key_points": answer.get("key_points", []),
            "passed": passed,
        }
    except Exception as exc:
        return {
            **case,
            "status": "ERROR",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def baseline_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for chapter, number, status, elapsed, passed in BASELINE:
        case = read_pair(chapter, number)
        results.append(
            {
                **case,
                "status": status,
                "elapsed_seconds": elapsed,
                "passed": passed,
                "origin": "previous_same_config_run",
                "note": (
                    "HTTP 200; expected record matched; citations valid; content matched reference"
                    if passed
                    else "Pinecone read timeout"
                ),
            }
        )
    return results


def build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(results, key=lambda item: (item["chapter"], item["question_number"]))
    elapsed = [float(item["elapsed_seconds"]) for item in ordered]
    successful = [item for item in ordered if item.get("status") == 200]
    passed = [item for item in ordered if item.get("passed")]
    sorted_elapsed = sorted(elapsed)
    p95_index = max(
        0,
        min(
            len(sorted_elapsed) - 1,
            int(0.95 * len(sorted_elapsed) + 0.9999) - 1,
        ),
    )
    average = sum(elapsed) / len(elapsed)
    return {
        "method": {
            "sample": (
                "60 stratified questions: chapters 1-4 have 9 each; chapter 5 has 8; "
                "chapter 6 has 9; chapter 7 has all 7 available in lesson 16"
            ),
            "pass_rule": (
                "HTTP 200, expected dataset record retrieved, non-empty valid citations, "
                "reference dates retained, and >=32% normalized reference-term coverage"
            ),
            "source_scope": (
                "Compared with paired JSON reference answers; textbook page metadata remains unverified"
            ),
            "warmup_excluded": False,
            "concurrency": 2,
        },
        "summary": {
            "questions_tested": len(ordered),
            "http_200": len(successful),
            "answers_passed": len(passed),
            "pass_rate_percent": round(100 * len(passed) / len(ordered), 2),
            "average_response_seconds": round(average, 3),
            "median_response_seconds": round(statistics.median(elapsed), 3),
            "p95_response_seconds": round(sorted_elapsed[p95_index], 3),
            "minimum_response_seconds": round(min(elapsed), 3),
            "maximum_response_seconds": round(max(elapsed), 3),
            "target_average_seconds": 15.0,
            "target_met": average <= 15.0,
        },
        "results": ordered,
    }


def save_report(path: Path, results: list[dict[str, Any]]) -> None:
    report = build_report(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--reuse-legacy-baseline",
        action="store_true",
        help="Reuse seven historical rows; omit for a clean current-code benchmark",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "local_benchmark_60_current.json",
    )
    args = parser.parse_args()
    start_question = 2 if args.reuse_legacy_baseline else 1
    cases = [
        read_pair(chapter, number)
        for chapter in range(1, 8)
        for number in range(start_question, MAX_QUESTION[chapter] + 1)
    ]
    results = baseline_results() if args.reuse_legacy_baseline else []
    if results:
        save_report(args.output, results)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_case, args.base_url, case): case for case in cases
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            save_report(args.output, results)
            print(
                f"[{completed:02d}/{len(cases)}] chapter={result['chapter']} "
                f"question={result['question_number']:03d} status={result['status']} "
                f"passed={result['passed']} seconds={result['elapsed_seconds']}",
                flush=True,
            )
    report = build_report(results)
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    print(f"REPORT={args.output.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
