import type { HistoricalImage, LearningAnswer } from "@/lib/types";
import { safeExternalUrl } from "@/lib/url";

interface Props {
  question: string;
  answer: LearningAnswer;
  materials?: HistoricalImage[];
}

type CuratedHistoricalImage = HistoricalImage & { topics: string[] };

const MEDIA_LABELS: Record<HistoricalImage["media_type"], string> = {
  photograph: "Ảnh chụp",
  painting: "Tranh lịch sử",
  engraving: "Bản khắc",
  portrait: "Chân dung",
  map: "Bản đồ",
  document: "Văn kiện",
  artifact: "Hiện vật"
};

const MATERIALS: CuratedHistoricalImage[] = [
  {
    id: "battle-of-naseby",
    topics: ["cách mạng tư sản anh", "nội chiến anh", "oliver cromwell", "quốc hội anh", "charles i"],
    title: "Trận Naseby trong Nội chiến Anh",
    description:
      "Bản khắc mô tả trận Naseby năm 1645, thắng lợi quyết định của lực lượng Quốc hội trong Nội chiến Anh.",
    image_url: "/historical/battle-of-naseby.jpg",
    source_url:
      "https://commons.wikimedia.org/wiki/File:Edward_Radclyffe_-_Battle_of_Naseby_-_B1998.14.672_-_Yale_Center_for_British_Art.jpg",
    institution: "Yale Center for British Art",
    license: "CC0",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
    creator: "Edward Radclyffe",
    date: "Thế kỉ XIX (tái hiện trận đánh năm 1645)",
    media_type: "engraving",
    alt: "Bản khắc tái hiện quân đội giao chiến tại trận Naseby trong Nội chiến Anh",
    observation_prompt: "Quan sát cách hai lực lượng được bố trí và tìm chi tiết thể hiện quy mô của trận đánh.",
    relevance: "Minh họa một bước ngoặt quân sự của Cách mạng tư sản Anh."
  },
  {
    id: "oliver-cromwell-1649",
    topics: ["cách mạng tư sản anh", "nội chiến anh", "oliver cromwell", "quốc hội anh"],
    title: "Chân dung Oliver Cromwell, khoảng năm 1649",
    description:
      "Chân dung người lãnh đạo lực lượng Quốc hội; đây là tác phẩm hội họa, không phải ảnh chụp đương thời.",
    image_url: "/historical/oliver-cromwell-1649.jpg",
    source_url:
      "https://commons.wikimedia.org/wiki/File:Portrait_of_Oliver_Cromwell,_circa_1649.jpg",
    institution: "Cromwell Museum",
    license: "Phạm vi công cộng",
    license_url: "https://creativecommons.org/publicdomain/mark/1.0/",
    creator: "Samuel Cooper (quy thuộc)",
    date: "Khoảng năm 1649",
    media_type: "portrait",
    alt: "Chân dung Oliver Cromwell mặc áo giáp, nhìn nghiêng sang trái",
    observation_prompt: "Từ trang phục và tư thế nhân vật, em nhận ra tác giả muốn nhấn mạnh vai trò nào của Cromwell?",
    relevance: "Giúp nhận diện nhân vật tiêu biểu của Cách mạng tư sản Anh."
  },
  {
    id: "storming-of-bastille",
    topics: ["cách mạng tư sản pháp", "cách mạng pháp", "bastille", "ba-xti", "14 tháng 7 năm 1789"],
    title: "Cuộc tấn công pháo đài Bastille, ngày 14/7/1789",
    description:
      "Tranh của Henry Singleton, sáng tác khoảng 1789–1791, tái hiện sự kiện mở đầu Cách mạng Pháp.",
    image_url: "/historical/storming-of-bastille.jpg",
    source_url:
      "https://commons.wikimedia.org/wiki/File:Henry_Singleton_the_Storming_of_the_Bastille.jpg",
    institution: "Wikimedia Commons",
    license: "Phạm vi công cộng",
    license_url: "https://creativecommons.org/publicdomain/mark/1.0/",
    creator: "Henry Singleton",
    date: "Khoảng 1789–1791",
    media_type: "painting",
    alt: "Tranh tái hiện người dân Paris tấn công pháo đài Bastille",
    observation_prompt: "Tìm những chi tiết cho thấy vai trò của quần chúng trong sự kiện ngày 14/7/1789.",
    relevance: "Tái hiện trực quan sự kiện mở đầu Cách mạng tư sản Pháp."
  },
  {
    id: "declaration-rights-1789",
    topics: [
      "cách mạng tư sản pháp",
      "cách mạng pháp",
      "tuyên ngôn nhân quyền",
      "tuyên ngôn nhân quyền và dân quyền",
      "quyền con người"
    ],
    title: "Tuyên ngôn Nhân quyền và Dân quyền năm 1789",
    description:
      "Bản thể hiện trực quan văn kiện năm 1789, hiện thuộc bộ sưu tập của Musée Carnavalet, Paris.",
    image_url: "/historical/declaration-rights-1789.jpg",
    source_url:
      "https://commons.wikimedia.org/wiki/File:Declaration_of_the_Rights_of_Man_and_of_the_Citizen_in_1789.jpg",
    institution: "Musée Carnavalet / Paris Musées",
    license: "CC0",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
    creator: "Jean-Jacques-François Le Barbier (quy thuộc)",
    date: "Năm 1789",
    media_type: "document",
    alt: "Bản trang trí Tuyên ngôn Nhân quyền và Dân quyền của Pháp năm 1789",
    observation_prompt: "Quan sát biểu tượng ở phía trên văn kiện và liên hệ với tư tưởng tự do, bình đẳng.",
    relevance: "Cho thấy tư tưởng và thành quả quan trọng của Cách mạng tư sản Pháp."
  }
];

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi")
    .replace(/đ/g, "d")
    .replace(/[-_/]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function safeLocalImageUrl(value: string): string | null {
  if (!value.startsWith("/historical/") || value.includes("..") || /["'<>\\]/.test(value)) return null;
  return value;
}

export function selectHistoricalMaterials(question: string, answer: LearningAnswer): HistoricalImage[] {
  const searchable = normalize(
    [
      question,
      answer.summary,
      ...answer.key_points,
      ...answer.sections.flatMap((section) => [section.heading, section.content])
    ].join(" ")
  );
  return MATERIALS.filter((material) =>
    material.topics.some((topic) => searchable.includes(normalize(topic)))
  ).slice(0, 4);
}

export function HistoricalSourceGallery({ question, answer, materials }: Props) {
  const candidates = materials?.length ? materials : selectHistoricalMaterials(question, answer);
  const safeMaterials = candidates
    .map((material) => ({
      ...material,
      safeImageUrl: safeLocalImageUrl(material.image_url),
      safeSourceUrl: safeExternalUrl(material.source_url),
      safeLicenseUrl: safeExternalUrl(material.license_url)
    }))
    .filter(
      (material): material is HistoricalImage & {
        safeImageUrl: string;
        safeSourceUrl: string;
        safeLicenseUrl: string | null;
      } => Boolean(material.safeImageUrl && material.safeSourceUrl)
    )
    .slice(0, 4);

  if (safeMaterials.length === 0) return null;

  return (
    <section className="section-card overflow-hidden" aria-labelledby="historical-materials-heading">
      <div className="border-b border-stone-200 bg-[#fffaf0] p-5 sm:p-7">
        <div className="flex items-start gap-3">
          <span
            className="history-serif grid h-11 w-11 shrink-0 place-items-center rounded-full border border-brand-200 bg-white text-sm font-bold text-brand-700"
            aria-hidden
          >
            TL
          </span>
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.18em] text-brand-600">
              Quan sát sử liệu
            </p>
            <h2 id="historical-materials-heading" className="history-serif text-xl font-bold text-ink sm:text-2xl">
              Tư liệu lịch sử xác thực
            </h2>
            <p className="mt-1 text-sm leading-6 text-stone-600">
              Quan sát ảnh, đọc chú thích rồi mở hồ sơ nguồn để phân biệt ảnh chụp, tranh tái hiện và văn kiện.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-5 p-5 sm:p-7 md:grid-cols-2 xl:grid-cols-3">
        {safeMaterials.map((material) => (
          <figure key={material.id} className="flex min-w-0 flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
            <div className="relative flex aspect-[4/3] items-center justify-center bg-stone-100 p-2">
              {/* Curated thumbnails are self-hosted; attribution is displayed below. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={material.safeImageUrl}
                alt={material.alt}
                loading="lazy"
                decoding="async"
                className="h-full w-full object-contain"
              />
              <span className="absolute left-3 top-3 rounded-full bg-white/95 px-3 py-1 text-[11px] font-black uppercase tracking-wide text-stone-700 shadow-sm">
                {MEDIA_LABELS[material.media_type]}
              </span>
            </div>

            <figcaption className="flex flex-1 flex-col p-4 sm:p-5">
              <h3 className="history-serif text-lg font-bold leading-6 text-ink">{material.title}</h3>
              <p className="mt-2 text-sm leading-6 text-stone-600">{material.description}</p>
              {material.relevance && (
                <p className="mt-3 rounded-xl bg-sky-50 px-3 py-2 text-sm leading-5 text-sky-950">
                  <strong>Liên hệ bài học:</strong> {material.relevance}
                </p>
              )}

              <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-xs leading-5 text-stone-600">
                {material.creator && <><dt className="font-bold text-stone-800">Tác giả:</dt><dd>{material.creator}</dd></>}
                {material.date && <><dt className="font-bold text-stone-800">Niên đại:</dt><dd>{material.date}</dd></>}
                <dt className="font-bold text-stone-800">Lưu giữ:</dt><dd>{material.institution}</dd>
                <dt className="font-bold text-stone-800">Quyền dùng:</dt>
                <dd>
                  {material.safeLicenseUrl ? (
                    <a className="font-semibold underline underline-offset-2 hover:text-brand-800" href={material.safeLicenseUrl} target="_blank" rel="noopener noreferrer">
                      {material.license}
                    </a>
                  ) : material.license}
                </dd>
              </dl>

              {material.observation_prompt && (
                <details className="mt-4 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-700">
                  <summary className="cursor-pointer font-bold text-stone-900">Gợi ý quan sát ảnh</summary>
                  <p className="mt-2 leading-6">{material.observation_prompt}</p>
                </details>
              )}

              <a
                href={material.safeSourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex min-h-10 items-center font-extrabold text-brand-700 underline decoration-brand-200 underline-offset-4 hover:text-brand-900"
                aria-label={`Xem hồ sơ nguồn của ${material.title}`}
              >
                Xem hồ sơ nguồn <span className="ml-1" aria-hidden>↗</span>
              </a>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
