"use client";

import { useEffect, useRef, useState } from "react";
import { AnswerFeedback } from "@/components/AnswerFeedback";
import { AnswerPanel } from "@/components/AnswerPanel";
import { DongSonDrumMotif, HeritageBackdrop, LacBirdMotif } from "@/components/HeritageMotifs";
import { HistoricalSourceGallery } from "@/components/HistoricalSourceGallery";
import { MindMap } from "@/components/MindMap";
import { QuestionComposer } from "@/components/QuestionComposer";
import { Quiz } from "@/components/Quiz";
import { SourceList } from "@/components/SourceList";
import { VideoList } from "@/components/VideoList";
import { askImageQuestion, askTextQuestion } from "@/lib/api";
import type {
  AskResponse,
  LessonProgressEvent,
  PartialLessonResponse,
  QuestionSubmission
} from "@/lib/types";

const LOADING_STAGES = [
  {
    afterSeconds: 0,
    label: "Tiếp nhận",
    title: "Đang đọc câu hỏi của em…",
    detail: "HISEDU đang xác định sự kiện, nhân vật và mốc thời gian cần tìm hiểu."
  },
  {
    afterSeconds: 5,
    label: "Tìm sử liệu",
    title: "Đang tìm nguồn liên quan…",
    detail: "Kho kiến thức đang chọn những tư liệu Lịch sử lớp 8 phù hợp nhất."
  },
  {
    afterSeconds: 12,
    label: "Đối chiếu",
    title: "Đang đối chiếu sử liệu…",
    detail: "Các dữ kiện chính đang được kiểm tra với nguồn đã tìm thấy."
  },
  {
    afterSeconds: 25,
    label: "Biên soạn",
    title: "Đang hoàn thiện bài học…",
    detail: "HISEDU đang tạo lời giải, sơ đồ tư duy và câu hỏi ghi nhớ."
  }
] as const;

const WAITING_TIPS = [
  "Mẹo học sử: nối kiến thức theo trục Nguyên nhân → Diễn biến → Kết quả → Ý nghĩa.",
  "Mỗi mốc thời gian sẽ dễ nhớ hơn khi gắn với một nhân vật hoặc sự kiện.",
  "HISEDU đang đối chiếu nguồn trước khi trình bày nội dung cho em."
] as const;

type RequestKind = "text" | "image";

interface LoadingResultProps {
  onCancel: () => void;
  requestKind?: RequestKind;
  progress?: LessonProgressEvent | null;
}

const PROGRESS_STAGE_INDEX: Record<LessonProgressEvent["stage"], number> = {
  received: 0,
  retrieval: 1,
  generation: 2,
  enrichment: 3,
  finalizing: 3
};

export function LoadingResult({
  onCancel,
  requestKind = "text",
  progress = null
}: LoadingResultProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const updateElapsed = () => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1_000));
    const interval = window.setInterval(updateElapsed, 1_000);
    return () => window.clearInterval(interval);
  }, []);

  const estimatedStageIndex = LOADING_STAGES.reduce(
    (current, candidate, index) => elapsedSeconds >= candidate.afterSeconds ? index : current,
    0
  );
  const stageIndex = progress ? PROGRESS_STAGE_INDEX[progress.stage] : estimatedStageIndex;
  const stage = LOADING_STAGES[stageIndex];
  const stageTitle = progress?.message ?? (requestKind === "image" && stageIndex === 0
    ? "Đang nhận dạng chữ trong ảnh…"
    : stage.title);
  const waitingTip = WAITING_TIPS[Math.floor(elapsedSeconds / 7) % WAITING_TIPS.length];

  return (
    <section
      className="loading-journey section-card relative overflow-hidden p-5 sm:p-7"
      aria-busy="true"
      aria-labelledby="loading-title"
    >
      <LacBirdMotif className="loading-journey__birds" />
      <div className="relative grid items-center gap-6 md:grid-cols-[12rem_1fr] md:gap-8">
        <div className="mx-auto flex flex-col items-center">
          <div className="loading-emblem" aria-hidden>
            <span className="loading-emblem__halo" />
            <DongSonDrumMotif className="loading-emblem__drum" />
            <span className="loading-emblem__center">SỬ</span>
          </div>
          <span className="mt-3 rounded-full border border-sun-400/40 bg-white/80 px-3 py-1 text-xs font-extrabold tabular-nums text-brand-800 shadow-sm">
            {elapsedSeconds} giây
          </span>
        </div>

        <div className="min-w-0">
          <p className="text-[11px] font-extrabold uppercase tracking-[0.2em] text-brand-700">
            Đang mở hồ sơ lịch sử
          </p>
          <div className="mt-2" role="status" aria-live="polite" aria-atomic="true">
            <h2 id="loading-title" className="history-serif text-2xl font-bold text-ink sm:text-3xl">
              {stageTitle}
            </h2>
            <p className="mt-1 text-sm leading-6 text-stone-600">{stage.detail}</p>
          </div>

          <div className="loading-progress mt-5" aria-hidden>
            <span />
          </div>

          <ol className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Tiến trình dự kiến">
            {LOADING_STAGES.map((item, index) => {
              const state = index === stageIndex ? "active" : index < stageIndex ? "passed" : "pending";
              return (
                <li key={item.label} className={`loading-step loading-step--${state}`}>
                  <span className="loading-step__number" aria-hidden>{String(index + 1).padStart(2, "0")}</span>
                  <span className="text-xs font-extrabold leading-tight">{item.label}</span>
                  {index === stageIndex && <span className="sr-only"> — bước đang thực hiện</span>}
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      <div className="relative mt-6 rounded-2xl border border-amber-200/70 bg-white/65 p-4 backdrop-blur-sm">
        <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-amber-900">Trong lúc chờ</p>
        <p className="mt-1 text-sm leading-6 text-stone-700">{waitingTip}</p>
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Nội dung đang được chuẩn bị">
          {["Lời giải", "Sơ đồ tư duy", "Nguồn đối chiếu", "Quiz ôn tập"].map((item) => (
            <span key={item} className="rounded-full border border-brand-100 bg-brand-50/80 px-3 py-1 text-xs font-bold text-brand-800">
              {item}
            </span>
          ))}
        </div>
      </div>

      {elapsedSeconds >= 30 && (
        <p className="relative mt-4 rounded-xl border border-heritage-100 bg-heritage-50 px-4 py-3 text-sm font-semibold text-heritage-700">
          Lần đầu mở kho kiến thức có thể lâu hơn một chút. Em không cần gửi lại câu hỏi.
        </p>
      )}

      <div className="relative mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-brand-100/70 pt-4">
        <p className="text-sm font-semibold tabular-nums text-stone-500">Đã chờ {elapsedSeconds} giây</p>
        <button
          type="button"
          onClick={onCancel}
          aria-label="Hủy yêu cầu"
          className="min-h-11 rounded-xl border border-stone-300 bg-white px-4 py-2 text-sm font-extrabold text-stone-700 shadow-sm transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-800"
        >
          Dừng xử lý
        </button>
      </div>
    </section>
  );
}

export function HiseduApp() {
  const [result, setResult] = useState<AskResponse | null>(null);
  const [partialResult, setPartialResult] = useState<PartialLessonResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wasCancelled, setWasCancelled] = useState(false);
  const [loadingKind, setLoadingKind] = useState<RequestKind>("text");
  const [progress, setProgress] = useState<LessonProgressEvent | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const activeRequestRef = useRef<AbortController | null>(null);

  useEffect(() => () => activeRequestRef.current?.abort(), []);

  async function handleSubmit({ question, image }: QuestionSubmission) {
    activeRequestRef.current?.abort();
    const controller = new AbortController();
    activeRequestRef.current = controller;
    setLoadingKind(image ? "image" : "text");
    setIsLoading(true);
    setError(null);
    setWasCancelled(false);
    setProgress(null);
    setResult(null);
    setPartialResult(null);
    window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth" }), 60);

    try {
      const revealCoreLesson = (partial: PartialLessonResponse) => {
        if (!controller.signal.aborted && activeRequestRef.current === controller) {
          setPartialResult(partial);
        }
      };
      const response = image
        ? await askImageQuestion(
            image,
            question,
            controller.signal,
            setProgress,
            revealCoreLesson
          )
        : await askTextQuestion(
            question,
            controller.signal,
            setProgress,
            revealCoreLesson
          );
      if (controller.signal.aborted || activeRequestRef.current !== controller) return;
      setResult(response);
      setPartialResult(null);
      window.setTimeout(() => resultRef.current?.focus(), 40);
    } catch (caught) {
      if (!controller.signal.aborted && activeRequestRef.current === controller) {
        setError(caught instanceof Error ? caught.message : "Có lỗi xảy ra. Em hãy thử lại nhé.");
      }
    } finally {
      if (activeRequestRef.current === controller) {
        activeRequestRef.current = null;
        setIsLoading(false);
      }
    }
  }

  function handleCancel() {
    const controller = activeRequestRef.current;
    if (!controller) return;
    controller.abort();
    activeRequestRef.current = null;
    setIsLoading(false);
    setWasCancelled(true);
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
              Thử nghiệm · Lịch sử lớp 8
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
                Hỏi bằng chữ hoặc chụp đề bài. Bản thử nghiệm hiện tập trung vào nội dung
                Lịch sử lớp 8, với sơ đồ, video, quiz và nguồn tham khảo để em đối chiếu.
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

        <div ref={resultRef} tabIndex={-1} className="mx-auto mt-8 max-w-5xl scroll-mt-28 space-y-6 outline-none" aria-label="Kết quả học tập" aria-busy={isLoading}>
          {isLoading && !partialResult && (
            <LoadingResult
              onCancel={handleCancel}
              requestKind={loadingKind}
              progress={progress}
            />
          )}

          {isLoading && partialResult && (
            <>
              <section
                className="section-card overflow-hidden border border-emerald-200 bg-emerald-50/90 p-4 sm:p-5"
                aria-busy="true"
                aria-label="Đang hoàn thiện phần học mở rộng"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="text-xs font-black uppercase tracking-[0.15em] text-emerald-800">
                      Lời giải đã sẵn sàng
                    </p>
                    <p className="mt-1 text-sm font-semibold leading-6 text-emerald-950" role="status" aria-live="polite">
                      {progress?.message ?? "HISEDU đang hoàn thiện sơ đồ tư duy, video và quiz…"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="inline-flex items-center gap-2 text-xs font-bold text-emerald-800">
                      <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-600" aria-hidden />
                      Tiếp tục xử lý
                    </span>
                    <button
                      type="button"
                      onClick={handleCancel}
                      aria-label="Hủy yêu cầu"
                      className="min-h-11 rounded-xl border border-emerald-300 bg-white px-4 py-2 text-sm font-extrabold text-stone-700 shadow-sm transition hover:border-rose-300 hover:bg-rose-50 hover:text-rose-800"
                    >
                      Dừng xử lý
                    </button>
                  </div>
                </div>
              </section>
              <AnswerPanel
                answer={partialResult.answer}
                question={partialResult.question}
                mindmap={partialResult.mindmap}
              />
              <SourceList sources={partialResult.sources} />
            </>
          )}

          {wasCancelled && !isLoading && (
            <div className="rounded-2xl border border-stone-200 bg-white/80 p-4 text-sm text-stone-700" role="status">
              <strong>Đã dừng yêu cầu.</strong> Em có thể chỉnh câu hỏi rồi thử lại bất cứ lúc nào.
            </div>
          )}

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
              <AnswerFeedback key={`feedback-${result.answer_id}`} answerId={result.answer_id} />
              <SourceList sources={result.sources} />
              <HistoricalSourceGallery question={result.question} answer={result.answer} />
              <MindMap key={`mindmap-${result.request_id}`} data={result.mindmap} />
              <VideoList videos={result.videos} />
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
