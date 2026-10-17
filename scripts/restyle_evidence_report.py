"""Apply a monochrome, borderless visual system to an existing HISEDU DOCX.

The script changes presentation only: decorative colors, cell shading, table
borders and paragraph rules are removed. Text, pagination, relationships and
embedded evidence are preserved.
"""

from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}

MUTED_COLORS = {"6B625D", "5B6573", "666666", "808080"}
DECORATIVE_COLORS = {
    "9B1C1C", "6F1515", "4B2E24", "C18B3F", "1F4E78", "1F3A5F", "172A3A"
}


def restyle_xml(data: bytes) -> bytes:
    root = etree.fromstring(data)

    for node in root.xpath(".//w:color", namespaces=NS):
        attr = f"{{{WORD_NS}}}val"
        value = (node.get(attr) or "").upper()
        node.set(attr, "666666" if value in MUTED_COLORS else "222222")

    # No colored panels or striped rows: hierarchy comes from typography and
    # whitespace only.
    for node in root.xpath(".//w:shd", namespaces=NS):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    for node in root.xpath(".//w:pBdr | .//w:tcBorders | .//w:tblBorders", namespaces=NS):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    for node in root.xpath(".//w:u", namespaces=NS):
        node.set(f"{{{WORD_NS}}}val", "none")

    # Explicitly suppress every edge so Word cannot reintroduce the built-in
    # Table Grid borders when opening the file on another computer.
    for table in root.xpath(".//w:tbl", namespaces=NS):
        properties = table.find(f"{{{WORD_NS}}}tblPr")
        if properties is None:
            properties = etree.Element(f"{{{WORD_NS}}}tblPr")
            table.insert(0, properties)
        borders = etree.SubElement(properties, f"{{{WORD_NS}}}tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            item = etree.SubElement(borders, f"{{{WORD_NS}}}{edge}")
            item.set(f"{{{WORD_NS}}}val", "nil")

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def restyle_report(source: Path, output: Path, test_image: Path | None = None) -> None:
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
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    data = restyle_xml(data)
                elif info.filename == "word/media/image10.png" and test_image is not None:
                    data = test_image.read_bytes()
                output_zip.writestr(info, data)
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_report(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("Gói DOCX bị lỗi CRC")
        document_xml = archive.read("word/document.xml").decode("utf-8")
        for legacy in DECORATIVE_COLORS:
            if legacy in document_xml:
                raise ValueError(f"Báo cáo còn màu trang trí cũ: {legacy}")
        if "w:pBdr" in document_xml or "w:shd" in document_xml:
            raise ValueError("Báo cáo còn đường kẻ hoặc nền trang trí")
        for required in ("60/60", "10,167 giây", "75/75"):
            if required not in document_xml:
                raise ValueError(f"Báo cáo thiếu số liệu bắt buộc: {required}")

    from docx import Document

    document = Document(path)
    if len(document.tables) != 4 or len(document.inline_shapes) != 10:
        raise ValueError("Cấu trúc bảng hoặc ảnh đã thay đổi ngoài dự kiến")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chuẩn hóa phong cách báo cáo HISEDU")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-image", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    test_image = args.test_image.resolve() if args.test_image else None
    restyle_report(args.source.resolve(), output, test_image)
    validate_report(output)
    print(f"PROFESSIONAL_REPORT={output}")


if __name__ == "__main__":
    main()
