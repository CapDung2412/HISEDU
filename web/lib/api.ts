import type {
  AnswerFeedbackRating,
  AnswerFeedbackResponse,
  AskResponse,
  LessonProgressEvent,
  OcrPreviewResponse,
  PartialLessonResponse,
  QuizAnswerResponse,
  QuizData,
  QuizSubmitResponse
} from "@/lib/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(
  /\/$/,
  ""
);
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
const OCR_REQUEST_TIMEOUT_MS = 60_000;
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
  timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
  externalSignal?: AbortSignal
): Promise<T> {
  const controller = new AbortController();
  let didTimeOut = false;
  const timeout = window.setTimeout(() => {
    didTimeOut = true;
    controller.abort();
  }, timeoutMs);
  const abortFromCaller = () => controller.abort(externalSignal?.reason);
  if (externalSignal?.aborted) {
    abortFromCaller();
  } else {
    externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  }
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
    if (externalSignal?.aborted) {
      throw new ApiError("Yêu cầu đã được hủy.");
    }
    if (didTimeOut || (error instanceof DOMException && error.name === "AbortError")) {
      throw new ApiError("Yêu cầu mất quá nhiều thời gian. Em hãy thử lại nhé.");
    }
    throw new ApiError("Không thể kết nối đến máy chủ HISEDU. Hãy kiểm tra lại kết nối.");
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

type LessonStreamEnvelope =
  | ({ type: "progress" } & LessonProgressEvent)
  | { type: "partial_result"; data: PartialLessonResponse }
  | { type: "result"; data: AskResponse }
  | {
      type: "error";
      error: { message: string; status?: number; request_id?: string };
    };

function parseStreamEnvelope(block: string): LessonStreamEnvelope | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  try {
    return JSON.parse(data) as LessonStreamEnvelope;
  } catch {
    throw new ApiError("Máy chủ HISEDU trả về luồng dữ liệu không hợp lệ.");
  }
}

async function requestLessonStream(
  path: string,
  init: RequestInit,
  onProgress: (event: LessonProgressEvent) => void,
  externalSignal?: AbortSignal,
  onPartialResult?: (result: PartialLessonResponse) => void
): Promise<AskResponse> {
  const controller = new AbortController();
  let didTimeOut = false;
  const timeout = window.setTimeout(() => {
    didTimeOut = true;
    controller.abort();
  }, LESSON_REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort(externalSignal?.reason);
  if (externalSignal?.aborted) abortFromCaller();
  else externalSignal?.addEventListener("abort", abortFromCaller, { once: true });

  const headers = new Headers(init.headers);
  headers.set("Accept", "text/event-stream");

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers
    });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new ApiError(
        getMessage(body),
        response.status,
        response.headers.get("x-request-id") ?? getRequestId(body)
      );
    }
    if (!response.body) {
      throw new ApiError("Trình duyệt chưa hỗ trợ nhận tiến trình từ HISEDU.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseStreamEnvelope(block);
        if (event?.type === "progress") {
          onProgress({ stage: event.stage, message: event.message });
        } else if (event?.type === "partial_result") {
          onPartialResult?.(event.data);
        } else if (event?.type === "error") {
          throw new ApiError(
            event.error.message,
            event.error.status,
            event.error.request_id
          );
        } else if (event?.type === "result") {
          return event.data;
        }
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    throw new ApiError("Kết nối kết thúc trước khi HISEDU hoàn thành câu trả lời.");
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (externalSignal?.aborted) throw new ApiError("Yêu cầu đã được hủy.");
    if (didTimeOut || (error instanceof DOMException && error.name === "AbortError")) {
      throw new ApiError("Yêu cầu mất quá nhiều thời gian. Em hãy thử lại nhé.");
    }
    throw new ApiError("Không thể kết nối đến máy chủ HISEDU. Hãy kiểm tra lại kết nối.");
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export function askTextQuestion(
  question: string,
  signal?: AbortSignal,
  onProgress?: (event: LessonProgressEvent) => void,
  onPartialResult?: (result: PartialLessonResponse) => void
): Promise<AskResponse> {
  if (onProgress) {
    return requestLessonStream(
      "/api/questions/ask-stream",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: 3 })
      },
      onProgress,
      signal,
      onPartialResult
    );
  }
  return request<AskResponse>(
    "/api/questions/ask",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 3 })
    },
    LESSON_REQUEST_TIMEOUT_MS,
    signal
  );
}

export function extractImageText(
  file: File,
  signal?: AbortSignal
): Promise<OcrPreviewResponse> {
  const data = new FormData();
  data.append("file", file);
  return request<OcrPreviewResponse>(
    "/api/questions/ocr",
    { method: "POST", body: data },
    OCR_REQUEST_TIMEOUT_MS,
    signal
  );
}

export function askImageQuestion(
  file: File,
  question?: string,
  signal?: AbortSignal,
  onProgress?: (event: LessonProgressEvent) => void,
  onPartialResult?: (result: PartialLessonResponse) => void
): Promise<AskResponse> {
  const data = new FormData();
  data.append("file", file);
  if (question?.trim()) data.append("question", question.trim());
  data.append("top_k", "3");
  data.append("mode", "hybrid");

  if (onProgress) {
    return requestLessonStream(
      "/api/questions/ask-image-stream",
      { method: "POST", body: data },
      onProgress,
      signal,
      onPartialResult
    );
  }

  return request<AskResponse>(
    "/api/questions/ask-image",
    {
      method: "POST",
      body: data
    },
    LESSON_REQUEST_TIMEOUT_MS,
    signal
  );
}

export function submitAnswerFeedback(
  answerId: string,
  rating: AnswerFeedbackRating,
  comment?: string
): Promise<AnswerFeedbackResponse> {
  const body: { rating: AnswerFeedbackRating; comment?: string } = { rating };
  if (comment?.trim()) body.comment = comment.trim();

  return request<AnswerFeedbackResponse>(
    `/api/answers/${encodeURIComponent(answerId)}/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }
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

export function submitQuizAnswer(
  quizId: string,
  questionId: string,
  optionId: string
): Promise<QuizAnswerResponse> {
  return request<QuizAnswerResponse>(`/api/quizzes/${encodeURIComponent(quizId)}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, option_id: optionId })
  });
}

export function resetQuizAttempt(quizId: string): Promise<QuizData> {
  return request<QuizData>(`/api/quizzes/${encodeURIComponent(quizId)}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
}
