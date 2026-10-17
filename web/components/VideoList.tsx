import type { LearningVideo } from "@/lib/types";
import { displayHostname, safeExternalUrl } from "@/lib/url";

interface Props {
  videos: LearningVideo[];
}

const labelNames: Record<string, string> = {
  cause: "Nguyên nhân",
  event: "Diễn biến",
  result: "Kết quả",
  meaning: "Ý nghĩa"
};

function FilmFrame() {
  return (
    <svg viewBox="0 0 320 150" className="absolute inset-0 h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id="film-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#351311" />
          <stop offset="1" stopColor="#8F2E29" />
        </linearGradient>
      </defs>
      <rect width="320" height="150" fill="url(#film-bg)" />
      <circle cx="270" cy="22" r="94" fill="none" stroke="#C99535" strokeOpacity=".18" strokeWidth="20" />
      <path d="M0 122C78 90 135 145 208 106C250 83 280 84 320 96V150H0Z" fill="#fff" fillOpacity=".05" />
      {[12, 42, 72, 102, 132].map((y) => <rect key={y} x="10" y={y} width="15" height="12" rx="2" fill="#F8ECC8" fillOpacity=".45" />)}
      {[12, 42, 72, 102, 132].map((y) => <rect key={y} x="295" y={y} width="15" height="12" rx="2" fill="#F8ECC8" fillOpacity=".45" />)}
    </svg>
  );
}

export function VideoList({ videos }: Props) {
  const safeVideos = videos
    .map((video) => ({ ...video, safeUrl: safeExternalUrl(video.url) }))
    .filter((video): video is LearningVideo & { safeUrl: string } => Boolean(video.safeUrl));

  return (
    <section className="section-card overflow-hidden" aria-labelledby="video-heading">
      <div className="flex flex-col gap-4 border-b border-stone-200 bg-[#fffaf0] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-7">
        <div className="flex items-start gap-3">
          <span className="history-serif grid h-11 w-11 shrink-0 place-items-center rounded-full border border-brand-200 bg-white text-sm font-bold text-brand-700" aria-hidden>
            03
          </span>
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.18em] text-brand-600">Tư liệu nghe nhìn</p>
            <h2 id="video-heading" className="history-serif text-xl font-bold text-ink sm:text-2xl">Xem để hiểu sâu hơn</h2>
            <p className="mt-1 text-sm text-stone-600">Video được đối chiếu theo đúng chủ đề và không tự động phát.</p>
          </div>
        </div>
        <span className="w-fit rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800">
          ✓ Kênh tin cậy
        </span>
      </div>

      {safeVideos.length === 0 ? (
        <div className="m-5 flex items-center gap-4 rounded-2xl border border-dashed border-stone-300 bg-stone-50/70 p-5 text-sm text-stone-600 sm:m-7" role="status">
          <span className="history-serif grid h-10 w-10 shrink-0 place-items-center rounded-full bg-stone-200 text-lg font-bold text-stone-500" aria-hidden>?</span>
          <div>
            <p className="font-bold text-stone-800">Đang thiếu video khớp chính xác</p>
            <p className="mt-0.5">HISEDU không hiển thị video khác chủ đề chỉ để lấp chỗ trống.</p>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 p-5 sm:p-7 md:grid-cols-2 xl:grid-cols-3">
          {safeVideos.slice(0, 6).map((video, index) => (
            <article key={video.safeUrl} className="group flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white transition duration-200 hover:-translate-y-1 hover:border-brand-200 hover:shadow-card">
              <div className="relative flex h-36 items-center justify-center overflow-hidden text-white">
                <FilmFrame />
                <span className="absolute left-4 top-3 text-[10px] font-extrabold uppercase tracking-[0.18em] text-white/70">Tư liệu {String(index + 1).padStart(2, "0")}</span>
                <span className="relative grid h-14 w-14 place-items-center rounded-full border border-white/40 bg-white/95 pl-1 text-xl text-brand-700 shadow-xl transition group-hover:scale-105" aria-hidden>▶</span>
              </div>
              <div className="flex flex-1 flex-col p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full border border-brand-100 bg-brand-50 px-2 py-1 font-bold text-brand-700">
                    {labelNames[video.label] ?? video.label}
                  </span>
                  <span className="truncate text-stone-500">{displayHostname(video.safeUrl)}</span>
                </div>
                <h3 className="history-serif text-lg font-bold leading-6 text-ink">{video.title}</h3>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-brand-700">{video.publisher}</p>
                <p className="mt-3 flex-1 text-sm leading-6 text-stone-600">{video.relevance}</p>
                <a
                  href={video.safeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-extrabold text-brand-700 transition hover:border-brand-700 hover:bg-brand-700 hover:text-white"
                  aria-label={`Xem video ${video.title} trên trang mới`}
                >
                  Xem video <span className="ml-1" aria-hidden>↗</span>
                </a>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
