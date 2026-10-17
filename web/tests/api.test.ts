import { describe, expect, it, vi } from "vitest";
import {
  askTextQuestion,
  extractImageText,
  resetQuizAttempt,
  submitAnswerFeedback,
  submitQuizAnswer
} from "@/lib/api";

describe("API client", () => {
  it("nhận tiến trình thật từ SSE trước khi nhận kết quả cuối", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      ': connected\n\ndata: {"type":"progress","stage":"retrieval","message":"Đang tìm sử liệu…"}\n',
      '\ndata: {"type":"progress","stage":"generation","message":"Đang biên soạn…"}\n\n',
      'data: {"type":"partial_result","data":{"request_id":"request-stream","question":"Cách mạng tư sản Anh?","answer":{"summary":"Năm 1642.","sections":[],"key_points":[],"citation_ids":["S1"]},"mindmap":{"title":"Cách mạng Anh","nodes":[],"edges":[]},"sources":[],"limitations":[]}}\n\n',
      'data: {"type":"result","data":{"request_id":"request-stream"}}\n\n'
    ];
    const response = {
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/event-stream" }),
      body: new ReadableStream({
        start(controller) {
          chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
          controller.close();
        }
      })
    } as unknown as Response;
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const onProgress = vi.fn();
    const onPartialResult = vi.fn();

    const result = await askTextQuestion(
      "Cách mạng tư sản Anh?",
      undefined,
      onProgress,
      onPartialResult
    );

    expect(result.request_id).toBe("request-stream");
    expect(onProgress).toHaveBeenNthCalledWith(1, {
      stage: "retrieval",
      message: "Đang tìm sử liệu…"
    });
    expect(onProgress).toHaveBeenNthCalledWith(2, {
      stage: "generation",
      message: "Đang biên soạn…"
    });
    expect(onPartialResult).toHaveBeenCalledTimes(1);
    expect(onPartialResult.mock.calls[0][0]).toMatchObject({
      request_id: "request-stream",
      answer: { summary: "Năm 1642." }
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/questions/ask-stream",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("đọc đúng error envelope thống nhất của backend", async () => {
    const response = {
      ok: false,
      status: 429,
      headers: { get: vi.fn(() => null) },
      json: vi.fn().mockResolvedValue({
        error: {
          code: "rate_limited",
          message: "Em gửi câu hỏi hơi nhanh. Hãy chờ một chút nhé.",
          request_id: "request-123"
        }
      })
    } as unknown as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    await expect(askTextQuestion("Khởi nghĩa Lam Sơn diễn ra thế nào?")).rejects.toMatchObject({
      name: "ApiError",
      message: "Em gửi câu hỏi hơi nhanh. Hãy chờ một chút nhé.",
      status: 429,
      requestId: "request-123"
    });
  });

  it("chuyển AbortSignal của giao diện tới yêu cầu đang chạy", async () => {
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      const signal = init?.signal;
      signal?.addEventListener("abort", () => reject(signal.reason), { once: true });
    })));
    const controller = new AbortController();

    const pendingRequest = askTextQuestion("Cách mạng tư sản Anh?", controller.signal);
    controller.abort();

    await expect(pendingRequest).rejects.toMatchObject({
      name: "ApiError",
      message: "Yêu cầu đã được hủy."
    });
  });

  it("gửi báo sai với request id và nhận trạng thái chờ giáo viên", async () => {
    const response = {
      ok: true,
      status: 201,
      headers: { get: vi.fn(() => null) },
      json: vi.fn().mockResolvedValue({
        feedback_id: "feedback-123",
        status: "pending_teacher_review"
      })
    } as unknown as Response;
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      submitAnswerFeedback("answer-123", "not_helpful", "  Sai mốc thời gian.  ")
    ).resolves.toEqual({
      feedback_id: "feedback-123",
      status: "pending_teacher_review"
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/answers/answer-123/feedback",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ rating: "not_helpful", comment: "Sai mốc thời gian." })
      })
    );
  });

  it("gửi ảnh tới endpoint OCR riêng trước khi tìm kiếm", async () => {
    const response = {
      ok: true,
      status: 200,
      headers: { get: vi.fn(() => null) },
      json: vi.fn().mockResolvedValue({
        text: "Chiến thắng Bạch Đằng diễn ra năm nào?",
        line_count: 1,
        mean_score: 0.93,
        needs_review: false
      })
    } as unknown as Response;
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["image"], "question.png", { type: "image/png" });

    await expect(extractImageText(file)).resolves.toMatchObject({
      text: "Chiến thắng Bạch Đằng diễn ra năm nào?",
      needs_review: false
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/questions/ocr",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) })
    );
  });

  it("gửi từng đáp án thích ứng và có thể đặt lại lượt quiz", async () => {
    const answerPayload = {
      quiz_id: "quiz-1",
      result: {
        question_id: "q1",
        selected_option_id: "a",
        correct: true,
        correct_option_id: "a",
        explanation: "Đúng theo nguồn S1.",
        source_ids: ["S1"]
      },
      next_question: null,
      answered_count: 5,
      total_questions: 5,
      score_so_far: 5,
      completed: true,
      adaptive_message: "Em đã hoàn thành 5 câu."
    };
    const resetPayload = { quiz_id: "quiz-1", questions: [] };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: vi.fn(() => null) },
        json: vi.fn().mockResolvedValue(answerPayload)
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: vi.fn(() => null) },
        json: vi.fn().mockResolvedValue(resetPayload)
      } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(submitQuizAnswer("quiz-1", "q1", "a")).resolves.toEqual(answerPayload);
    await expect(resetQuizAttempt("quiz-1")).resolves.toEqual(resetPayload);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/quizzes/quiz-1/answer",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question_id: "q1", option_id: "a" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/quizzes/quiz-1/reset",
      expect.objectContaining({ method: "POST" })
    );
  });
});
