"use client";

import { useEffect, useMemo, useState } from "react";
import { submitQuizAnswers } from "@/lib/api";
import type { QuizData, QuizSubmitResponse } from "@/lib/types";

interface Props {
  quiz: QuizData;
  onSubmit?: (quizId: string, answers: Record<string, string>) => Promise<QuizSubmitResponse>;
}

export function Quiz({ quiz, onSubmit = submitQuizAnswers }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizSubmitResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setAnswers({});
    setResult(null);
    setError(null);
  }, [quiz.quiz_id]);

  const resultByQuestion = useMemo(
    () => new Map(result?.results.map((item) => [item.question_id, item]) ?? []),
    [result]
  );
  const answeredCount = Object.keys(answers).length;

  async function submit() {
    if (answeredCount !== quiz.questions.length) {
      setError(`Em còn ${quiz.questions.length - answeredCount} câu chưa chọn đáp án.`);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      setResult(await onSubmit(quiz.quiz_id, answers));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa thể chấm bài. Em hãy thử lại nhé.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function retry() {
    setAnswers({});
    setResult(null);
    setError(null);
    document.getElementById(`quiz-${quiz.quiz_id}`)?.scrollIntoView({ behavior: "smooth" });
  }

  if (quiz.questions.length === 0) return null;

  return (
    <section id={`quiz-${quiz.quiz_id}`} className="section-card scroll-mt-6 overflow-hidden" aria-labelledby="quiz-heading">
      <div className="bg-gradient-to-r from-amber-50 to-white p-5 sm:p-7">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-sun-100 text-xl" aria-hidden>🏆</span>
          <div>
            <p className="text-xs font-extrabold uppercase tracking-wider text-amber-700">Thử thách ghi nhớ</p>
            <h2 id="quiz-heading" className="text-xl font-black text-ink sm:text-2xl">Quiz 5 câu</h2>
            <p className="mt-1 text-sm text-slate-600">Chọn một đáp án cho mỗi câu. Đáp án chỉ hiện sau khi em nộp bài.</p>
          </div>
        </div>
      </div>

      {result && (
        <div className="border-y border-emerald-100 bg-emerald-50 p-5 text-center" role="status" aria-live="polite">
          <p className="text-sm font-bold uppercase tracking-wide text-emerald-800">Kết quả của em</p>
          <p className="mt-1 text-4xl font-black text-emerald-700">
            {result.score}<span className="text-xl text-emerald-600">/{result.max_score}</span>
          </p>
          <p className="mt-1 text-sm text-emerald-900">
            {result.score === result.max_score ? "Tuyệt vời! Em đã nắm bài rất chắc." : "Cùng xem giải thích để nhớ bài lâu hơn nhé!"}
          </p>
        </div>
      )}

      <div className="space-y-7 p-5 sm:p-7">
        {quiz.questions.map((question, questionIndex) => {
          const feedback = resultByQuestion.get(question.id);
          return (
            <fieldset key={question.id} className="min-w-0">
              <legend className="flex w-full gap-3 font-extrabold leading-6 text-ink">
                <span className="grid h-8 min-w-8 place-items-center rounded-xl bg-brand-50 text-sm text-brand-700" aria-hidden>{questionIndex + 1}</span>
                <span className="pt-1">{question.prompt}</span>
              </legend>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {question.options.map((option, optionIndex) => {
                  const selected = answers[question.id] === option.id;
                  const isCorrectOption = feedback?.correct_option_id === option.id;
                  const isWrongSelection = Boolean(feedback && selected && !feedback.correct);
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
                        name={`question-${question.id}`}
                        value={option.id}
                        checked={selected}
                        disabled={Boolean(result) || isSubmitting}
                        onChange={() => {
                          setAnswers((current) => ({ ...current, [question.id]: option.id }));
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

              {feedback && (
                <div className={`mt-3 rounded-2xl p-4 text-sm ${feedback.correct ? "bg-emerald-50 text-emerald-950" : "bg-amber-50 text-amber-950"}`} aria-live="polite">
                  <p className="font-extrabold">{feedback.correct ? "Chính xác!" : "Chưa đúng rồi."}</p>
                  <p className="mt-1 leading-6">{feedback.explanation}</p>
                  {feedback.source_ids.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {feedback.source_ids.map((sourceId) => (
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
            </fieldset>
          );
        })}

        <div className="border-t border-slate-100 pt-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-semibold text-slate-600" aria-live="polite">
              {result ? "Em đã hoàn thành lượt này." : `Đã trả lời ${answeredCount}/${quiz.questions.length} câu`}
            </p>
            {result ? (
              <button type="button" onClick={retry} className="min-h-12 rounded-2xl bg-brand-600 px-6 py-3 font-extrabold text-white hover:bg-brand-700">
                Làm lại quiz
              </button>
            ) : (
              <button type="button" onClick={submit} disabled={isSubmitting} className="min-h-12 rounded-2xl bg-brand-600 px-6 py-3 font-extrabold text-white shadow-lg shadow-blue-100 hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60">
                {isSubmitting ? "Đang chấm bài…" : "Nộp bài"}
              </button>
            )}
          </div>
          {error && <p className="mt-3 text-sm font-semibold text-rose-700" role="alert">{error}</p>}
        </div>
      </div>
    </section>
  );
}
