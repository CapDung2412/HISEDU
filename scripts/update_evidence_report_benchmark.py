from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DCTERMS_NS = "http://purl.org/dc/terms/"
NS = {"w": W_NS, "dcterms": DCTERMS_NS}


def qn(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def replace_paragraph_text(paragraph: etree._Element, value: str) -> None:
    text_nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not text_nodes:
        run = etree.SubElement(paragraph, qn(W_NS, "r"))
        text_node = etree.SubElement(run, qn(W_NS, "t"))
        text_nodes = [text_node]
    text_nodes[0].text = value
    for text_node in text_nodes[1:]:
        text_node.text = ""


def insert_scope_note(after: etree._Element, value: str) -> None:
    paragraph = etree.Element(qn(W_NS, "p"))
    properties = after.find(qn(W_NS, "pPr"))
    if properties is not None:
        paragraph.append(copy.deepcopy(properties))

    label_run = etree.SubElement(paragraph, qn(W_NS, "r"))
    label_properties = etree.SubElement(label_run, qn(W_NS, "rPr"))
    etree.SubElement(label_properties, qn(W_NS, "b"))
    label = etree.SubElement(label_run, qn(W_NS, "t"))
    label.text = "Phạm vi phép đo: "

    body_run = etree.SubElement(paragraph, qn(W_NS, "r"))
    body = etree.SubElement(body_run, qn(W_NS, "t"))
    body.text = value
    after.addnext(paragraph)


def format_seconds(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def update_document_xml(xml_bytes: bytes, summary: dict[str, object]) -> bytes:
    root = etree.fromstring(xml_bytes)
    questions = int(summary["questions_tested"])
    passed = int(summary["answers_passed"])
    average = format_seconds(float(summary["average_response_seconds"]))
    median = format_seconds(float(summary["median_response_seconds"]))
    p95 = format_seconds(float(summary["p95_response_seconds"]))
    minimum = format_seconds(float(summary["minimum_response_seconds"]))
    maximum = format_seconds(float(summary["maximum_response_seconds"]))
    percentage = float(summary["pass_rate_percent"])

    benchmark_paragraph: etree._Element | None = None
    replaced_limit = False
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        text = paragraph_text(paragraph)
        if text.startswith("Bộ chạy thử cục bộ ghi nhận"):
            replace_paragraph_text(
                paragraph,
                (
                    f"Bộ chạy thử cục bộ ngày 16/10/2026 ghi nhận {passed}/{questions} "
                    f"câu đạt tiêu chí ({percentage:.0f}%), với thời gian phản hồi "
                    f"trung bình {average} giây; trung vị {median} giây; P95 {p95} "
                    f"giây; nhanh nhất {minimum} giây và chậm nhất {maximum} giây. "
                    "Mục tiêu thời gian trung bình không quá 15 giây đã đạt."
                ),
            )
            benchmark_paragraph = paragraph
        elif text.startswith("Đo lại thời gian phản hồi trên nhiều thiết bị"):
            replace_paragraph_text(
                paragraph,
                (
                    "Benchmark mới đã báo cáo trung vị và P95; vẫn cần đo trên "
                    "nhiều thiết bị, điều kiện mạng, câu diễn đạt mới và ảnh OCR."
                ),
            )
            replaced_limit = True
        elif text == "Kết quả kiểm thử":
            replace_paragraph_text(paragraph, "Kết quả kiểm thử và benchmark")

    replacements = {
        "59/60": f"{passed}/{questions}",
        "23,321 giây": f"{average} giây",
        "74/74": "75/75",
    }
    for text_node in root.xpath(".//w:t", namespaces=NS):
        if text_node.text in replacements:
            text_node.text = replacements[text_node.text]

    if benchmark_paragraph is None:
        raise ValueError("Không tìm thấy đoạn benchmark cũ trong báo cáo")
    if not replaced_limit:
        raise ValueError("Không tìm thấy đoạn giới hạn đo thời gian trong báo cáo")
    insert_scope_note(
        benchmark_paragraph,
        (
            "60 câu nguyên văn trong dataset, chạy hai luồng đồng thời và có "
            "tính thời gian khởi động. Kết quả không đại diện cho ảnh/OCR, câu "
            "diễn đạt mới qua CLIP/Pinecone hoặc mọi điều kiện mạng; đây chưa "
            "phải đánh giá mù độc lập."
        ),
    )
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def update_core_properties(xml_bytes: bytes) -> bytes:
    root = etree.fromstring(xml_bytes)
    modified = root.find(qn(DCTERMS_NS, "modified"))
    if modified is not None:
        modified.text = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def update_report(
    source: Path,
    benchmark: Path,
    test_image: Path,
    output: Path,
) -> None:
    payload = json.loads(benchmark.read_text(encoding="utf-8"))
    summary = payload["summary"]
    if (
        int(summary["questions_tested"]) != 60
        or int(summary["http_200"]) != 60
        or int(summary["answers_passed"]) != 60
        or not bool(summary["target_met"])
    ):
        raise ValueError("Benchmark chưa đủ điều kiện 60/60 và mục tiêu 15 giây")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output.parent, suffix=".docx", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(source, "r") as source_zip, zipfile.ZipFile(
            temporary_path, "w"
        ) as output_zip:
            output_zip.comment = source_zip.comment
            for info in source_zip.infolist():
                data = source_zip.read(info.filename)
                if info.filename == "word/document.xml":
                    data = update_document_xml(data, summary)
                elif info.filename == "docProps/core.xml":
                    data = update_core_properties(data)
                elif info.filename == "word/media/image10.png":
                    data = test_image.read_bytes()
                output_zip.writestr(info, data)
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_report(path: Path, test_image: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("Gói DOCX bị lỗi CRC")
        document_xml = archive.read("word/document.xml").decode("utf-8")
        required = (
            "60/60",
            "10,167 giây",
            "trung vị 9,710 giây",
            "P95 13,511 giây",
            "75/75",
            "Kết quả kiểm thử và benchmark",
            "Phạm vi phép đo:",
        )
        for value in required:
            if value not in document_xml:
                raise ValueError(f"Báo cáo thiếu nội dung bắt buộc: {value}")
        for stale in ("59/60", "23,321 giây", "74/74"):
            if stale in document_xml:
                raise ValueError(f"Báo cáo còn số liệu cũ: {stale}")
        embedded = archive.read("word/media/image10.png")
        if hashlib.sha256(embedded).digest() != hashlib.sha256(
            test_image.read_bytes()
        ).digest():
            raise ValueError("Ảnh kết quả kiểm thử chưa được cập nhật")

    from docx import Document

    document = Document(path)
    if len(document.inline_shapes) != 10:
        raise ValueError("Số ảnh trong báo cáo đã thay đổi ngoài dự kiến")
    if len(document.tables) != 4:
        raise ValueError("Số bảng trong báo cáo đã thay đổi ngoài dự kiến")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cập nhật benchmark trong báo cáo HISEDU")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--test-image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    test_image = args.test_image.resolve()
    update_report(
        args.source.resolve(),
        args.benchmark.resolve(),
        test_image,
        output,
    )
    validate_report(output, test_image)
    print(f"UPDATED_REPORT={output}")


if __name__ == "__main__":
    main()
