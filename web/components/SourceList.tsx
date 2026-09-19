import type { ReferenceSource } from "@/lib/types";
import { displayHostname, safeExternalUrl } from "@/lib/url";

interface Props {
  sources: ReferenceSource[];
}

const sourceTypeNames: Record<ReferenceSource["type"], string> = {
  dataset: "Dữ liệu HISEDU",
  sgk: "Sách giáo khoa",
  government: "Cơ quan nhà nước",
  museum: "Bảo tàng",
  wikipedia: "Wikipedia",
  news: "Báo chí",
  other: "Nguồn khác"
};

function locationLabel(source: ReferenceSource): string {
  if (source.page !== undefined && source.page !== null && String(source.page).trim()) {
    return `Trang ${source.page}`;
  }
  if (source.type === "sgk") {
    const missingPage = "Dữ liệu hiện tại chưa ghi nhận số trang";
    return source.locator?.trim()
      ? `${source.locator} · ${missingPage}`
      : missingPage;
  }
  if (source.locator?.trim()) return source.locator;
  return "";
}

export function SourceList({ sources }: Props) {
  return (
    <section className="section-card p-5 sm:p-7" aria-labelledby="sources-heading">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-2xl bg-emerald-50 text-xl" aria-hidden>🔎</span>
        <div>
          <h2 id="sources-heading" className="text-xl font-black text-ink sm:text-2xl">Nguồn tham khảo</h2>
          <p className="text-sm text-slate-600">Em có thể mở từng nguồn để kiểm tra và đọc thêm.</p>
        </div>
      </div>

      {sources.length === 0 ? (
        <p className="mt-5 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">
          Chưa có nguồn đủ tin cậy để hiển thị cho câu trả lời này.
        </p>
      ) : (
        <ol className="mt-5 grid gap-3">
          {sources.map((source) => {
            const safeUrl = safeExternalUrl(source.url);
            const location = locationLabel(source);
            return (
              <li
                key={source.id}
                id={`source-${source.id}`}
                tabIndex={-1}
                className="scroll-mt-8 rounded-3xl border border-slate-200 p-4 outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-50 sm:p-5"
              >
                <div className="flex items-start gap-3">
                  <span className="grid h-9 min-w-9 place-items-center rounded-xl bg-brand-50 px-2 text-xs font-black text-brand-700">
                    {source.id}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <h3 className="font-extrabold text-ink">{source.title}</h3>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{sourceTypeNames[source.type]}</span>
                    </div>
                    <p className="mt-1 text-sm font-semibold text-slate-600">{source.publisher}</p>
                    {location && <p className="mt-1 text-xs text-slate-500">{location}</p>}
                    {source.supports.length > 0 && (
                      <p className="mt-3 text-sm leading-6 text-slate-700">
                        Hỗ trợ nội dung: {source.supports.join(" · ")}
                      </p>
                    )}
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      {source.accessed_at && <span>Truy cập: {source.accessed_at}</span>}
                      {safeUrl && (
                        <a
                          href={safeUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-extrabold text-brand-700 underline decoration-brand-200 underline-offset-4 hover:text-brand-800"
                          aria-label={`Mở nguồn ${source.title} trên trang mới`}
                        >
                          {displayHostname(safeUrl)} <span aria-hidden>↗</span>
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
