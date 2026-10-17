import { CitationLinks } from "@/components/CitationLinks";
import type { LearningAnswer, MindMapData } from "@/lib/types";

interface Props {
  question: string;
  answer: LearningAnswer;
  mindmap?: MindMapData;
}

type FactKind = "time" | "event" | "person" | "meaning";

interface FactRange {
  start: number;
  end: number;
  kind: FactKind;
}

interface StructuredFact {
  kind: FactKind;
  term: string;
}

const SAFE_FACT_PATTERNS: ReadonlyArray<{ kind: FactKind; pattern: RegExp }> = [
  {
    kind: "time",
    pattern: /\b\d{1,2}[/-]\d{1,2}[/-]\d{3,4}\b|\b(?:1\d{3}|20\d{2})(?:\s*[–—-]\s*(?:1\d{3}|20\d{2}))?\b|thế\s+kỷ\s+(?:[IVXLCDM]+|\d{1,2})/giu
  },
  {
    kind: "meaning",
    // Stop at a sentence boundary instead of a fixed character count. A hard
    // limit could end the highlight halfway through a Vietnamese word.
    pattern: /(?:[Ýý]\s*nghĩa|[Tt]ác động|[Vv]ai trò|[Kk]ết quả)\s*:?\s+[^.!?;\n]{3,}|(?:[Đđ]ánh dấu|[Mm]ở ra|[Kk]hẳng định|[Tt]ạo tiền đề|[Cc]hấm dứt|[Ll]ật đổ|[Tt]hành lập)\s+[^.!?;\n]{3,}/gu
  }
];

const IDENTITY_FALLBACK_PATTERNS: ReadonlyArray<{ kind: FactKind; pattern: RegExp }> = [
  {
    kind: "event",
    pattern: /(?:[Cc]ách mạng|[Kk]hởi nghĩa|[Pp]hong trào|[Cc]hiến tranh|[Cc]hiến dịch|[Tt]rận|[Hh]iệp định|[Tt]uyên ngôn)\s+(?:(?!(?:bùng|nổ|diễn|đã|là|do|vì|nhằm|dẫn|xảy|được|có|vào|từ|ở|tiếp|củng)\b)[\p{L}\p{N}][\p{L}\p{N}’'–-]*)(?:\s+(?!(?:bùng|nổ|diễn|đã|là|do|vì|nhằm|dẫn|xảy|được|có|vào|từ|ở|tiếp|củng)\b)[\p{L}\p{N}][\p{L}\p{N}’'–-]*){0,6}/gu
  },
  {
    kind: "person",
    pattern: /(?:[Vv]ua|[Hh]oàng đế|[Cc]hủ tịch|[Đđ]ại tướng|[Tt]ướng|[Ll]ãnh tụ|[Aa]nh hùng dân tộc)\s+(?:\p{Lu}[\p{L}’'-]+)(?:\s+(?:\p{Lu}[\p{L}’'-]+)){0,4}/gu
  },
  {
    kind: "person",
    pattern: /(?<![\p{L}\p{N}])(?:\p{Lu}[\p{L}’'-]+)(?:\s+(?:\p{Lu}[\p{L}’'-]+)){1,4}(?![\p{L}\p{N}])/gu
  }
];

const FACT_PRIORITY: Record<FactKind, number> = {
  time: 0,
  person: 1,
  event: 2,
  meaning: 3
};

const FACT_STYLES: Record<FactKind, string> = {
  time: "bg-red-100 text-red-800 decoration-red-300",
  event: "bg-rose-100 text-red-900 decoration-red-400",
  person: "bg-orange-100 text-red-800 decoration-orange-300",
  meaning: "bg-amber-100 text-red-900 decoration-red-300"
};

const FACT_TITLES: Record<FactKind, string> = {
  time: "Mốc thời gian",
  event: "Sự kiện lịch sử",
  person: "Nhân vật lịch sử",
  meaning: "Ý nghĩa hoặc tác động"
};

const GENERIC_MINDMAP_LABELS = new Set([
  "nguyên nhân",
  "diễn biến",
  "nhân vật",
  "ý nghĩa",
  "kết quả",
  "mốc thời gian",
  "ghi nhớ nhanh",
  "chủ đề"
]);

function structuredFactsFromMindmap(mindmap?: MindMapData): StructuredFact[] {
  if (!mindmap) return [];
  const facts: StructuredFact[] = [];
  const seen = new Set<string>();
  const add = (kind: FactKind, raw?: string | null) => {
    const term = raw?.trim();
    if (!term || term.length < 2) return;
    const normalizedTerm = term.toLocaleLowerCase("vi");
    // Structural branch names organize the mind map but are not historical
    // facts, so highlighting them in prose would create noisy false positives.
    if (GENERIC_MINDMAP_LABELS.has(normalizedTerm)) return;
    const key = `${kind}:${normalizedTerm}`;
    if (seen.has(key)) return;
    seen.add(key);
    facts.push({ kind, term });
  };

  add("event", mindmap.title);
  for (const node of mindmap.nodes) {
    if (node.type === "time" || node.type === "event" || node.type === "person" || node.type === "meaning") {
      add(node.type, node.label);
    }
    add("time", node.time);
    for (const person of node.people ?? []) add("person", person);
  }
  return facts;
}

function addPatternRanges(matches: FactRange[], text: string, patterns: ReadonlyArray<{ kind: FactKind; pattern: RegExp }>) {
  for (const { kind, pattern } of patterns) {
    pattern.lastIndex = 0;
    for (const match of text.matchAll(pattern)) {
      const start = match.index;
      const value = match[0];
      if (start !== undefined && value.trim()) matches.push({ start, end: start + value.length, kind });
    }
  }
}

function addStructuredRanges(matches: FactRange[], text: string, facts: StructuredFact[]) {
  const haystack = text.toLocaleLowerCase("vi");
  for (const { kind, term } of facts) {
    const needle = term.toLocaleLowerCase("vi");
    let offset = 0;
    while (offset < haystack.length) {
      const start = haystack.indexOf(needle, offset);
      if (start < 0) break;
      const end = start + needle.length;
      const before = start > 0 ? text[start - 1] : "";
      const after = end < text.length ? text[end] : "";
      if (!/[\p{L}\p{N}]/u.test(before) && !/[\p{L}\p{N}]/u.test(after)) {
        matches.push({ start, end, kind });
      }
      offset = Math.max(end, start + 1);
    }
  }
}

function findFactRanges(text: string, structuredFacts: StructuredFact[]): FactRange[] {
  const matches: FactRange[] = [];
  addStructuredRanges(matches, text, structuredFacts);
  addPatternRanges(matches, text, SAFE_FACT_PATTERNS);
  // Structured mind-map terms are authoritative. Broad name/event heuristics
  // are only a compatibility fallback for older responses without a mind map.
  if (structuredFacts.length === 0) addPatternRanges(matches, text, IDENTITY_FALLBACK_PATTERNS);
  return matches;
}

function HighlightFacts({ text, structuredFacts }: { text: string; structuredFacts: StructuredFact[] }) {
  const ranges = findFactRanges(text, structuredFacts);
  if (ranges.length === 0) return <>{text}</>;

  const boundaries = Array.from(new Set([0, text.length, ...ranges.flatMap(({ start, end }) => [start, end])]))
    .sort((left, right) => left - right);

  return boundaries.slice(0, -1).map((start, index) => {
    const end = boundaries[index + 1];
    const content = text.slice(start, end);
    const active = ranges
      .filter((range) => range.start <= start && range.end >= end)
      .sort((left, right) => FACT_PRIORITY[left.kind] - FACT_PRIORITY[right.kind])[0];

    if (!active) return <span key={`${start}-${end}`}>{content}</span>;
    return (
      <mark
        key={`${start}-${end}-${active.kind}`}
        data-key-fact="true"
        data-fact-kind={active.kind}
        title={FACT_TITLES[active.kind]}
        className={`rounded px-1 font-extrabold underline decoration-2 underline-offset-2 ${FACT_STYLES[active.kind]}`}
      >
        {content}
      </mark>
    );
  });
}

export function AnswerPanel({ question, answer, mindmap }: Props) {
  const structuredFacts = structuredFactsFromMindmap(mindmap);
  return (
    <article className="section-card overflow-hidden" aria-labelledby="answer-heading">
      <div className="relative overflow-hidden border-b-4 border-sun-400 bg-brand-950 p-5 text-white sm:p-7">
        <div className="timeline-dots absolute inset-y-0 right-0 w-1/3 opacity-30" aria-hidden />
        <div className="flex items-start gap-3">
          <span className="history-serif grid h-11 w-11 shrink-0 place-items-center rounded-full border border-sun-400/70 bg-white/10 text-lg font-bold text-sun-100" aria-hidden>
            01
          </span>
          <div className="relative">
            <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-sun-100">Giải đáp chủ đề</p>
            <h2 id="answer-heading" className="history-serif mt-1 text-xl font-bold leading-snug text-white sm:text-3xl">
              {question || "Câu hỏi trong ảnh"}
            </h2>
          </div>
        </div>
        <p className="relative mt-5 rounded-2xl border border-white/15 border-l-4 border-l-sun-400 bg-white/10 p-4 whitespace-pre-line text-base font-semibold leading-7 text-white/95 backdrop-blur-sm sm:text-lg">
          <HighlightFacts text={answer.summary} structuredFacts={structuredFacts} />
          <CitationLinks ids={answer.citation_ids} />
        </p>
      </div>

      <div className="p-5 sm:p-7">
        <div className="mb-5 flex items-center gap-3">
          <span className="h-px w-9 bg-sun-400" aria-hidden />
          <h3 className="history-serif text-xl font-bold text-ink sm:text-2xl">Cùng tìm hiểu kỹ hơn</h3>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {answer.sections.map((section, index) => (
            <section key={`${section.heading}-${index}`} className="rounded-2xl border border-stone-200 bg-[#fffdf8] p-5 transition hover:border-brand-200 hover:shadow-sm">
              <div className="flex items-center gap-2">
                <span className="history-serif grid h-8 w-8 shrink-0 place-items-center rounded-full border border-brand-200 bg-brand-50 text-sm font-bold text-brand-700" aria-hidden>
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h4 className="history-serif text-lg font-bold text-red-800">{section.heading}</h4>
              </div>
              <p className="mt-3 whitespace-pre-line text-sm leading-7 text-stone-700 sm:text-base">
                <HighlightFacts text={section.content} structuredFacts={structuredFacts} />
                <CitationLinks ids={section.citation_ids} />
              </p>
            </section>
          ))}
        </div>

        {answer.key_points.length > 0 && (
          <aside className="mt-6 overflow-hidden rounded-2xl border border-brand-200 bg-brand-50" aria-labelledby="remember-heading">
            <div className="border-b border-brand-200 bg-brand-700 px-5 py-3 text-white">
              <h3 id="remember-heading" className="history-serif flex items-center gap-2 text-lg font-bold">
                <span className="text-sun-100" aria-hidden>◆</span> Thông tin chính cần nhớ
              </h3>
            </div>
            <div className="p-5">
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.14em] text-brand-700">Ghi vào vở học tập</p>
            <ul className="space-y-2">
              {answer.key_points.map((point, index) => (
                <li key={`${point}-${index}`} className="flex gap-3 rounded-xl border border-brand-100 bg-white px-4 py-3 text-sm font-bold leading-6 text-red-950 shadow-sm sm:text-base">
                  <span className="history-serif font-bold text-red-700" aria-hidden>{index + 1}.</span>
                  <span><HighlightFacts text={point} structuredFacts={structuredFacts} /></span>
                </li>
              ))}
            </ul>
            </div>
          </aside>
        )}
      </div>
    </article>
  );
}
