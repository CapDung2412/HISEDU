"use client";

import { FormEvent, useState } from "react";
import { submitAnswerFeedback } from "@/lib/api";
import type { AnswerFeedbackResponse } from "@/lib/types";

interface Props {
  answerId: string;
  onSubmit?: (
    answerId: string,
    rating: "not_helpful",
    comment?: string
  ) => Promise<AnswerFeedbackResponse>;
}

export function AnswerFeedback({ answerId, onSubmit = submitAnswerFeedback }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSent, setIsSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit(answerId, "not_helpful", comment.trim() || undefined);
      setIsSent(true);
      setIsOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa thể gửi báo cáo. Em hãy thử lại nhé.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isSent) {
    return (
      <aside className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900" role="status">
        <strong>Đã gửi để giáo viên kiểm tra.</strong> Cảm ơn em đã giúp HISEDU cải thiện câu trả lời.
      </aside>
    );
  }

  return (
    <aside className="rounded-2xl border border-stone-200 bg-white/80 px-4 py-3" aria-label="Phản hồi về câu trả lời">
      {!isOpen ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="text-sm font-bold text-rose-700 underline decoration-rose-200 underline-offset-4 hover:text-rose-800"
        >
          Báo câu trả lời sai
        </button>
      ) : (
        <form onSubmit={handleSubmit}>
          <label htmlFor={`answer-feedback-${answerId}`} className="block text-sm font-bold text-ink">
            Em thấy nội dung nào chưa đúng? <span className="font-normal text-stone-500">(không bắt buộc)</span>
          </label>
          <textarea
            id={`answer-feedback-${answerId}`}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            maxLength={1_000}
            rows={3}
            disabled={isSubmitting}
            className="mt-2 w-full resize-y rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm leading-6 text-ink outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-50 disabled:opacity-60"
            placeholder="Ví dụ: Mốc thời gian hoặc nhân vật cần kiểm tra lại…"
          />
          <p className="mt-1 text-xs text-stone-500">
            Không nhập họ tên, lớp, số điện thoại hoặc thông tin cá nhân.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="min-h-10 rounded-xl bg-rose-700 px-4 py-2 text-sm font-extrabold text-white transition hover:bg-rose-800 disabled:cursor-wait disabled:opacity-60"
            >
              {isSubmitting ? "Đang gửi…" : "Gửi để giáo viên kiểm tra"}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setError(null);
              }}
              disabled={isSubmitting}
              className="min-h-10 rounded-xl px-4 py-2 text-sm font-bold text-stone-600 hover:bg-stone-100 disabled:opacity-60"
            >
              Đóng
            </button>
          </div>
          {error && <p className="mt-2 text-sm font-semibold text-rose-700" role="alert">{error}</p>}
        </form>
      )}
    </aside>
  );
}
