"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { extractImageText } from "@/lib/api";
import type { OcrPreviewResponse, QuestionSubmission } from "@/lib/types";

const MAX_QUESTION_LENGTH = 1_200;
const MAX_COMBINED_QUERY_LENGTH = 2_000;
const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const SUGGESTIONS = [
  "Vì sao Cách mạng tư sản Anh bùng nổ?",
  "Vì sao Anh là nước đầu tiên tiến hành cách mạng công nghiệp?",
  "Vì sao Đông Nam Á trở thành mục tiêu xâm lược của các nước phương Tây?"
];

interface Props {
  onSubmit: (submission: QuestionSubmission) => Promise<void> | void;
  busy?: boolean;
}

type OcrStatus = "idle" | "reading" | "ready" | "error";

function combineQuestion(question: string, ocrText: string): string {
  const normalizedQuestion = question.trim();
  const normalizedOcr = ocrText.trim();
  if (!normalizedQuestion) return normalizedOcr.slice(0, MAX_COMBINED_QUERY_LENGTH);
  return `${normalizedQuestion}\n\nNội dung nhận diện từ ảnh: ${normalizedOcr}`.slice(
    0,
    MAX_COMBINED_QUERY_LENGTH
  );
}

export function QuestionComposer({ onSubmit, busy = false }: Props) {
  const [question, setQuestion] = useState("");
  const [image, setImage] = useState<File | undefined>();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [ocrText, setOcrText] = useState("");
  const [ocrPreview, setOcrPreview] = useState<OcrPreviewResponse | null>(null);
  const [ocrStatus, setOcrStatus] = useState<OcrStatus>("idle");
  const [validationError, setValidationError] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const ocrTextRef = useRef<HTMLTextAreaElement>(null);
  const activeOcrRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!image) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  useEffect(() => () => activeOcrRef.current?.abort(), []);

  async function readImageText(file: File) {
    activeOcrRef.current?.abort();
    const controller = new AbortController();
    activeOcrRef.current = controller;
    setOcrStatus("reading");
    setOcrText("");
    setOcrPreview(null);
    setValidationError(null);
    try {
      const preview = await extractImageText(file, controller.signal);
      if (controller.signal.aborted || activeOcrRef.current !== controller) return;
      setOcrText(preview.text);
      setOcrPreview(preview);
      setOcrStatus("ready");
      window.setTimeout(() => ocrTextRef.current?.focus(), 40);
    } catch (error) {
      if (controller.signal.aborted || activeOcrRef.current !== controller) return;
      setOcrStatus("error");
      setValidationError(
        error instanceof Error
          ? error.message
          : "Chưa đọc được chữ trong ảnh. Em hãy thử lại với ảnh rõ hơn."
      );
    } finally {
      if (activeOcrRef.current === controller) activeOcrRef.current = null;
    }
  }

  function chooseImage(file?: File) {
    setValidationError(null);
    if (!file) return;
    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      setValidationError("Ảnh cần có định dạng JPG, PNG hoặc WebP.");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      setValidationError("Ảnh cần nhỏ hơn 5 MB. Em hãy chọn ảnh nhẹ hơn nhé.");
      return;
    }
    setImage(file);
    void readImageText(file);
  }

  function removeImage() {
    activeOcrRef.current?.abort();
    activeOcrRef.current = null;
    setImage(undefined);
    setOcrText("");
    setOcrPreview(null);
    setOcrStatus("idle");
    setValidationError(null);
    if (uploadRef.current) uploadRef.current.value = "";
    if (cameraRef.current) cameraRef.current.value = "";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    setValidationError(null);
    if (!normalized && !image) {
      setValidationError("Em hãy nhập câu hỏi hoặc chọn một ảnh trước nhé.");
      return;
    }
    if (image && ocrStatus !== "ready") {
      await readImageText(image);
      return;
    }
    if (image) {
      const normalizedOcr = ocrText.trim();
      if (normalizedOcr.length < 3) {
        setValidationError("Em hãy kiểm tra và bổ sung văn bản nhận diện trước khi tìm kiếm.");
        return;
      }
      // Once the student confirms the OCR draft, search its text directly.
      // This avoids running OCR and CLIP image retrieval for a second time.
      await onSubmit({ question: combineQuestion(normalized, normalizedOcr) });
      return;
    }
    await onSubmit({ question: normalized, image: undefined });
  }

  return (
    <section className="section-card overflow-hidden border-brand-200/80 p-4 ring-4 ring-white/50 sm:p-6" aria-label="Đặt câu hỏi lịch sử">
      <div className="mb-4 flex items-center justify-between gap-4 border-b border-stone-100 pb-4">
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-brand-600">Bắt đầu khám phá</p>
          <h2 className="history-serif mt-0.5 text-xl font-bold text-ink sm:text-2xl">Em muốn tìm hiểu điều gì?</h2>
        </div>
        <span className="hidden rounded-full border border-sun-400/30 bg-sun-50 px-3 py-1 text-xs font-bold text-amber-900 sm:block">
          Văn bản hoặc hình ảnh
        </span>
      </div>
      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor="history-question" className="mb-2 block text-sm font-bold text-stone-700">
          Câu hỏi của em
        </label>
        <div className="rounded-2xl border border-stone-200 bg-[#fffefa] shadow-inner transition focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-50">
          <textarea
            id="history-question"
            value={question}
            onChange={(event) => {
              setQuestion(event.target.value);
              setValidationError(null);
            }}
            maxLength={MAX_QUESTION_LENGTH}
            rows={4}
            disabled={busy}
            aria-describedby="question-help question-count question-error"
            placeholder="Ví dụ: Vì sao Cách mạng tư sản Anh bùng nổ?"
            className="min-h-28 w-full resize-y rounded-t-2xl border-0 bg-transparent px-4 pb-2 pt-4 text-base leading-7 text-ink outline-none placeholder:text-stone-400 disabled:cursor-wait disabled:opacity-70 sm:px-5 sm:text-lg"
          />
          <div className="flex items-center justify-between gap-3 px-4 pb-3 text-xs text-stone-500 sm:px-5">
            <span id="question-help">Không nhập thông tin cá nhân của em.</span>
            <span id="question-count" aria-label={`${question.length} trên ${MAX_QUESTION_LENGTH} ký tự`}>
              {question.length}/{MAX_QUESTION_LENGTH}
            </span>
          </div>
        </div>

        {previewUrl && image && (
          <div className="mt-4 rounded-2xl border border-brand-100 bg-brand-50 p-3 sm:p-4">
            <div className="flex items-center gap-3">
              {/* Blob previews do not benefit from Next image optimization. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previewUrl} alt="Ảnh câu hỏi đã chọn" className="h-20 w-20 rounded-xl object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-ink">{image.name}</p>
                <p className="mt-1 text-xs font-semibold text-slate-600" aria-live="polite">
                  {ocrStatus === "reading" && "Đang đọc chữ trong ảnh…"}
                  {ocrStatus === "ready" && "Đã nhận diện · Em hãy kiểm tra lại nội dung bên dưới"}
                  {ocrStatus === "error" && "Chưa nhận diện được · Có thể thử đọc lại"}
                  {ocrStatus === "idle" && `${(image.size / 1024 / 1024).toFixed(1)} MB`}
                </p>
              </div>
              <button
                type="button"
                onClick={removeImage}
                disabled={busy}
                className="min-h-11 rounded-full px-3 py-2 text-sm font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                aria-label="Xóa ảnh đã chọn"
              >
                Xóa
              </button>
            </div>

            {ocrStatus === "reading" && (
              <div className="mt-3 rounded-xl border border-brand-100 bg-white/80 p-4" role="status">
                <div className="h-3 w-40 animate-pulse rounded-full bg-brand-100" />
                <div className="mt-3 h-3 w-full animate-pulse rounded-full bg-stone-200" />
                <div className="mt-2 h-3 w-4/5 animate-pulse rounded-full bg-stone-200" />
                <span className="sr-only">Đang nhận dạng văn bản trong ảnh</span>
              </div>
            )}

            {ocrStatus === "ready" && ocrPreview && (
              <div className="mt-3 rounded-xl border border-amber-200 bg-[#fffdf8] p-3 sm:p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <label htmlFor="ocr-preview" className="block text-sm font-extrabold text-brand-900">
                      Kiểm tra văn bản nhận diện
                    </label>
                    <p id="ocr-preview-help" className="mt-0.5 text-xs leading-5 text-stone-600">
                      Em có thể sửa tên riêng, mốc năm hoặc chữ bị đọc sai trước khi tìm kiếm.
                    </p>
                  </div>
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-900">
                    {ocrPreview.line_count} dòng
                    {ocrPreview.mean_score !== null
                      ? ` · ${Math.round(ocrPreview.mean_score * 100)}% nhận diện`
                      : ""}
                  </span>
                </div>
                <textarea
                  ref={ocrTextRef}
                  id="ocr-preview"
                  value={ocrText}
                  onChange={(event) => {
                    setOcrText(event.target.value);
                    setValidationError(null);
                  }}
                  maxLength={MAX_COMBINED_QUERY_LENGTH}
                  rows={5}
                  disabled={busy}
                  aria-describedby="ocr-preview-help"
                  className="mt-3 min-h-28 w-full resize-y rounded-xl border border-stone-200 bg-white px-3 py-3 text-base leading-7 text-ink outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-50 disabled:opacity-60"
                />
                <p className={`mt-2 text-xs font-semibold ${ocrPreview.needs_review ? "text-amber-800" : "text-emerald-700"}`}>
                  {ocrPreview.needs_review
                    ? "Ảnh có phần chưa rõ — em nên đối chiếu kỹ trước khi tiếp tục."
                    : "Ảnh khá rõ — vẫn nên kiểm tra tên người và mốc thời gian."}
                </p>
              </div>
            )}

            {ocrStatus === "error" && (
              <button
                type="button"
                onClick={() => void readImageText(image)}
                disabled={busy}
                className="mt-3 min-h-11 rounded-xl border border-brand-200 bg-white px-4 py-2 text-sm font-extrabold text-brand-800 transition hover:bg-brand-50 disabled:opacity-50"
              >
                Thử đọc lại ảnh
              </button>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <input
              ref={uploadRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              tabIndex={-1}
              onChange={(event) => chooseImage(event.target.files?.[0])}
              aria-hidden="true"
            />
            <button
              type="button"
              onClick={() => uploadRef.current?.click()}
              disabled={busy}
              className="min-h-11 rounded-xl border border-stone-200 bg-white px-4 py-2 text-sm font-bold text-stone-700 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
            >
              <span className="mr-1 text-brand-600" aria-hidden>＋</span> Tải ảnh
            </button>

            <input
              ref={cameraRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              className="sr-only"
              tabIndex={-1}
              onChange={(event) => chooseImage(event.target.files?.[0])}
              aria-hidden="true"
            />
            <button
              type="button"
              onClick={() => cameraRef.current?.click()}
              disabled={busy}
              className="min-h-11 rounded-xl border border-stone-200 bg-white px-4 py-2 text-sm font-bold text-stone-700 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
            >
              <span className="mr-1 text-brand-600" aria-hidden>◎</span> Chụp câu hỏi
            </button>
          </div>

          <button
            type="submit"
            disabled={busy || ocrStatus === "reading"}
            className="min-h-12 rounded-xl border border-brand-800 bg-brand-700 px-7 py-3 font-extrabold text-white shadow-lg shadow-brand-200 transition hover:-translate-y-0.5 hover:bg-brand-800 disabled:cursor-wait disabled:translate-y-0 disabled:opacity-60"
          >
            {busy
              ? "Đang tìm hiểu…"
              : ocrStatus === "reading"
                ? "Đang đọc ảnh…"
                : image && ocrStatus !== "ready"
                  ? "Đọc lại ảnh"
                  : "Hỏi HISEDU"} <span aria-hidden>→</span>
          </button>
        </div>

        <p id="question-error" className="mt-3 min-h-6 text-sm font-semibold text-rose-700" role="alert">
          {validationError}
        </p>
      </form>

      <div className="border-t border-stone-100 pt-4">
        <p className="text-[11px] font-black uppercase tracking-[0.16em] text-stone-500">Gợi ý câu hỏi</p>
        <div className="mt-2 flex gap-2 overflow-x-auto pb-2 sm:flex-wrap" aria-label="Câu hỏi gợi ý">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={busy}
              onClick={() => {
                setQuestion(suggestion);
                setValidationError(null);
              }}
              className="shrink-0 rounded-full border border-sun-400/25 bg-sun-50 px-3 py-2 text-left text-xs font-semibold text-amber-950 transition hover:border-sun-400 hover:bg-sun-100 disabled:opacity-50 sm:text-sm"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
