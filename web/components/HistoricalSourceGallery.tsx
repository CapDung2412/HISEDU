import type { LearningAnswer } from "@/lib/types";

interface Props {
  question: string;
  answer: LearningAnswer;
}

interface HistoricalMaterial {
  id: string;
  topics: string[];
  title: string;
  description: string;
  imageUrl: string;
  sourceUrl: string;
  institution: string;
  license: string;
}

const MATERIALS: HistoricalMaterial[] = [
  {
    id: "battle-of-naseby",
    topics: ["cách mạng tư sản anh", "nội chiến anh", "oliver cromwell", "quốc hội anh", "charles i"],
    title: "Trận Naseby trong Nội chiến Anh",
    description:
      "Bản khắc mô tả trận Naseby năm 1645, thắng lợi quyết định của lực lượng Quốc hội trong Nội chiến Anh.",
    imageUrl: "/historical/battle-of-naseby.jpg",
    sourceUrl:
      "https://commons.wikimedia.org/wiki/File:Edward_Radclyffe_-_Battle_of_Naseby_-_B1998.14.672_-_Yale_Center_for_British_Art.jpg",
    institution: "Yale Center for British Art",
    license: "CC0"
  },
  {
    id: "oliver-cromwell-1649",
    topics: ["cách mạng tư sản anh", "nội chiến anh", "oliver cromwell", "quốc hội anh"],
    title: "Chân dung Oliver Cromwell, khoảng năm 1649",
    description:
      "Chân dung nhân vật lãnh đạo lực lượng Quốc hội; dùng để nhận diện nhân vật, không phải ảnh chụp đương thời.",
    imageUrl: "/historical/oliver-cromwell-1649.jpg",
    sourceUrl:
      "https://commons.wikimedia.org/wiki/File:Portrait_of_Oliver_Cromwell,_circa_1649.jpg",
    institution: "Cromwell Museum",
    license: "Phạm vi công cộng"
  },
  {
    id: "storming-of-bastille",
    topics: ["cách mạng tư sản pháp", "cách mạng pháp", "bastille", "ba-xti", "14 tháng 7 năm 1789"],
    title: "Cuộc tấn công pháo đài Bastille, ngày 14/7/1789",
    description:
      "Tranh lịch sử của Henry Singleton, được sáng tác khoảng 1789–1791, tái hiện sự kiện mở đầu Cách mạng Pháp.",
    imageUrl: "/historical/storming-of-bastille.jpg",
    sourceUrl:
      "https://commons.wikimedia.org/wiki/File:Henry_Singleton_the_Storming_of_the_Bastille.jpg",
    institution: "Wikimedia Commons",
    license: "Phạm vi công cộng"
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
    imageUrl: "/historical/declaration-rights-1789.jpg",
    sourceUrl:
      "https://commons.wikimedia.org/wiki/File:Declaration_of_the_Rights_of_Man_and_of_the_Citizen_in_1789.jpg",
    institution: "Musée Carnavalet / Paris Musées",
    license: "CC0"
  }
];

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("vi")
    .replace(/đ/g, "d");
}

export function selectHistoricalMaterials(question: string, answer: LearningAnswer): HistoricalMaterial[] {
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
  ).slice(0, 2);
}

export function HistoricalSourceGallery({ question, answer }: Props) {
  const materials = selectHistoricalMaterials(question, answer);
  if (materials.length === 0) return null;

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
            <p className="mt-1 text-sm text-stone-600">
              Ảnh tác phẩm hoặc văn kiện đã được tuyển chọn; mở nguồn để xem mô tả và giấy phép gốc.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 p-5 sm:p-7 md:grid-cols-2">
        {materials.map((material) => (
          <figure key={material.id} className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
            {/* The licensed thumbnail is self-hosted; attribution remains linked below. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={material.imageUrl}
              alt={material.title}
              loading="lazy"
              className="h-56 w-full bg-stone-100 object-cover object-center"
            />
            <figcaption className="p-4">
              <h3 className="history-serif text-lg font-bold text-ink">{material.title}</h3>
              <p className="mt-2 text-sm leading-6 text-stone-600">{material.description}</p>
              <p className="mt-3 text-xs font-semibold text-stone-500">
                {material.institution} · {material.license}
              </p>
              <a
                href={material.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex min-h-10 items-center font-extrabold text-brand-700 underline decoration-brand-200 underline-offset-4 hover:text-brand-900"
              >
                Xem hồ sơ tư liệu và giấy phép <span className="ml-1" aria-hidden>↗</span>
              </a>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
