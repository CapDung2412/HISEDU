import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HiseduApp, LoadingResult } from "@/components/HiseduApp";

const apiMocks = vi.hoisted(() => ({
  askTextQuestion: vi.fn(),
  askImageQuestion: vi.fn(),
  submitAnswerFeedback: vi.fn(),
  submitQuizAnswers: vi.fn()
}));

vi.mock("@/lib/api", () => apiMocks);

afterEach(() => {
  vi.useRealTimers();
});

describe("HiseduApp", () => {
  it("ưu tiên giai đoạn thật do backend gửi thay cho bộ đếm ước lượng", () => {
    render(
      <LoadingResult
        onCancel={vi.fn()}
        progress={{ stage: "generation", message: "Đang biên soạn câu trả lời từ sử liệu…" }}
      />
    );

    expect(screen.getByText("Đang biên soạn câu trả lời từ sử liệu…")).toBeInTheDocument();
    expect(screen.getByText("Đối chiếu").closest("li")).toHaveClass("loading-step--active");
  });

  it("cập nhật giai đoạn và thời gian chờ", () => {
    vi.useFakeTimers();
    render(<LoadingResult onCancel={vi.fn()} />);

    expect(screen.getByText("Đang đọc câu hỏi của em…")).toBeInTheDocument();
    expect(screen.getByText("Đã chờ 0 giây")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(8_000));
    expect(screen.getByText("Đang tìm nguồn liên quan…")).toBeInTheDocument();
    expect(screen.getByText("Đã chờ 8 giây")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(12_000));
    expect(screen.getByText("Đang đối chiếu sử liệu…")).toBeInTheDocument();
    expect(screen.getByText("Đã chờ 20 giây")).toBeInTheDocument();
  });

  it("hiển thị bước OCR riêng cho câu hỏi bằng ảnh", () => {
    render(<LoadingResult onCancel={vi.fn()} requestKind="image" />);

    expect(screen.getByText("Đang nhận dạng chữ trong ảnh…")).toBeInTheDocument();
    expect(screen.getByLabelText("Tiến trình dự kiến")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Đang nhận dạng chữ trong ảnh…" })).toHaveAttribute(
      "aria-busy",
      "true"
    );
  });

  it("hiện lời giải và nguồn ngay khi backend gửi kết quả lõi", async () => {
    const user = userEvent.setup();
    apiMocks.askTextQuestion.mockImplementation(
      (
        _question: string,
        signal?: AbortSignal,
        _onProgress?: unknown,
        onPartialResult?: (value: unknown) => void
      ) => {
        onPartialResult?.({
          request_id: "request-partial",
          question: "Cách mạng tư sản Anh bùng nổ vì sao?",
          answer: {
            summary: "Mâu thuẫn xã hội ngày càng gay gắt.",
            sections: [],
            key_points: ["Mâu thuẫn xã hội là một nguyên nhân quan trọng."],
            citation_ids: ["S1"]
          },
          mindmap: {
            title: "Cách mạng tư sản Anh",
            nodes: [
              {
                id: "root",
                label: "Cách mạng tư sản Anh",
                description: "Chủ đề",
                type: "root"
              }
            ],
            edges: []
          },
          sources: [
            {
              id: "S1",
              title: "Bài học Cách mạng tư sản Anh",
              publisher: "Dữ liệu HISEDU",
              type: "dataset",
              page_status: "unverified",
              supports: ["Nguyên nhân cách mạng"]
            }
          ],
          limitations: []
        });
        return new Promise((_resolve, reject) => {
          signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true }
          );
        });
      }
    );
    render(<HiseduApp />);

    await user.type(screen.getByLabelText("Câu hỏi của em"), "Cách mạng tư sản Anh bùng nổ vì sao?");
    await user.click(screen.getByRole("button", { name: /Hỏi HISEDU/i }));

    expect(await screen.findByText("Mâu thuẫn xã hội ngày càng gay gắt.")).toBeInTheDocument();
    expect(screen.getByText("Bài học Cách mạng tư sản Anh")).toBeInTheDocument();
    expect(screen.getByText("Lời giải đã sẵn sàng")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sơ đồ tư duy" })).not.toBeInTheDocument();
    expect(screen.queryByText("Xem để hiểu sâu hơn")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Hủy yêu cầu" }));
  });

  it("hủy AbortSignal của yêu cầu đang chạy", async () => {
    const user = userEvent.setup();
    let receivedSignal: AbortSignal | undefined;
    apiMocks.askTextQuestion.mockImplementation((_question: string, signal?: AbortSignal) => {
      receivedSignal = signal;
      return new Promise((_resolve, reject) => {
        signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true }
        );
      });
    });
    render(<HiseduApp />);

    await user.type(screen.getByLabelText("Câu hỏi của em"), "Cách mạng tư sản Anh bùng nổ vì sao?");
    await user.click(screen.getByRole("button", { name: /Hỏi HISEDU/i }));

    expect(receivedSignal).toBeDefined();
    expect(receivedSignal?.aborted).toBe(false);
    await user.click(screen.getByRole("button", { name: "Hủy yêu cầu" }));

    expect(receivedSignal?.aborted).toBe(true);
    expect(screen.getByText(/Đã dừng yêu cầu/)).toBeInTheDocument();
    expect(screen.queryByText("Đang đọc câu hỏi của em…")).not.toBeInTheDocument();
  });
});
