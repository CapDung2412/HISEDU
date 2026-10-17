import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnswerFeedback } from "@/components/AnswerFeedback";

describe("AnswerFeedback", () => {
  it("xác nhận trước khi gửi báo sai để giáo viên kiểm tra", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue({
      feedback_id: "feedback-1",
      status: "pending_teacher_review"
    });
    render(<AnswerFeedback answerId="answer-1" onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Báo câu trả lời sai" }));
    expect(screen.getByText(/Không nhập họ tên/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Em thấy nội dung nào chưa đúng/), "Sai mốc năm 1642");
    await user.click(screen.getByRole("button", { name: "Gửi để giáo viên kiểm tra" }));

    expect(onSubmit).toHaveBeenCalledWith("answer-1", "not_helpful", "Sai mốc năm 1642");
    expect(await screen.findByText(/Đã gửi để giáo viên kiểm tra/)).toBeInTheDocument();
  });

  it("hiển thị lỗi và cho phép gửi lại", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockRejectedValue(new Error("Máy chủ chưa nhận được phản hồi."));
    render(<AnswerFeedback answerId="answer-2" onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Báo câu trả lời sai" }));
    await user.click(screen.getByRole("button", { name: "Gửi để giáo viên kiểm tra" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Máy chủ chưa nhận được phản hồi.");
    expect(screen.getByRole("button", { name: "Gửi để giáo viên kiểm tra" })).toBeEnabled();
  });
});
