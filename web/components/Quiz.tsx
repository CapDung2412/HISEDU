"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { resetQuizAttempt, submitQuizAnswer } from "@/lib/api";
import type {
  QuizAnswerResponse,
  QuizData,
  QuizDifficulty,
  QuizQuestion,
  QuizResultItem
} from "@/lib/types";

interface Props {
  quiz: QuizData;
  onAnswer?: (
    quizId: string,
    questionId: string,
    optionId: string
  ) => Promise<QuizAnswerResponse>;
  onReset?: (quizId: string) => Promise<QuizData>;
}

const difficultyLabel: Record<QuizDifficulty, string> = {
  remember: "Nhận biết",
  understand: "Thông hiểu",
  apply: "Vận dụng"
};

function difficultyOf(question: QuizQuestion): QuizDifficulty {
  return question.difficulty ?? "understand";
}

export function Quiz({
  quiz,
  onAnswer = submitQuizAnswer,
  onReset = resetQuizAttempt
}: Props) {
  const sectionRef = useRef<HTMLElement>(null);
  const [currentQuestion, setCurrentQuestion] = useState<QuizQuestion | null>(
    quiz.questions[0] ?? null
  );
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [currentResult, setCurrentResult] = useState<QuizResultItem | null>(null);
  const [nextQuestion, setNextQuestion] = useState<QuizQuestion | null>(null);
  const [history, setHistory] = useState<QuizResultItem[]>([]);
  const [score, setScore] = useState(0);
  const [adaptiveMessage, setAdaptiveMessage] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCurrentQuestion(quiz.questions[0] ?? null);
    setSelectedOptionId(null);
    setCurrentResult(null);
    setNextQuestion(null);
    setHistory([]);
    setScore(0);
    setAdaptiveMessage(null);
    setCompleted(false);
    setError(null);
  }, [quiz.quiz_id, quiz.questions]);

  const questionById = useMemo(
    () => new Map(quiz.questions.map((question) => [question.id, question])),
    [quiz.questions]
  );
  const questionNumber = Math.min(
    quiz.questions.length,
    history.length + (currentResult ? 0 : 1)
  );
  const progress = quiz.questions.length
    ? Math.round((history.length / quiz.questions.length) * 100)
    : 0;

  async function checkAnswer() {
    if (!currentQuestion || !selectedOptionId) {
      setError("Em hãy chọn một đáp án trước khi kiểm tra.");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await onAnswer(
        quiz.quiz_id,
        currentQuestion.id,
        selectedOptionId
      );
      setCurrentResult(response.result);
      setNextQuestion(response.next_question);
      setScore(response.score_so_far);
      setCompleted(response.completed);
      setAdaptiveMessage(response.adaptive_message);
      setHistory((items) =>
        items.some((item) => item.question_id === response.result.question_id)
          ? items
          : [...items, response.result]
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa thể chấm câu này. Em hãy thử lại nhé.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function continueQuiz() {
    if (!nextQuestion) return;
    setCurrentQuestion(nextQuestion);
    setSelectedOptionId(null);
    setCurrentResult(null);
    setNextQuestion(null);
    setAdaptiveMessage(null);
    setError(null);
    sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function retry() {
    setIsResetting(true);
    setError(null);
    try {
      const freshQuiz = await onReset(quiz.quiz_id);
      setCurrentQuestion(freshQuiz.questions[0] ?? null);
      setSelectedOptionId(null);
      setCurrentResult(null);
      setNextQuestion(null);
      setHistory([]);
      setScore(0);
      setAdaptiveMessage(null);
      setCompleted(false);
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa thể tạo lượt mới. Em hãy thử lại nhé.");
    } finally {
      setIsResetting(false);
    }
  }

  if (!currentQuestion || quiz.questions.length === 0) return null;

  return (
    <section
      ref={sectionRef}
      id={`quiz-${quiz.quiz_id}`}
      className="section-card scroll-mt-28 overflow-hidden"
      aria-labelledby="quiz-heading"
    >
      <div className="border-b border-sun-400/30 bg-gradient-to-r from-sun-50 to-white p-5 sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="history-serif grid h-11 w-11 place-items-center rounded-full border border-sun-400/50 bg-white text-sm font-bold text-brand-700" aria-hidden>05</span>
            <div>
              <p className="text-xs font-extrabold uppercase tracking-wider text-amber-700">Luyện tập thích ứng</p>
              <h2 id="quiz-heading" className="history-serif text-xl font-bold text-ink sm:text-2xl">Quiz 5 câu</h2>
              <p className="mt-1 text-sm text-slate-600">Trả lời từng câu; độ khó tiếp theo sẽ thay đổi theo kết quả của em.</p>
            </div>
          </div>
          <div className="min-w-44 rounded-2xl border border-sun-200 bg-white/80 px-4 py-3">
            <div className="flex items-center justify-between text-xs font-bold text-slate-600">
              <span>{completed ? "Hoàn thành" : `Câu ${questionNumber}/${quiz.questions.length}`}</span>
              <span>{progress}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden>
              <div className="h-full rounded-full bg-gradient-to-r from-brand-600 to-sun-500 transition-[width] duration-500" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </div>

      {completed && (
        <div className="border-b border-emerald-100 bg-emerald-50 p-5 text-center" role="status" aria-live="polite">
          <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">Kết quả của em</p>
          <p className="mt-1 text-4xl font-black text-emerald-700">
            {score}<span className="text-xl text-emerald-600">/{quiz.questions.length}</span>
          </p>
          <p className="mt-1 text-sm text-emerald-900">
            {score === quiz.questions.length ? "Tuyệt vời! Em đã nắm bài rất chắc." : "Hãy xem lại lời giải ở từng câu rồi thử thêm một lượt nhé!"}
          </p>
        </div>
      )}

      <div className="p-5 sm:p-7">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-extrabold text-brand-700">
            {difficultyLabel[difficultyOf(currentQuestion)]}
          </span>
          <span className="text-xs font-semibold text-slate-500">
            HISEDU chọn mức này theo câu trả lời trước
          </span>
        </div>

        <fieldset className="min-w-0" disabled={Boolean(currentResult) || isSubmitting}>
          <legend className="flex w-full gap-3 font-extrabold leading-6 text-ink">
            <span className="grid h-8 min-w-8 place-items-center rounded-xl bg-brand-50 text-sm text-brand-700" aria-hidden>{questionNumber}</span>
            <span className="pt-1">{currentQuestion.prompt}</span>
          </legend>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {currentQuestion.options.map((option, optionIndex) => {
              const selected = selectedOptionId === option.id;
              const isCorrectOption = currentResult?.correct_option_id === option.id;
              const isWrongSelection = Boolean(currentResult && selected && !currentResult.correct);
              const stateClass = isCorrectOption
                ? "border-emerald-500 bg-emerald-50 text-emerald-950"
                : isWrongSelection
                  ? "border-rose-400 bg-rose-50 text-rose-950"
                  : selected
                    ? "border-brand-500 bg-brand-50 text-brand-950 ring-2 ring-brand-100"
                    : "border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:bg-brand-50/50";
              return (
                <label key={option.id} className={`flex min-h-14 cursor-pointer items-start gap-3 rounded-2xl border-2 p-3 transition ${stateClass}`}>
                  <input
                    type="radio"
                    name={`question-${currentQuestion.id}`}
                    value={option.id}
                    checked={selected}
                    onChange={() => {
                      setSelectedOptionId(option.id);
                      setError(null);
                    }}
                    className="peer sr-only"
                  />
                  <span className="grid h-7 min-w-7 place-items-center rounded-full border border-current text-xs font-black peer-focus-visible:ring-4 peer-focus-visible:ring-sun-400" aria-hidden>
                    {String.fromCharCode(65 + optionIndex)}
                  </span>
                  <span className="pt-0.5 text-sm font-semibold leading-5">{option.text}</span>
                  {isCorrectOption && <span className="ml-auto font-black text-emerald-700" aria-label="Đáp án đúng">✓</span>}
                  {isWrongSelection && <span className="ml-auto font-black text-rose-700" aria-label="Đáp án đã chọn không đúng">×</span>}
                </label>
              );
            })}
          </div>
        </fieldset>

        {currentResult && (
          <div className={`mt-4 rounded-2xl p-4 text-sm ${currentResult.correct ? "bg-emerald-50 text-emerald-950" : "bg-amber-50 text-amber-950"}`} aria-live="polite">
            <p className="font-extrabold">{currentResult.correct ? "Chính xác!" : "Chưa đúng rồi."}</p>
            <p className="mt-1 leading-6">{currentResult.explanation}</p>
            {currentResult.source_ids.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {currentResult.source_ids.map((sourceId) => (
                  <button
                    key={sourceId}
                    type="button"
                    onClick={() => {
                      const source = document.getElementById(`source-${sourceId}`);
                      source?.scrollIntoView({ behavior: "smooth", block: "center" });
                      source?.focus({ preventScroll: true });
                    }}
                    className="font-bold text-brand-700 underline underline-offset-2"
                  >
                    Xem nguồn [{sourceId}]
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {adaptiveMessage && (
          <div className="mt-3 flex items-start gap-2 rounded-2xl border border-brand-100 bg-brand-50 p-3 text-sm font-semibold text-brand-900" role="status">
            <span aria-hidden>↗</span>
            <p>{adaptiveMessage}</p>
          </div>
        )}

        <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-semibold text-slate-600" aria-live="polite">
            Đã hoàn thành {history.length}/{quiz.questions.length} câu · đúng {score} câu
          </p>
          {completed ? (
            <button type="button" onClick={retry} disabled={isResetting} className="min-h-12 rounded-2xl bg-brand-600 px-6 py-3 font-extrabold text-white hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60">
              {isResetting ? "Đang tạo lượt mới…" : "Làm lại quiz"}
            </button>
          ) : currentResult ? (
            <button type="button" onClick={continueQuiz} className="min-h-12 rounded-2xl bg-brand-600 px-6 py-3 font-extrabold text-white hover:bg-brand-700">
              Câu tiếp theo →
            </button>
          ) : (
            <button type="button" onClick={checkAnswer} disabled={isSubmitting || !selectedOptionId} className="min-h-12 rounded-2xl bg-brand-600 px-6 py-3 font-extrabold text-white shadow-lg shadow-blue-100 hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">
              {isSubmitting ? "Đang kiểm tra…" : "Kiểm tra đáp án"}
            </button>
          )}
        </div>
        {error && <p className="mt-3 text-sm font-semibold text-rose-700" role="alert">{error}</p>}

        {completed && history.length > 0 && (
          <details className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <summary className="cursor-pointer font-extrabold text-brand-700">Xem lại kết quả 5 câu</summary>
            <ol className="mt-3 space-y-2 text-sm text-slate-700">
              {history.map((item, index) => (
                <li key={item.question_id} className="flex gap-2">
                  <span className={`font-black ${item.correct ? "text-emerald-700" : "text-rose-700"}`} aria-hidden>{item.correct ? "✓" : "×"}</span>
                  <span>{index + 1}. {questionById.get(item.question_id)?.prompt ?? "Câu hỏi ôn tập"}</span>
                </li>
              ))}
            </ol>
          </details>
        )}
      </div>
    </section>
  );
}
