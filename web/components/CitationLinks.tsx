interface Props {
  ids: string[];
}

export function CitationLinks({ ids }: Props) {
  const uniqueIds = [...new Set(ids)].filter(Boolean);
  if (uniqueIds.length === 0) return null;

  function goToSource(id: string) {
    const target = document.getElementById(`source-${id}`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus({ preventScroll: true });
  }

  return (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-baseline" aria-label="Nguồn trích dẫn">
      {uniqueIds.map((id) => (
        <button
          type="button"
          key={id}
          onClick={() => goToSource(id)}
          className="rounded-md bg-brand-50 px-1.5 py-0.5 text-xs font-extrabold text-brand-700 underline decoration-brand-200 underline-offset-2 hover:bg-brand-100"
          aria-label={`Xem nguồn ${id}`}
        >
          [{id}]
        </button>
      ))}
    </span>
  );
}

