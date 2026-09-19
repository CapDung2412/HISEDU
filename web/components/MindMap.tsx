"use client";

import { KeyboardEvent, PointerEvent, useId, useMemo, useRef, useState } from "react";
import type { MindMapData, MindMapNode, MindMapNodeType } from "@/lib/types";

interface Props {
  data: MindMapData;
}

interface PositionedNode extends MindMapNode {
  x: number;
  y: number;
}

const CANVAS_WIDTH = 960;
const CANVAS_HEIGHT = 560;
const NODE_WIDTH = 176;
const NODE_HEIGHT = 84;

const typeStyle: Record<MindMapNodeType, { label: string; className: string; dot: string }> = {
  root: { label: "Chủ đề", className: "border-brand-600 bg-brand-600 text-white", dot: "bg-brand-600" },
  cause: { label: "Nguyên nhân", className: "border-amber-200 bg-amber-50 text-amber-950", dot: "bg-amber-500" },
  event: { label: "Diễn biến", className: "border-sky-200 bg-sky-50 text-sky-950", dot: "bg-sky-500" },
  result: { label: "Kết quả", className: "border-emerald-200 bg-emerald-50 text-emerald-950", dot: "bg-emerald-500" },
  meaning: { label: "Ý nghĩa", className: "border-rose-200 bg-rose-50 text-rose-950", dot: "bg-rose-500" }
};

function styleFor(type: string) {
  return typeStyle[type as MindMapNodeType] ?? typeStyle.event;
}

function positionNodes(nodes: MindMapNode[]): PositionedNode[] {
  const rootIndex = Math.max(0, nodes.findIndex((node) => node.type === "root"));
  const ordered = nodes.filter((_, index) => index !== rootIndex);
  const root = nodes[rootIndex];
  const positioned: PositionedNode[] = root
    ? [{ ...root, x: CANVAS_WIDTH / 2 - NODE_WIDTH / 2, y: CANVAS_HEIGHT / 2 - NODE_HEIGHT / 2 }]
    : [];

  ordered.forEach((node, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / Math.max(ordered.length, 1);
    positioned.push({
      ...node,
      x: CANVAS_WIDTH / 2 + Math.cos(angle) * 340 - NODE_WIDTH / 2,
      y: CANVAS_HEIGHT / 2 + Math.sin(angle) * 190 - NODE_HEIGHT / 2
    });
  });
  return positioned;
}

export function MindMap({ data }: Props) {
  const markerId = `arrow-${useId().replace(/:/g, "")}`;
  const canvasRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const [zoom, setZoom] = useState(0.8);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [selectedId, setSelectedId] = useState(data.nodes.find((node) => node.type === "root")?.id ?? data.nodes[0]?.id);
  const nodes = useMemo(() => positionNodes(data.nodes), [data.nodes]);
  const byId = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const selectedNode = data.nodes.find((node) => node.id === selectedId);

  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.panX + event.clientX - dragRef.current.x,
      y: dragRef.current.panY + event.clientY - dragRef.current.y
    });
  }

  function resetView() {
    setZoom(0.8);
    setPan({ x: 0, y: 0 });
  }

  function handleCanvasKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const movement = 28;
    if (event.key === "ArrowLeft") setPan((value) => ({ ...value, x: value.x - movement }));
    else if (event.key === "ArrowRight") setPan((value) => ({ ...value, x: value.x + movement }));
    else if (event.key === "ArrowUp") setPan((value) => ({ ...value, y: value.y - movement }));
    else if (event.key === "ArrowDown") setPan((value) => ({ ...value, y: value.y + movement }));
    else if (event.key === "+" || event.key === "=") setZoom((value) => Math.min(1.35, value + 0.1));
    else if (event.key === "-") setZoom((value) => Math.max(0.55, value - 0.1));
    else if (event.key === "Home") resetView();
    else return;
    event.preventDefault();
  }

  async function toggleFullscreen() {
    if (!canvasRef.current) return;
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (canvasRef.current.requestFullscreen) await canvasRef.current.requestFullscreen();
    } catch {
      // Fullscreen can be blocked by browser or device policy; the map remains usable inline.
    }
  }

  return (
    <section className="section-card overflow-hidden p-5 sm:p-7" aria-labelledby="mindmap-heading">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-violet-50 text-xl" aria-hidden>🧠</span>
          <div>
            <h2 id="mindmap-heading" className="text-xl font-black text-ink sm:text-2xl">Sơ đồ tư duy</h2>
            <p className="text-sm text-slate-600">{data.title}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2" aria-label="Điều khiển sơ đồ">
          <button
            type="button"
            onClick={() => setZoom((value) => Math.max(0.55, value - 0.1))}
            className="grid h-10 min-w-10 place-items-center rounded-xl border border-slate-200 bg-white px-3 font-black text-slate-700 hover:bg-slate-50"
            aria-label="Thu nhỏ sơ đồ"
          >−</button>
          <button
            type="button"
            onClick={() => setZoom((value) => Math.min(1.35, value + 0.1))}
            className="grid h-10 min-w-10 place-items-center rounded-xl border border-slate-200 bg-white px-3 font-black text-slate-700 hover:bg-slate-50"
            aria-label="Phóng to sơ đồ"
          >+</button>
          <button type="button" onClick={resetView} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
            Căn giữa
          </button>
          <button type="button" onClick={toggleFullscreen} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 hover:bg-slate-50">
            Toàn màn hình
          </button>
        </div>
      </div>

      {nodes.length === 0 ? (
        <p className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">Chưa có dữ liệu để vẽ sơ đồ tư duy.</p>
      ) : (
        <>
          <div
            ref={canvasRef}
            onPointerDown={startDrag}
            onPointerMove={moveDrag}
            onPointerUp={() => { dragRef.current = null; }}
            onPointerCancel={() => { dragRef.current = null; }}
            onKeyDown={handleCanvasKeyDown}
            role="region"
            tabIndex={0}
            className="relative mt-5 h-[27rem] touch-none overflow-hidden rounded-3xl border border-brand-100 bg-[radial-gradient(circle_at_center,_#ffffff_0,_#f1f9ff_72%)] cursor-grab active:cursor-grabbing sm:h-[31rem]"
            aria-label={`Sơ đồ tư duy: ${data.title}. Kéo hoặc dùng các phím mũi tên để di chuyển.`}
          >
            <div
              className="absolute left-1/2 top-1/2 h-[560px] w-[960px] origin-center transition-transform duration-200"
              style={{ transform: `translate(calc(-50% + ${pan.x}px), calc(-50% + ${pan.y}px)) scale(${zoom})` }}
            >
              <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`} aria-hidden="true">
                <defs>
                  <marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                    <path d="M 0 0 L 8 4 L 0 8 z" fill="#8bb6d6" />
                  </marker>
                </defs>
                {data.edges.map((edge, index) => {
                  const source = byId.get(edge.source);
                  const target = byId.get(edge.target);
                  if (!source || !target) return null;
                  return (
                    <line
                      key={`${edge.source}-${edge.target}-${index}`}
                      x1={source.x + NODE_WIDTH / 2}
                      y1={source.y + NODE_HEIGHT / 2}
                      x2={target.x + NODE_WIDTH / 2}
                      y2={target.y + NODE_HEIGHT / 2}
                      stroke="#8bb6d6"
                      strokeWidth="3"
                      markerEnd={`url(#${markerId})`}
                    />
                  );
                })}
              </svg>

              {nodes.map((node) => {
                const nodeStyle = styleFor(node.type);
                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSelectedId(node.id)}
                    aria-pressed={selectedId === node.id}
                    className={`absolute flex h-[84px] w-[176px] flex-col items-center justify-center rounded-2xl border-2 px-3 text-center shadow-lg transition hover:-translate-y-1 focus:z-10 ${nodeStyle.className} ${selectedId === node.id ? "ring-4 ring-sun-400/70" : ""}`}
                    style={{ left: node.x, top: node.y }}
                    title={node.description}
                  >
                    <span className="text-[10px] font-black uppercase tracking-wide opacity-70">{nodeStyle.label}</span>
                    <span className="mt-1 line-clamp-2 text-sm font-extrabold leading-5">{node.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {selectedNode && (
            <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-700" aria-live="polite">
              <strong className="text-ink">{selectedNode.label}:</strong> {selectedNode.description}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2" aria-label="Chú thích màu sắc">
            {Object.entries(typeStyle).map(([type, style]) => (
              <span key={type} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600">
                <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} aria-hidden /> {style.label}
              </span>
            ))}
          </div>

          <details className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer font-extrabold text-brand-700">Xem sơ đồ dạng danh sách</summary>
            <ul className="mt-4 space-y-3">
              {data.nodes.map((node) => (
                <li key={node.id} className="border-l-4 border-brand-100 pl-3">
                  <p className="font-bold text-ink">{node.label}</p>
                  <p className="text-sm text-slate-600">{node.description}</p>
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}
