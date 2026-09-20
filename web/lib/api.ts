import type { AskResponse, QuizSubmitResponse } from "@/lib/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(
  /\/$/,
  ""
);
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
// The first lesson request may also initialize the local CLIP text model.
// This is only a safety ceiling; successful responses return immediately.
const LESSON_REQUEST_TIMEOUT_MS = 90_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly requestId?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getMessage(body: unknown): string {
  if (!body || typeof body !== "object") return "Đã có lỗi xảy ra. Vui lòng thử lại.";
  const record = body as Record<string, unknown>;
  if (record.error && typeof record.error === "object") {
    const apiError = record.error as Record<string, unknown>;
    if (typeof apiError.message === "string") return apiError.message;
  }
  if (typeof record.detail === "string") return record.detail;
  if (typeof record.message === "string") return record.message;
  return "Đã có lỗi xảy ra. Vui lòng thử lại.";
}

function getRequestId(body: unknown): string | undefined {
  if (!body || typeof body !== "object") return undefined;
  const error = (body as Record<string, unknown>).error;
  if (!error || typeof error !== "object") return undefined;
  const requestId = (error as Record<string, unknown>).request_id;
  return typeof requestId === "string" ? requestId : undefined;
}

async function request<T>(
  path: string,
  init: RequestInit,
  timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers
    });
    const body: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      throw new ApiError(
        getMessage(body),
        response.status,
        response.headers.get("x-request-id") ?? getRequestId(body)
      );
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Yêu cầu mất quá nhiều thời gian. Em hãy thử lại nhé.");
    }
    throw new ApiError("Không thể kết nối đến máy chủ HISEDU. Hãy kiểm tra lại kết nối.");
  } finally {
    window.clearTimeout(timeout);
  }
}

export function askTextQuestion(question: string): Promise<AskResponse> {
  return request<AskResponse>(
    "/api/questions/ask",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 5 })
    },
    LESSON_REQUEST_TIMEOUT_MS
  );
}

export function askImageQuestion(file: File, question?: string): Promise<AskResponse> {
  const data = new FormData();
  data.append("file", file);
  if (question?.trim()) data.append("question", question.trim());
  data.append("top_k", "5");
  data.append("mode", "hybrid");

  return request<AskResponse>(
    "/api/questions/ask-image",
    {
      method: "POST",
      body: data
    },
    LESSON_REQUEST_TIMEOUT_MS
  );
}

export function submitQuizAnswers(
  quizId: string,
  answers: Record<string, string>
): Promise<QuizSubmitResponse> {
  return request<QuizSubmitResponse>(`/api/quizzes/${encodeURIComponent(quizId)}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers })
  });
}
