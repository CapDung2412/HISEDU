"use client";

import { useRef, useState } from "react";
import { AnswerPanel } from "@/components/AnswerPanel";
import { MindMap } from "@/components/MindMap";
import { QuestionComposer } from "@/components/QuestionComposer";
import { Quiz } from "@/components/Quiz";
import { SourceList } from "@/components/SourceList";
import { VideoList } from "@/components/VideoList";
import { askImageQuestion, askTextQuestion } from "@/lib/api";
import type { AskResponse, QuestionSubmission } from "@/lib/types";

function LoadingResult() {
  return (
    <div className="section-card space-y-5 p-5 sm:p-7" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-100 text-xl" aria-hidden>
          ✨
        </span>
        <div>
          <p className="font-bold text-ink">HISEDU đang tìm câu trả lời…</p>
          <p className="text-sm text-slate-600">Đang đọc tài liệu và sắp xếp kiến thức cho em.</p>
        </div>
      </div>
      <div className="space-y-3" aria-hidden>
        <div className="h-4 w-4/5 animate-soft-pulse rounded-full bg-slate-200" />
        <div className="h-4 w-full animate-soft-pulse rounded-full bg-slate-200" />
        <div className="h-4 w-2/3 animate-soft-pulse rounded-full bg-slate-200" />
      </div>
    </div>
  );
}

export function HiseduApp() {
  const [result, setResult] = useState<AskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  async function handleSubmit({ question, image }: QuestionSubmission) {
    setIsLoading(true);
    setError(null);
    setResult(null);
    window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth" }), 60);

    try {
      const response = image
        ? await askImageQuestion(image, question)
        : await askTextQuestion(question);
      setResult(response);
      window.setTimeout(() => resultRef.current?.focus(), 40);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Có lỗi xảy ra. Em hãy thử lại nhé.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen overflow-x-hidden">
      <a href="#main-content" className="skip-link">
        Đi tới nội dung chính
      </a>

      <header className="border-b border-white/80 bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <a href="#" className="group flex items-center gap-3" aria-label="HISEDU — Trang chủ">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-600 text-xl text-white shadow-lg shadow-blue-200 transition group-hover:-rotate-3" aria-hidden>
              H
            </span>
            <span>
              <strong className="block text-lg leading-5 tracking-tight text-brand-700">HISEDU</strong>
              <span className="text-xs font-medium text-slate-500">Học sử thật dễ hiểu</span>
            </span>
          </a>
          <span className="hidden items-center gap-2 rounded-full bg-sun-50 px-3 py-1.5 text-sm font-semibold text-amber-800 sm:flex">
            <span aria-hidden>🌱</span> Dành cho học sinh THCS
          </span>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6 sm:pt-14">
        <section className="mx-auto max-w-3xl text-center" aria-labelledby="hero-title">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-100 bg-white px-4 py-2 text-sm font-semibold text-brand-700 shadow-sm">
            <span aria-hidden>📚</span> Người bạn đồng hành môn Lịch sử
          </div>
          <h1 id="hero-title" className="balanced text-3xl font-black leading-tight tracking-tight text-ink sm:text-5xl">
            Điều gì trong lịch sử khiến em tò mò?
          </h1>
          <p className="balanced mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
            Hãy hỏi bằng chữ hoặc chụp câu hỏi. HISEDU sẽ giải thích dễ hiểu, vẽ sơ đồ tư duy
            và tạo quiz để em nhớ lâu hơn.
          </p>
        </section>

        <div className="mx-auto mt-8 max-w-4xl sm:mt-10">
          <QuestionComposer onSubmit={handleSubmit} busy={isLoading} />
        </div>

        <div ref={resultRef} tabIndex={-1} className="mx-auto mt-8 max-w-5xl scroll-mt-6 space-y-6 outline-none" aria-label="Kết quả học tập">
          {isLoading && <LoadingResult />}

          {error && !isLoading && (
            <div className="section-card border-rose-200 bg-rose-50 p-5" role="alert">
              <div className="flex items-start gap-3">
                <span className="text-xl" aria-hidden>🌦️</span>
                <div>
                  <h2 className="font-bold text-rose-900">Chưa thể trả lời lúc này</h2>
                  <p className="mt-1 text-sm text-rose-800">{error}</p>
                </div>
              </div>
            </div>
          )}

          {result && !isLoading && (
            <>
              {result.retrieval.low_confidence && (
                <aside className="rounded-3xl border border-amber-300 bg-amber-50 p-5 text-amber-950" role="note">
                  <strong>HISEDU chưa tìm thấy tài liệu khớp hoàn toàn.</strong>{" "}
                  Câu trả lời dưới đây nên được kiểm tra thêm; em có thể hỏi cụ thể hơn nhé.
                </aside>
              )}
              <AnswerPanel answer={result.answer} question={result.question} />
              <MindMap key={`mindmap-${result.request_id}`} data={result.mindmap} />
              <VideoList videos={result.videos} />
              <SourceList sources={result.sources} />
              <Quiz key={`quiz-${result.request_id}`} quiz={result.quiz} />

              {result.limitations.length > 0 && (
                <aside className="rounded-3xl border border-slate-200 bg-slate-50 p-5" aria-labelledby="limitations-title">
                  <h2 id="limitations-title" className="font-bold text-slate-800">Điều em nên lưu ý</h2>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
                    {result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
                  </ul>
                </aside>
              )}
            </>
          )}
        </div>
      </main>

      <footer className="border-t border-brand-100 bg-white/80">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-7 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p><strong className="text-brand-700">HISEDU</strong> — Học lịch sử bằng sự tò mò.</p>
          <p>AI có thể nhầm. Hãy luôn xem nguồn tham khảo.</p>
        </div>
      </footer>
    </div>
  );
}
