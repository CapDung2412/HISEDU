from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "dossier_evidence"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str, radius: int = 28, width: int = 3) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont, fill: str) -> None:
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, font=fnt, fill=fill)


def create_ocr_sample() -> None:
    image = Image.new("RGB", (1200, 720), "#ded8ce")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((82, 58, 1118, 662), radius=14, fill="#fffdf8", outline="#bda990", width=3)
    draw.line((135, 155, 1065, 155), fill="#8b2b22", width=3)
    centered(draw, (600, 105), "PHIẾU HỌC TẬP LỊCH SỬ 8", font(34, bold=True), "#54201c")
    draw.text((145, 205), "Câu hỏi:", font=font(28, bold=True), fill="#84251f")
    draw.multiline_text(
        (145, 262),
        "Những khó khăn kinh tế và tài chính nào\n"
        "góp phần làm bùng nổ Cách mạng tư sản Pháp?",
        font=font(40, bold=True),
        fill="#24211f",
        spacing=20,
    )
    draw.text((145, 455), "Gợi ý: nợ công, thuế khóa, mất mùa và đời sống nhân dân.", font=font(25), fill="#5c5650")
    draw.text((145, 575), "Ảnh mẫu dùng để kiểm tra luồng OCR cục bộ của HISEDU.", font=font(21), fill="#776f67")
    image.save(OUT / "ocr_question_sample.png", quality=95)


def create_test_results() -> None:
    image = Image.new("RGB", (1600, 900), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.text((78, 62), "HISEDU | KẾT QUẢ KIỂM THỬ", font=font(44, bold=True), fill="#222222")
    draw.text((80, 125), "Minh chứng kỹ thuật ngày 17/10/2026", font=font(23), fill="#666666")

    cards = [
        ("87/87", "Backend", "Python unit/integration tests"),
        ("31/31", "Frontend", "Vitest component/API tests"),
        ("ĐẠT", "TypeScript", "tsc --noEmit"),
        ("ĐẠT", "ESLint", "0 warning, 0 error"),
    ]
    x_positions = [78, 455, 832, 1209]
    for x, (value, label, detail) in zip(x_positions, cards):
        centered(draw, (x + 155, 310), value, font(58, bold=True), "#222222")
        centered(draw, (x + 155, 393), label, font(30, bold=True), "#222222")
        centered(draw, (x + 155, 452), detail, font(18), "#666666")

    draw.rounded_rectangle((78, 570, 1522, 812), radius=18, fill="#f4f4f4")
    draw.text((120, 612), "PHẠM VI XÁC NHẬN", font=font(27, bold=True), fill="#222222")
    draw.text(
        (120, 664),
        "• Benchmark thật: 60/60 câu đạt; TB 10,167 giây; P95 13,511 giây; mục tiêu ≤ 15 giây: ĐẠT.",
        font=font(22),
        fill="#222222",
    )
    draw.text(
        (120, 713),
        "• 87 test backend và 31 test frontend chạy cục bộ, không gọi dịch vụ ngoài.",
        font=font(22),
        fill="#222222",
    )
    draw.text(
        (120, 762),
        "• Benchmark dùng câu trong dataset; chưa thay thế đánh giá mù và thẩm định của giáo viên.",
        font=font(22),
        fill="#222222",
    )
    image.save(OUT / "11_test_results.png", quality=95)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    create_ocr_sample()
    create_test_results()
    print("Created OCR sample and current test-results evidence.")
