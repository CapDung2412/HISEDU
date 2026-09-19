import { describe, expect, it, vi } from "vitest";
import { askTextQuestion } from "@/lib/api";

describe("API client", () => {
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
});
