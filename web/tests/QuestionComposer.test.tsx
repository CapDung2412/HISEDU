import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QuestionComposer } from "@/components/QuestionComposer";
import { extractImageText } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  extractImageText: vi.fn()
}));

describe("QuestionComposer", () => {
  it("yêu cầu câu hỏi hoặc ảnh trước khi gửi", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<QuestionComposer onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: /Hỏi HISEDU/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("nhập câu hỏi hoặc chọn một ảnh");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("gửi câu hỏi văn bản đã loại bỏ khoảng trắng thừa", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<QuestionComposer onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Câu hỏi của em"), "  Chiến thắng Bạch Đằng có ý nghĩa gì?  ");
    await user.click(screen.getByRole("button", { name: /Hỏi HISEDU/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      question: "Chiến thắng Bạch Đằng có ý nghĩa gì?",
      image: undefined
    });
  });

  it("từ chối tệp không phải JPG, PNG hoặc WebP", () => {
    const { container } = render(<QuestionComposer onSubmit={vi.fn()} />);
    const input = container.querySelector('input[type="file"]');
    const file = new File(["not-an-image"], "question.txt", { type: "text/plain" });

    fireEvent.change(input!, { target: { files: [file] } });

    expect(screen.getByRole("alert")).toHaveTextContent("JPG, PNG hoặc WebP");
  });

  it("cho phép sửa OCR rồi tìm kiếm bằng văn bản đã xác nhận", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    vi.mocked(extractImageText).mockResolvedValue({
      text: "Cách mạng tư sản Anh bùng nổ năm 1624?",
      line_count: 1,
      mean_score: 0.82,
      needs_review: false
    });
    const { container } = render(<QuestionComposer onSubmit={onSubmit} />);
    const input = container.querySelector('input[type="file"]');
    const file = new File(["image"], "question.png", { type: "image/png" });

    fireEvent.change(input!, { target: { files: [file] } });

    const preview = await screen.findByLabelText("Kiểm tra văn bản nhận diện");
    expect(preview).toHaveValue("Cách mạng tư sản Anh bùng nổ năm 1624?");
    expect(onSubmit).not.toHaveBeenCalled();

    await user.clear(preview);
    await user.type(preview, "Cách mạng tư sản Anh bùng nổ năm 1642?");
    await user.click(screen.getByRole("button", { name: /Hỏi HISEDU/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      question: "Cách mạng tư sản Anh bùng nổ năm 1642?"
    });
  });
});

