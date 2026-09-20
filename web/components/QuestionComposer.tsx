"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { QuestionSubmission } from "@/lib/types";

const MAX_QUESTION_LENGTH = 1_200;
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

export function QuestionComposer({ onSubmit, busy = false }: Props) {
  const [question, setQuestion] = useState("");
  const [image, setImage] = useState<File | undefined>();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!image) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

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
  }

  function removeImage() {
    setImage(undefined);
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
    await onSubmit({ question: normalized, image });
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
            placeholder="Ví dụ: Vì sao chiến thắng Bạch Đằng năm 938 có ý nghĩa lớn?"
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
          <div className="mt-4 flex items-center gap-3 rounded-2xl border border-brand-100 bg-brand-50 p-3">
            {/* Blob previews do not benefit from Next image optimization. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt="Ảnh câu hỏi đã chọn" className="h-20 w-20 rounded-xl object-cover" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold text-ink">{image.name}</p>
              <p className="text-xs text-slate-600">{(image.size / 1024 / 1024).toFixed(1)} MB · Sẵn sàng phân tích</p>
            </div>
            <button
              type="button"
              onClick={removeImage}
              disabled={busy}
              className="rounded-full px-3 py-2 text-sm font-bold text-rose-700 hover:bg-rose-50"
              aria-label="Xóa ảnh đã chọn"
            >
              Xóa
            </button>
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
            disabled={busy}
            className="min-h-12 rounded-xl border border-brand-800 bg-brand-700 px-7 py-3 font-extrabold text-white shadow-lg shadow-brand-200 transition hover:-translate-y-0.5 hover:bg-brand-800 disabled:cursor-wait disabled:translate-y-0 disabled:opacity-60"
          >
            {busy ? "Đang tìm hiểu…" : "Hỏi HISEDU"} <span aria-hidden>→</span>
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
