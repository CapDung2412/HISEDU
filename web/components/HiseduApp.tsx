"use client";

import { useRef, useState } from "react";
import { AnswerPanel } from "@/components/AnswerPanel";
import { DongSonDrumMotif, HeritageBackdrop, LacBirdMotif } from "@/components/HeritageMotifs";
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
        <span className="grid h-11 w-11 place-items-center rounded-full border border-brand-200 bg-brand-50 text-brand-700" aria-hidden>
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700" />
        </span>
        <div>
          <p className="history-serif text-lg font-bold text-ink">HISEDU đang tra cứu sử liệu…</p>
          <p className="text-sm text-stone-600">Đang đối chiếu tài liệu và sắp xếp kiến thức cho em.</p>
        </div>
      </div>
      <div className="space-y-3" aria-hidden>
        <div className="h-3 w-4/5 animate-soft-pulse rounded-full bg-stone-200" />
        <div className="h-3 w-full animate-soft-pulse rounded-full bg-stone-200" />
        <div className="h-3 w-2/3 animate-soft-pulse rounded-full bg-stone-200" />
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
    <div className="relative isolate min-h-screen overflow-x-hidden">
      <HeritageBackdrop />
      <a href="#main-content" className="skip-link">
        Đi tới nội dung chính
      </a>

      <header className="sticky top-0 z-40 border-b border-brand-100/80 bg-[#fffdf8]/90 backdrop-blur-xl">
        <div className="h-1 bg-gradient-to-r from-brand-950 via-brand-600 to-sun-400" aria-hidden />
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <a href="#" className="group flex items-center gap-3" aria-label="HISEDU — Trang chủ">
            <span className="grid h-11 w-11 place-items-center rounded-full border-2 border-sun-400 bg-brand-700 text-white shadow-md transition group-hover:-rotate-3" aria-hidden>
              <DongSonDrumMotif className="h-9 w-9" />
            </span>
            <span>
              <strong className="history-serif block text-xl leading-5 tracking-[0.08em] text-brand-800">HISEDU</strong>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-stone-500">Hiểu sử · Vững tương lai</span>
            </span>
          </a>
          <div className="hidden items-center gap-5 sm:flex">
            <a href="#question-area" className="text-sm font-bold text-stone-600 transition hover:text-brand-700">Đặt câu hỏi</a>
            <span className="rounded-full border border-sun-400/40 bg-sun-50 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-amber-900">
              Dành cho học sinh THCS
            </span>
          </div>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-6xl px-4 pb-20 pt-7 sm:px-6 sm:pt-10">
        <section className="history-hero px-6 pb-20 pt-9 sm:px-10 sm:pb-24 sm:pt-12 lg:px-14" aria-labelledby="hero-title">
          <DongSonDrumMotif className="history-hero__drum" />
          <LacBirdMotif className="history-hero__birds" />
          <div className="grid items-center gap-8 lg:grid-cols-[1.35fr_0.65fr]">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 text-xs font-extrabold uppercase tracking-[0.18em] text-brand-700">
                <span className="h-px w-8 bg-sun-400" aria-hidden />
                <span>Trợ lý học tập môn Lịch sử</span>
              </div>
              <h1 id="hero-title" className="history-serif balanced max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight text-ink sm:text-5xl lg:text-6xl">
                Mỗi dấu mốc đều có một <span className="text-brand-700">câu chuyện</span>
              </h1>
              <p className="balanced mt-5 max-w-2xl text-base leading-7 text-stone-600 sm:text-lg">
                Hỏi bằng chữ hoặc chụp đề bài. HISEDU giúp em hiểu bối cảnh, nắm diễn biến
                và ghi nhớ kiến thức bằng sơ đồ, video, quiz có nguồn tham khảo.
              </p>
            </div>

            <aside className="relative hidden overflow-hidden rounded-3xl border border-white/80 bg-white/70 p-5 shadow-sm backdrop-blur-sm lg:block" aria-label="Quy trình học với HISEDU">
              <DongSonDrumMotif className="pointer-events-none absolute -bottom-14 -right-12 h-36 w-36 text-brand-700/[0.06]" />
              <p className="history-serif text-lg font-bold text-brand-800">Học theo 3 bước</p>
              <ol className="mt-4 space-y-4">
                {["Đặt câu hỏi", "Hiểu theo hệ thống", "Ghi nhớ bằng luyện tập"].map((item, index) => (
                  <li key={item} className="flex items-center gap-3 text-sm font-semibold text-stone-700">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-sun-400/50 bg-sun-50 font-black text-brand-700">{index + 1}</span>
                    {item}
                  </li>
                ))}
              </ol>
            </aside>
          </div>
        </section>

        <div id="question-area" className="relative z-10 mx-auto -mt-12 max-w-4xl scroll-mt-28 sm:-mt-14">
          <QuestionComposer onSubmit={handleSubmit} busy={isLoading} />
        </div>

        <div className="museum-rule mx-auto mt-8 max-w-xl text-[11px] font-bold uppercase tracking-[0.22em] text-stone-500" aria-hidden>
          <span>Khám phá · Hiểu sâu · Ghi nhớ</span>
        </div>

        <div ref={resultRef} tabIndex={-1} className="mx-auto mt-8 max-w-5xl scroll-mt-28 space-y-6 outline-none" aria-label="Kết quả học tập">
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
              <AnswerPanel answer={result.answer} question={result.question} mindmap={result.mindmap} />
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

      <footer className="relative overflow-hidden border-t-4 border-sun-400 bg-heritage-900 text-white/75">
        <LacBirdMotif className="pointer-events-none absolute -right-10 -top-2 h-24 w-72 text-sun-100/[0.08]" />
        <div className="relative mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p><strong className="history-serif mr-2 text-lg tracking-wider text-white">HISEDU</strong> Học lịch sử bằng sự tò mò.</p>
          <p className="text-xs">Nội dung AI cần được đối chiếu cùng nguồn tham khảo.</p>
        </div>
      </footer>
    </div>
  );
}
