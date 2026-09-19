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

export function VideoList({ videos }: Props) {
  const safeVideos = videos
    .map((video) => ({ ...video, safeUrl: safeExternalUrl(video.url) }))
    .filter((video): video is LearningVideo & { safeUrl: string } => Boolean(video.safeUrl));

  return (
    <section className="section-card p-5 sm:p-7" aria-labelledby="video-heading">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-2xl bg-rose-50 text-xl" aria-hidden>🎬</span>
        <div>
          <h2 id="video-heading" className="text-xl font-black text-ink sm:text-2xl">Xem để hiểu sâu hơn</h2>
          <p className="text-sm text-slate-600">Video được chọn theo nội dung em vừa học và sẽ không tự động phát.</p>
        </div>
      </div>

      {safeVideos.length === 0 ? (
        <div className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600" role="status">
          Chưa tìm thấy video đáng tin cậy phù hợp với câu hỏi này.
        </div>
      ) : (
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {safeVideos.slice(0, 3).map((video) => (
            <article key={video.safeUrl} className="group flex flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white transition hover:-translate-y-1 hover:shadow-card">
              <div className="flex h-28 items-center justify-center bg-gradient-to-br from-brand-700 to-brand-500 text-white">
                <span className="grid h-14 w-14 place-items-center rounded-full bg-white/95 pl-1 text-2xl text-brand-700 shadow-xl" aria-hidden>▶</span>
              </div>
              <div className="flex flex-1 flex-col p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-rose-50 px-2 py-1 font-bold text-rose-700">
                    {labelNames[video.label] ?? video.label}
                  </span>
                  <span className="truncate text-slate-500">{displayHostname(video.safeUrl)}</span>
                </div>
                <h3 className="font-extrabold leading-6 text-ink">{video.title}</h3>
                <p className="mt-1 text-xs font-semibold text-brand-700">{video.publisher}</p>
                <p className="mt-3 flex-1 text-sm leading-6 text-slate-600">{video.relevance}</p>
                <a
                  href={video.safeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 inline-flex min-h-11 items-center justify-center rounded-2xl bg-brand-50 px-4 py-2 text-sm font-extrabold text-brand-700 transition hover:bg-brand-100"
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
