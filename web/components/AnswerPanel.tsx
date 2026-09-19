import { CitationLinks } from "@/components/CitationLinks";
import type { LearningAnswer } from "@/lib/types";

interface Props {
  question: string;
  answer: LearningAnswer;
}

export function AnswerPanel({ question, answer }: Props) {
  return (
    <article className="section-card overflow-hidden" aria-labelledby="answer-heading">
      <div className="border-b border-brand-100 bg-gradient-to-r from-brand-50 to-white p-5 sm:p-7">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand-600 text-xl text-white" aria-hidden>
            💡
          </span>
          <div>
            <p className="text-xs font-extrabold uppercase tracking-wider text-brand-600">Trả lời nhanh</p>
            <h2 id="answer-heading" className="mt-1 text-xl font-black text-ink sm:text-2xl">
              {question || "Câu hỏi trong ảnh"}
            </h2>
          </div>
        </div>
        <p className="mt-5 whitespace-pre-line text-base font-medium leading-7 text-slate-800 sm:text-lg">
          {answer.summary}
          <CitationLinks ids={answer.citation_ids} />
        </p>
      </div>

      <div className="p-5 sm:p-7">
        <h3 className="text-lg font-black text-ink sm:text-xl">Cùng tìm hiểu kỹ hơn</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {answer.sections.map((section, index) => (
            <section key={`${section.heading}-${index}`} className="rounded-3xl border border-slate-100 bg-slate-50/70 p-5">
              <div className="flex items-center gap-2">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-white text-xs font-black text-brand-700 shadow-sm" aria-hidden>
                  {index + 1}
                </span>
                <h4 className="font-extrabold text-ink">{section.heading}</h4>
              </div>
              <p className="mt-3 whitespace-pre-line text-sm leading-6 text-slate-700 sm:text-base">
                {section.content}
                <CitationLinks ids={section.citation_ids} />
              </p>
            </section>
          ))}
        </div>

        {answer.key_points.length > 0 && (
          <aside className="mt-6 rounded-3xl border border-amber-200 bg-sun-50 p-5" aria-labelledby="remember-heading">
            <h3 id="remember-heading" className="flex items-center gap-2 font-black text-amber-950">
              <span aria-hidden>⭐</span> Ghi nhớ nhanh
            </h3>
            <ul className="mt-3 space-y-2">
              {answer.key_points.map((point, index) => (
                <li key={`${point}-${index}`} className="flex gap-2 text-sm leading-6 text-amber-950 sm:text-base">
                  <span className="font-black text-amber-600" aria-hidden>•</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </aside>
        )}
      </div>
    </article>
  );
}

