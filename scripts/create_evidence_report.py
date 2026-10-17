"""Create the HISEDU evidence report as a polished DOCX document.

This script intentionally does not call OpenAI, Pinecone, YouTube, or any other
external API.  It only assembles locally available text and screenshots.

Default output:
    reports/HISEDU_Bao_cao_minh_chung_2026-10-16.docx

Optional screenshots can be placed in ``reports/evidence_assets`` or supplied
with ``--assets-dir``. Missing screenshots are skipped and reported on stdout.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
except ImportError as exc:  # pragma: no cover - friendly CLI error
    raise SystemExit(
        "Thiếu python-docx. Cài bằng lệnh: "
        ".\\.venv\\Scripts\\python.exe -m pip install python-docx"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT / "reports" / "HISEDU_Bao_cao_minh_chung_2026-10-16.docx"
)
DEFAULT_ASSETS_DIR = REPO_ROOT / "reports" / "evidence_assets"
GITHUB_URL = "https://github.com/CapDung2412/HISEDU"
REPORT_DATE = "16/10/2026"

# Professional document palette: one navy accent, neutral text and gray fills.
# The legacy constant names are kept so the report layout remains stable while
# all visual elements use the same restrained design system.
RED = "1F4E78"
DARK_RED = "1F4E78"
BROWN = "222222"
GOLD = "1F4E78"
PALE_GOLD = "F2F4F7"
PARCHMENT = "F8FAFC"
LIGHT_RED = "F2F4F7"
LIGHT_GREEN = "F2F4F7"
MUTED = "666666"
WHITE = "FFFFFF"


@dataclass(frozen=True)
class EvidenceImage:
    filename: str
    caption: str
    demo_local: bool = False


EVIDENCE_IMAGES = {
    "dataset": EvidenceImage(
        "01_dataset_audit.png",
        "Kết quả kiểm tra cấu trúc và khả năng đọc bộ dữ liệu HISEDU.",
    ),
    "vector": EvidenceImage(
        "02_vector_pipeline.png",
        "Luồng đưa 327/327 bản ghi đã kiểm tra vào kho vector Pinecone.",
    ),
    "home": EvidenceImage(
        "05_home_current.png",
        "Giao diện chính HISEDU dành cho học sinh THCS.",
        True,
    ),
    "loading": EvidenceImage(
        "06_loading_sse.png",
        "Màn hình chờ hiển thị đúng giai đoạn xử lý qua SSE.",
        True,
    ),
    "ocr": EvidenceImage(
        "07_ocr_editable.png",
        "Văn bản OCR được hiển thị để học sinh kiểm tra và chỉnh sửa.",
        True,
    ),
    "partial": EvidenceImage(
        "08_partial_answer.png",
        "Câu trả lời và nguồn được hiển thị trước khi nội dung bổ trợ hoàn tất.",
        True,
    ),
    "mindmap": EvidenceImage(
        "09_mindmap.png",
        "Sơ đồ tư duy tương tác được tổ chức theo bốn nhóm kiến thức chính.",
        True,
    ),
    "video": EvidenceImage(
        "09_video.png",
        "Video đúng chủ đề được lọc theo kênh tin cậy và channelId đã xác minh.",
        True,
    ),
    "quiz": EvidenceImage(
        "10_quiz_adaptive.png",
        "Quiz thích ứng hiển thị mức độ, phản hồi, giải thích và nguồn.",
        True,
    ),
    "tests": EvidenceImage(
        "11_test_results.png",
        "Kết quả kiểm thử tự động của backend và frontend.",
    ),
}


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, *, top: int = 90, start: int = 110,
                     bottom: int = 90, end: int = 110) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in {
        "top": top,
        "start": start,
        "bottom": bottom,
        "end": end,
    }.items():
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_text(cell, text: str, *, bold: bool = False,
                  color: str = BROWN, size: float = 10.5) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_cell_margins(cell)


def add_page_field(paragraph, field_name: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = field_name
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instruction, separate, text, end):
        run._r.append(element)


def add_hyperlink(paragraph, text: str, url: str,
                  color: str = RED, underline: bool = True) -> None:
    part = paragraph.part
    relationship_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    run_properties = OxmlElement("w:rPr")
    color_element = OxmlElement("w:color")
    color_element.set(qn("w:val"), color)
    run_properties.append(color_element)
    if underline:
        underline_element = OxmlElement("w:u")
        underline_element.set(qn("w:val"), "single")
        run_properties.append(underline_element)
    run.append(run_properties)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_bottom_border(paragraph, color: str = GOLD, size: str = "10") -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    borders = paragraph_properties.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        paragraph_properties.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "5")
    bottom.set(qn("w:color"), color)
    borders.append(bottom)


def configure_document(document: Document) -> None:
    section = document.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)
    section.header_distance = Cm(0.8)
    section.footer_distance = Cm(0.8)

    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor.from_string(BROWN)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(6)

    heading_specs = {
        "Title": (22, DARK_RED, 10),
        "Subtitle": (12, MUTED, 6),
        "Heading 1": (16, DARK_RED, 10),
        "Heading 2": (13.5, RED, 7),
        "Heading 3": (12, BROWN, 5),
    }
    for style_name, (size, color, before) in heading_specs.items():
        style = styles[style_name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = style_name != "Subtitle"
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(5)

    core = document.core_properties
    core.title = "HISEDU – Báo cáo minh chứng sản phẩm"
    core.subject = "Minh chứng sản phẩm giáo dục Lịch sử lớp 8"
    core.author = "Nhóm dự án HISEDU"
    core.keywords = "HISEDU, Lịch sử lớp 8, OCR, SSE, Pinecone, mindmap, quiz"

    header = section.header
    header_paragraph = header.paragraphs[0]
    header_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header_paragraph.add_run("HISEDU  •  HỒ SƠ MINH CHỨNG")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string(RED)
    add_bottom_border(header_paragraph, GOLD, "6")

    footer = section.footer
    footer_paragraph = footer.paragraphs[0]
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_paragraph.add_run("HISEDU  |  Trang ")
    footer_run.font.name = "Times New Roman"
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor.from_string(MUTED)
    add_page_field(footer_paragraph, "PAGE")
    footer_paragraph.add_run(" / ")
    add_page_field(footer_paragraph, "NUMPAGES")


def add_title_page(document: Document) -> None:
    document.add_paragraph()
    label = document.add_paragraph()
    label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = label.add_run("TRỢ LÝ HỌC TẬP MÔN LỊCH SỬ")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor.from_string(GOLD)

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("HISEDU")

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("BÁO CÁO MINH CHỨNG SẢN PHẨM")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor.from_string(BROWN)
    add_bottom_border(subtitle, GOLD, "14")

    scope = document.add_paragraph()
    scope.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = scope.add_run("Phạm vi nội dung: Lịch sử lớp 8")
    run.italic = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor.from_string(MUTED)

    document.add_paragraph()
    info_table = document.add_table(rows=0, cols=2)
    info_table.style = "Table Grid"
    project_rows = [
        ("Tên sản phẩm", "HISEDU – Trợ lý học tập môn Lịch sử"),
        ("Đối tượng", "Học sinh THCS; nội dung minh chứng tập trung lớp 8"),
        ("Mã nguồn", GITHUB_URL),
        ("Ngày lập báo cáo", REPORT_DATE),
        ("Phiên bản", "MVP local / hồ sơ minh chứng"),
    ]
    for label_text, value in project_rows:
        cells = info_table.add_row().cells
        set_cell_text(cells[0], label_text, bold=True, color=DARK_RED)
        shade_cell(cells[0], PALE_GOLD)
        if label_text == "Mã nguồn":
            cells[1].text = ""
            add_hyperlink(cells[1].paragraphs[0], value, value)
            set_cell_margins(cells[1])
        else:
            set_cell_text(cells[1], value)

    note = document.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.space_before = Pt(18)
    run = note.add_run(
        "Tài liệu không chứa khóa API, tệp .env hoặc thông tin cá nhân."
    )
    run.italic = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor.from_string(MUTED)
    document.add_page_break()


def add_callout(document: Document, title: str, body: str,
                *, fill: str = PALE_GOLD, accent: str = RED) -> None:
    table = document.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    shade_cell(cell, fill)
    set_cell_margins(cell, top=130, start=160, bottom=130, end=160)
    cell.text = ""
    paragraph = cell.paragraphs[0]
    title_run = paragraph.add_run(f"{title}\n")
    title_run.bold = True
    title_run.font.name = "Times New Roman"
    title_run.font.size = Pt(11)
    title_run.font.color.rgb = RGBColor.from_string(accent)
    body_run = paragraph.add_run(body)
    body_run.font.name = "Times New Roman"
    body_run.font.size = Pt(10.5)
    body_run.font.color.rgb = RGBColor.from_string(BROWN)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def add_bullets(document: Document, items: Iterable[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.left_indent = Cm(0.65)
        paragraph.paragraph_format.first_line_indent = Cm(-0.3)
        paragraph.add_run(item)


def add_metric_table(document: Document) -> None:
    table = document.add_table(rows=2, cols=4)
    table.style = "Table Grid"
    labels = ("Dataset", "Pinecone", "Benchmark", "Thời gian TB")
    values = ("327/327", "327/327", "60/60", "10,167 giây")
    for column, label in enumerate(labels):
        set_cell_text(table.cell(0, column), label, bold=True, color=WHITE, size=10)
        shade_cell(table.cell(0, column), RED)
        set_cell_text(table.cell(1, column), values[column], bold=True,
                      color=DARK_RED, size=13)
        shade_cell(table.cell(1, column), PARCHMENT)
        table.cell(1, column).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        table.cell(0, column).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_evidence_index(document: Document) -> None:
    document.add_heading("MỤC LỤC MINH CHỨNG", level=1)
    rows = [
        ("MC01", "Kiểm tra dataset", "01_dataset_audit.png"),
        ("MC02", "Pipeline vector và Pinecone", "02_vector_pipeline.png"),
        ("MC03", "Giao diện HISEDU", "05_home_current.png"),
        ("MC04", "Tốc độ: SSE và kết quả từng phần", "06_loading_sse.png; 08_partial_answer.png"),
        ("MC05", "OCR cho phép chỉnh sửa", "07_ocr_editable.png"),
        ("MC06", "Video và mindmap", "09_mindmap.png; 09_video.png"),
        ("MC07", "Quiz thích ứng", "10_quiz_adaptive.png"),
        ("MC08", "Kết quả kiểm thử và benchmark", "11_test_results.png"),
    ]
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    headers = ("Mã", "Nội dung", "Tệp minh chứng")
    for index, header in enumerate(headers):
        set_cell_text(table.cell(0, index), header, bold=True, color=WHITE)
        shade_cell(table.cell(0, index), BROWN)
    set_repeat_table_header(table.rows[0])
    for evidence_id, content, filename in rows:
        cells = table.add_row().cells
        set_cell_text(cells[0], evidence_id, bold=True, color=RED)
        set_cell_text(cells[1], content)
        set_cell_text(cells[2], filename, color=MUTED, size=9.5)
        if len(table.rows) % 2 == 0:
            for cell in cells:
                shade_cell(cell, PARCHMENT)


def locate_image(image: EvidenceImage, assets_dir: Path) -> Path | None:
    search_directories = (
        assets_dir,
        DEFAULT_ASSETS_DIR,
        REPO_ROOT / "reports" / "assets",
        REPO_ROOT / "reports",
        REPO_ROOT / "evidence",
        REPO_ROOT,
    )
    seen: set[Path] = set()
    for directory in search_directories:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidate = resolved / image.filename
        if candidate.is_file():
            return candidate
    return None


def add_evidence_image(document: Document, image: EvidenceImage,
                       assets_dir: Path, figure_number: int) -> bool:
    path = locate_image(image, assets_dir)
    if path is None:
        return False
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(path), width=Cm(15.3))

    caption = document.add_paragraph()
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.keep_with_next = True
    caption_text = f"Hình {figure_number}. {image.caption}"
    if image.demo_local:
        caption_text += " [Dữ liệu demo cục bộ; không gọi API thật.]"
    run = caption.add_run(caption_text)
    run.italic = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor.from_string(MUTED)
    return True


def add_body(document: Document, assets_dir: Path) -> list[str]:
    missing_images: list[str] = []
    figure_number = 1

    def insert_image(key: str) -> None:
        nonlocal figure_number
        image = EVIDENCE_IMAGES[key]
        if add_evidence_image(document, image, assets_dir, figure_number):
            figure_number += 1
        else:
            missing_images.append(image.filename)

    document.add_heading("1. Tổng quan và phạm vi", level=1)
    document.add_paragraph(
        "HISEDU là trợ lý học tập môn Lịch sử dành cho học sinh THCS. "
        "Hệ thống hỗ trợ đặt câu hỏi bằng văn bản hoặc hình ảnh, truy xuất "
        "dữ liệu đã lập chỉ mục, trình bày câu trả lời có nguồn và tạo nội "
        "dung hỗ trợ ghi nhớ. Báo cáo này tập trung vào nội dung Lịch sử lớp 8."
    )
    add_metric_table(document)
    add_callout(
        document,
        "Nguyên tắc minh chứng",
        "Số liệu trong báo cáo phản ánh lần kiểm tra cục bộ đã ghi nhận. "
        "Ảnh 06–10 sử dụng dữ liệu demo cục bộ và không gọi OpenAI, Pinecone "
        "hoặc YouTube API thật trong lúc chụp minh chứng.",
    )
    insert_image("home")

    add_evidence_index(document)

    document.add_heading("2. Dataset và kho vector", level=1)
    document.add_heading("2.1. Kiểm tra dataset", level=2)
    document.add_paragraph(
        "Quy trình kiểm tra ghi nhận 327/327 bản ghi dữ liệu có thể đọc và "
        "đạt yêu cầu cấu trúc của bộ dữ liệu hiện tại. Các tệp câu hỏi và "
        "JSON kết quả được ghép theo quy ước đường dẫn an toàn, giúp giảm lỗi "
        "khi xử lý trên Windows hoặc khi triển khai sang môi trường khác."
    )
    add_bullets(
        document,
        (
            "Kiểm tra khả năng đọc tệp và cấu trúc JSON.",
            "Đối chiếu cặp câu hỏi – kết quả theo khóa và đường dẫn tương ứng.",
            "Phát hiện dữ liệu thiếu, bản ghi trùng hoặc đường dẫn không hợp lệ.",
            "Không suy đoán số trang sách giáo khoa khi metadata nguồn không cung cấp.",
        ),
    )
    insert_image("dataset")

    document.add_heading("2.2. Pinecone và pipeline vector", level=2)
    document.add_paragraph(
        "Kết quả đối chiếu cho thấy 327/327 bản ghi của bộ dữ liệu đã được "
        "đưa vào chỉ mục Pinecone trong lần kiểm tra ghi nhận. Metadata đi "
        "kèm vector được dùng để truy vết nội dung nguồn khi trả lời."
    )
    insert_image("vector")

    document.add_heading("3. Kết quả benchmark cục bộ", level=1)
    document.add_paragraph(
        "Bộ chạy thử cục bộ ngày 16/10/2026 ghi nhận 60/60 câu đạt tiêu chí "
        "(100%), với thời gian phản hồi trung bình 10,167 giây; trung vị "
        "9,710 giây; P95 13,511 giây; nhanh nhất 7,109 giây và chậm nhất "
        "16,442 giây. Mục tiêu thời gian trung bình không quá 15 giây đã đạt."
    )
    add_callout(
        document,
        "CẢNH BÁO VỀ PHƯƠNG PHÁP ĐÁNH GIÁ",
        "60/60 không phải kết quả đánh giá mù độc lập. Lượt đo dùng 60 câu "
        "nguyên văn trong dataset, hai luồng đồng thời và có tính thời gian "
        "khởi động. Vì vậy số liệu không đại diện cho ảnh/OCR, câu diễn đạt "
        "mới qua CLIP/Pinecone hoặc mọi điều kiện mạng. Cần bổ sung bộ câu hỏi "
        "mới do người ngoài nhóm xây dựng và chấm đối chiếu nguồn.",
        fill=LIGHT_RED,
        accent=DARK_RED,
    )

    document.add_heading("4. Năm nội dung cải tiến", level=1)
    document.add_heading("4.1. Tốc độ – SSE và kết quả từng phần", level=2)
    document.add_paragraph(
        "Backend truyền trạng thái xử lý bằng Server-Sent Events (SSE). Khi "
        "nội dung lõi hoàn tất, câu trả lời và nguồn được gửi về trước; video, "
        "mindmap và quiz tiếp tục hoàn thiện. Cơ chế heartbeat, hủy yêu cầu và "
        "xử lý lỗi giúp giao diện không bị hiểu nhầm là đứng yên."
    )
    add_bullets(
        document,
        (
            "Hiển thị đúng giai đoạn đang truy xuất hoặc tổng hợp.",
            "Giảm thời gian chờ cảm nhận nhờ trả kết quả quan trọng trước.",
            "Giữ API JSON cũ để tương thích với luồng hiện có.",
        ),
    )
    insert_image("loading")
    insert_image("partial")

    document.add_heading("4.2. Nhận diện ảnh – OCR có thể chỉnh sửa", level=2)
    document.add_paragraph(
        "Ảnh câu hỏi được OCR cục bộ bằng PaddleOCR. Văn bản nhận diện, độ tin "
        "cậy và số dòng được hiển thị để học sinh xem lại. Học sinh có thể sửa "
        "nội dung trước khi xác nhận tra cứu, tránh đưa lỗi OCR trực tiếp vào "
        "pipeline tìm kiếm."
    )
    insert_image("ocr")

    document.add_heading("4.3. Video – lọc đúng kênh bằng channelId", level=2)
    document.add_paragraph(
        "Video được xếp hạng theo chủ đề, tiêu đề và mô tả; sau đó kiểm tra "
        "channelId thay vì chỉ dựa vào tên hiển thị. Danh sách cho phép gồm "
        "EZ Sử, HTV, VTV, Sử Lược – Tóm Tắt Lịch Sử và Dòng Máu Việt. "
        "Kết quả trùng hoặc không đủ liên quan bị loại bỏ."
    )

    document.add_heading("4.4. Mindmap – bốn nhóm kiến thức", level=2)
    document.add_paragraph(
        "Sơ đồ tư duy tổ chức nội dung thành bốn nhánh chính: Nguyên nhân, "
        "Diễn biến, Nhân vật và Ý nghĩa. Người học có thể mở hoặc thu gọn từng "
        "nhánh, chọn nút để xem chi tiết, phóng to, thu nhỏ, căn vừa khung và "
        "chuyển sang toàn màn hình."
    )
    insert_image("mindmap")
    insert_image("video")

    document.add_heading("4.5. Quiz thích ứng", level=2)
    document.add_paragraph(
        "Quiz hiển thị từng câu ở mức Nhớ, Hiểu hoặc Vận dụng. Sau mỗi lựa "
        "chọn, hệ thống cho biết đúng/sai, giải thích và nguồn. Trả lời đúng sẽ "
        "ưu tiên câu khó hơn; trả lời sai sẽ ưu tiên câu nền tảng để củng cố."
    )
    insert_image("quiz")

    document.add_heading("5. Kết quả kiểm thử kỹ thuật", level=1)
    test_rows = [
        ("Backend", "75/75", "Đạt"),
        ("Frontend", "29/29", "Đạt"),
        ("TypeScript", "Kiểm tra kiểu", "Đạt"),
        ("ESLint", "Kiểm tra mã nguồn frontend", "Đạt"),
    ]
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for index, header in enumerate(("Hạng mục", "Phạm vi", "Kết quả")):
        set_cell_text(table.cell(0, index), header, bold=True, color=WHITE)
        shade_cell(table.cell(0, index), BROWN)
    set_repeat_table_header(table.rows[0])
    for index, row_data in enumerate(test_rows):
        cells = table.add_row().cells
        for column, value in enumerate(row_data):
            color = RED if column == 2 else BROWN
            set_cell_text(cells[column], value, bold=column == 2, color=color)
        if index % 2 == 0:
            for cell in cells:
                shade_cell(cell, PARCHMENT)
    insert_image("tests")

    document.add_heading("6. Giới hạn và việc cần bổ sung", level=1)
    add_bullets(
        document,
        (
            "Thực hiện đánh giá mù với bộ câu hỏi mới, không lấy trực tiếp từ kho dữ liệu.",
            "Mời giáo viên Lịch sử đối chiếu độ đúng, độ đủ và chất lượng nguồn của câu trả lời.",
            "Bổ sung số trang SGK chỉ khi bản ghi nguồn có metadata đáng tin cậy; tuyệt đối không tự tạo số trang.",
            "Benchmark mới đã báo cáo trung vị và P95; vẫn cần đo trên nhiều thiết bị, điều kiện mạng, câu diễn đạt mới và ảnh OCR.",
            "OCR vẫn phụ thuộc độ rõ, độ nghiêng và ánh sáng của ảnh; học sinh cần xác nhận văn bản trước khi gửi.",
            "Kết quả video phụ thuộc trạng thái mạng, hạn mức YouTube API và video còn công khai trên kênh cho phép.",
            "Mở rộng nội dung sang lớp 6, 7 và 9 sau khi hoàn tất kiểm duyệt dữ liệu lớp 8.",
        ),
    )

    document.add_heading("7. Hướng dẫn liên kết và nộp minh chứng", level=1)
    document.add_heading("7.1. Liên kết mã nguồn", level=2)
    paragraph = document.add_paragraph("Repository GitHub: ")
    add_hyperlink(paragraph, GITHUB_URL, GITHUB_URL)
    add_bullets(
        document,
        (
            "Nếu repository để riêng tư, cấp quyền cho tài khoản chấm hoặc chuyển sang công khai theo quy định cuộc thi.",
            "Không commit tệp .env, API key, mật khẩu, dữ liệu cá nhân hoặc tệp cache chứa bí mật.",
        ),
    )

    document.add_heading("7.2. Liên kết Google Drive/Docs", level=2)
    document.add_paragraph(
        "URL minh chứng cần bổ sung trước khi nộp: "
        "[DÁN LIÊN KẾT GOOGLE DRIVE/DOCS TẠI ĐÂY]"
    )
    add_bullets(
        document,
        (
            "Tải báo cáo DOCX hoặc bản PDF xuất từ báo cáo lên Google Drive.",
            "Đặt quyền “Bất kỳ ai có đường liên kết” ở chế độ “Người xem”.",
            "Mở cửa sổ ẩn danh để xác nhận liên kết hoạt động và không yêu cầu đăng nhập.",
            "Nếu có video demo, đặt trong cùng thư mục và liên kết từ trang đầu của tài liệu nộp.",
        ),
    )

    document.add_heading("8. Kết luận", level=1)
    document.add_paragraph(
        "Năm cải tiến giúp HISEDU phản hồi rõ ràng hơn, nhận diện ảnh an toàn "
        "hơn, lựa chọn video chính xác hơn, tổ chức kiến thức có hệ thống và "
        "hỗ trợ học sinh tự kiểm tra mức độ hiểu bài. Các số liệu trong báo cáo "
        "được trình bày kèm giới hạn để bảo đảm minh chứng có thể kiểm tra và "
        "không vượt quá phạm vi kết quả thực tế."
    )
    add_callout(
        document,
        "Xác nhận trước khi nộp",
        "Kiểm tra lại URL GitHub, URL Google Drive/Docs, quyền xem, ảnh minh "
        "chứng và việc che toàn bộ khóa bí mật. Không ghi số trang SGK nếu "
        "chưa có nguồn dữ liệu xác thực.",
        fill=LIGHT_GREEN,
        accent=DARK_RED,
    )

    return missing_images


def build_report(output_path: Path, assets_dir: Path) -> list[str]:
    document = Document()
    configure_document(document)
    add_title_page(document)
    missing_images = add_body(document, assets_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return missing_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sinh báo cáo minh chứng HISEDU dạng DOCX."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Tệp DOCX đầu ra (mặc định: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=DEFAULT_ASSETS_DIR,
        help=f"Thư mục chứa ảnh minh chứng (mặc định: {DEFAULT_ASSETS_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output.resolve()
    assets_dir = args.assets_dir.resolve()
    missing_images = build_report(output_path, assets_dir)

    print(f"Đã tạo báo cáo: {output_path}")
    if missing_images:
        print("Các ảnh chưa tồn tại nên chưa được chèn:")
        for filename in missing_images:
            print(f"  - {filename}")
    else:
        print("Đã chèn đủ toàn bộ ảnh minh chứng dự kiến.")


if __name__ == "__main__":
    main()
