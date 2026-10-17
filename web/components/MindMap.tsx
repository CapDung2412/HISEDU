"use client";

import {
  KeyboardEvent,
  PointerEvent,
  WheelEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState
} from "react";
import type {
  MindMapData,
  MindMapEdge,
  MindMapNode,
  MindMapNodeType
} from "@/lib/types";

interface Props {
  data: MindMapData;
}

type NodeSide = -1 | 0 | 1;

interface PositionedNode extends MindMapNode {
  depth: number;
  side: NodeSide;
  x: number;
  y: number;
}

interface DisplayEdge extends MindMapEdge {
  secondary: boolean;
}

interface MindMapGraph {
  byId: Map<string, MindMapNode>;
  children: Map<string, string[]>;
  depths: Map<string, number>;
  edges: DisplayEdge[];
  maxDepth: number;
  nodes: MindMapNode[];
  parents: Map<string, string>;
  rootId?: string;
}

interface MindMapLayout {
  byId: Map<string, PositionedNode>;
  height: number;
  nodes: PositionedNode[];
  width: number;
}

interface NodeStyle {
  label: string;
  icon: string;
  className: string;
  dot: string;
  line: string;
}

type LearningSectionKey = "cause" | "event" | "person" | "meaning";

interface LearningSection {
  key: LearningSectionKey;
  label: string;
  description: string;
}

const NODE_WIDTH = 224;
const NODE_HEIGHT = 116;
const COLUMN_STRIDE = 324;
const ROW_GAP = 24;
const ROW_STRIDE = NODE_HEIGHT + ROW_GAP;
const CANVAS_PADDING_X = 88;
const CANVAS_PADDING_Y = 64;
const MIN_CANVAS_WIDTH = 1_160;
const MIN_CANVAS_HEIGHT = 660;
const DEFAULT_ZOOM = 0.78;
const MIN_ZOOM = 0.32;
const MAX_ZOOM = 1.6;
const ZOOM_STEP = 0.1;

const typeStyle: Record<MindMapNodeType, NodeStyle> = {
  root: {
    label: "Chủ đề",
    icon: "◎",
    className: "border-brand-700 bg-brand-600 text-white",
    dot: "bg-brand-600",
    line: "#347ead"
  },
  time: {
    label: "Mốc thời gian",
    icon: "◷",
    className: "border-red-300 bg-red-50 text-red-950",
    dot: "bg-red-600",
    line: "#dc2626"
  },
  person: {
    label: "Nhân vật",
    icon: "♟",
    className: "border-rose-300 bg-rose-50 text-rose-950",
    dot: "bg-rose-600",
    line: "#e11d48"
  },
  cause: {
    label: "Nguyên nhân",
    icon: "?",
    className: "border-amber-200 bg-amber-50 text-amber-950",
    dot: "bg-amber-500",
    line: "#f59e0b"
  },
  event: {
    label: "Diễn biến",
    icon: "→",
    className: "border-brand-300 bg-brand-50 text-brand-950",
    dot: "bg-brand-600",
    line: "#a83d32"
  },
  result: {
    label: "Kết quả",
    icon: "✓",
    className: "border-emerald-200 bg-emerald-50 text-emerald-950",
    dot: "bg-emerald-500",
    line: "#34d399"
  },
  meaning: {
    label: "Ý nghĩa",
    icon: "★",
    className: "border-red-300 bg-red-50 text-red-950",
    dot: "bg-red-700",
    line: "#b91c1c"
  },
  memory: {
    label: "Ghi nhớ nhanh",
    icon: "!",
    className: "border-orange-200 bg-orange-50 text-orange-950",
    dot: "bg-orange-500",
    line: "#fb923c"
  }
};

const typeOrder: MindMapNodeType[] = [
  "root",
  "time",
  "person",
  "cause",
  "event",
  "result",
  "meaning",
  "memory"
];

const typeAliases: Record<string, MindMapNodeType> = {
  character: "person",
  date: "time",
  development: "event",
  key_point: "memory",
  memory_point: "memory",
  people: "person",
  significance: "meaning",
  timeline: "time"
};

const learningSections: readonly LearningSection[] = [
  {
    key: "cause",
    label: "Nguyên nhân",
    description: "Các nguyên nhân sâu xa và trực tiếp của sự kiện."
  },
  {
    key: "event",
    label: "Diễn biến",
    description: "Các mốc thời gian và diễn biến chính của sự kiện."
  },
  {
    key: "person",
    label: "Nhân vật",
    description: "Các nhân vật lịch sử và vai trò liên quan."
  },
  {
    key: "meaning",
    label: "Ý nghĩa",
    description: "Kết quả, ý nghĩa và những điều cần ghi nhớ."
  }
];

function canonicalType(type: string): MindMapNodeType {
  if (type in typeStyle) return type as MindMapNodeType;
  return typeAliases[type] ?? "event";
}

function styleFor(node: MindMapNode, rootId?: string): NodeStyle {
  return node.id === rootId ? typeStyle.root : typeStyle[canonicalType(node.type)];
}

function nonEmptyText(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function textList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return Array.from(
    new Set(value.map(nonEmptyText).filter((item): item is string => Boolean(item)))
  );
}

function normalizedLabel(value: unknown): string {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/đ/giu, "d")
    .replace(/[^a-z0-9]+/giu, " ")
    .trim()
    .toLocaleLowerCase("vi");
}

function sectionForNode(node: MindMapNode): LearningSectionKey {
  const type = canonicalType(node.type);
  if (type === "cause") return "cause";
  if (type === "person") return "person";
  if (type === "time" || type === "event") return "event";
  return "meaning";
}

function organizeByLearningSections(
  inputNodes: MindMapNode[],
  inputEdges: MindMapEdge[]
): { nodes: MindMapNode[]; edges: MindMapEdge[] } {
  const sourceNodes = Array.isArray(inputNodes) ? inputNodes : [];
  const root = sourceNodes.find((node) => canonicalType(node.type) === "root") ?? sourceNodes[0];
  if (!root) return { nodes: [], edges: [] };

  const usedIds = new Set(sourceNodes.map((node) => node.id));
  const sectionNodes = new Map<LearningSectionKey, MindMapNode>();
  const claimedIds = new Set<string>([root.id]);

  const uniqueSectionId = (key: LearningSectionKey) => {
    const base = `section-${key}`;
    let candidate = base;
    let suffix = 2;
    while (usedIds.has(candidate)) candidate = `${base}-${suffix++}`;
    usedIds.add(candidate);
    return candidate;
  };

  for (const section of learningSections) {
    const existing = sourceNodes.find(
      (node) =>
        node.id !== root.id &&
        canonicalType(node.type) === section.key &&
        normalizedLabel(node.label) === normalizedLabel(section.label)
    );
    const sectionNode = existing ?? {
      id: uniqueSectionId(section.key),
      label: section.label,
      description: section.description,
      type: section.key
    };
    sectionNodes.set(section.key, sectionNode);
    claimedIds.add(sectionNode.id);
  }

  const factNodes = sourceNodes.filter((node) => !claimedIds.has(node.id));
  const factIds = new Set(factNodes.map((node) => node.id));
  const sectionEdges: MindMapEdge[] = [];
  for (const section of learningSections) {
    const sectionNode = sectionNodes.get(section.key) as MindMapNode;
    sectionEdges.push({ source: root.id, target: sectionNode.id });
    for (const node of factNodes) {
      if (sectionForNode(node) === section.key) {
        sectionEdges.push({ source: sectionNode.id, target: node.id });
      }
    }
  }

  // Preserve useful cause-and-effect links as secondary (dashed) edges, but
  // never let an old root edge bypass the four required learning sections.
  const relatedFactEdges = (Array.isArray(inputEdges) ? inputEdges : []).filter(
    (edge) => factIds.has(edge.source) && factIds.has(edge.target)
  );

  return {
    nodes: [
      { ...root, type: "root" },
      ...learningSections.map((section) => sectionNodes.get(section.key) as MindMapNode),
      ...factNodes
    ],
    edges: [...sectionEdges, ...relatedFactEdges]
  };
}

function makeGraph(inputNodes: MindMapNode[], inputEdges: MindMapEdge[]): MindMapGraph {
  const organized = organizeByLearningSections(inputNodes, inputEdges);
  const seenIds = new Set<string>();
  const nodes = organized.nodes.filter((node) => {
    if (!nonEmptyText(node?.id) || seenIds.has(node.id)) return false;
    seenIds.add(node.id);
    return true;
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const rootId = nodes.find((node) => canonicalType(node.type) === "root")?.id ?? nodes[0]?.id;
  const emptyGraph: MindMapGraph = {
    byId,
    children: new Map(),
    depths: new Map(),
    edges: [],
    maxDepth: 0,
    nodes,
    parents: new Map(),
    rootId
  };

  if (!rootId) return emptyGraph;

  const edgeKeys = new Set<string>();
  const validEdges = organized.edges.filter((edge) => {
    const key = `${edge?.source}\u0000${edge?.target}`;
    if (
      !byId.has(edge?.source) ||
      !byId.has(edge?.target) ||
      edge.source === edge.target ||
      edgeKeys.has(key)
    ) {
      return false;
    }
    edgeKeys.add(key);
    return true;
  });

  const outgoing = new Map<string, MindMapEdge[]>();
  const incoming = new Map<string, MindMapEdge[]>();
  nodes.forEach((node) => {
    outgoing.set(node.id, []);
    incoming.set(node.id, []);
  });
  validEdges.forEach((edge) => {
    outgoing.get(edge.source)?.push(edge);
    incoming.get(edge.target)?.push(edge);
  });

  const parents = new Map<string, string>();
  const depths = new Map<string, number>([[rootId, 0]]);

  function visit(startId: string) {
    const queue = [startId];
    for (let index = 0; index < queue.length; index += 1) {
      const source = queue[index];
      const sourceDepth = depths.get(source) ?? 0;
      for (const edge of outgoing.get(source) ?? []) {
        if (edge.target === rootId || depths.has(edge.target)) continue;
        parents.set(edge.target, source);
        depths.set(edge.target, sourceDepth + 1);
        queue.push(edge.target);
      }
    }
  }

  visit(rootId);

  // Keep incomplete or malformed responses useful: attach each disconnected
  // component to the topic, then preserve its valid internal relationships.
  while (depths.size < nodes.length) {
    const unvisited = nodes.filter((node) => !depths.has(node.id));
    const candidate =
      unvisited.find((node) =>
        (incoming.get(node.id) ?? []).every((edge) => depths.has(edge.source))
      ) ?? unvisited[0];
    parents.set(candidate.id, rootId);
    depths.set(candidate.id, 1);
    visit(candidate.id);
  }

  const children = new Map<string, string[]>();
  nodes.forEach((node) => children.set(node.id, []));
  parents.forEach((parentId, childId) => children.get(parentId)?.push(childId));

  const treeKeys = new Set(
    Array.from(parents, ([target, source]) => `${source}\u0000${target}`)
  );
  const displayEdges: DisplayEdge[] = Array.from(parents, ([target, source]) => ({
    source,
    target,
    secondary: false
  }));
  validEdges.forEach((edge) => {
    const key = `${edge.source}\u0000${edge.target}`;
    if (!treeKeys.has(key) && edge.target !== rootId) {
      displayEdges.push({ ...edge, secondary: true });
    }
  });

  return {
    byId,
    children,
    depths,
    edges: displayEdges,
    maxDepth: Math.max(...depths.values()),
    nodes,
    parents,
    rootId
  };
}

function collapseGraph(graph: MindMapGraph, collapsedIds: ReadonlySet<string>): MindMapGraph {
  if (!graph.rootId || collapsedIds.size === 0) return graph;

  const visibleIds = new Set<string>();
  const queue = [graph.rootId];
  for (let index = 0; index < queue.length; index += 1) {
    const id = queue[index];
    if (visibleIds.has(id)) continue;
    visibleIds.add(id);
    if (!collapsedIds.has(id)) queue.push(...(graph.children.get(id) ?? []));
  }

  const nodes = graph.nodes.filter((node) => visibleIds.has(node.id));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map(
    nodes.map((node) => [
      node.id,
      collapsedIds.has(node.id)
        ? []
        : (graph.children.get(node.id) ?? []).filter((id) => visibleIds.has(id))
    ])
  );
  const parents = new Map(
    Array.from(graph.parents).filter(
      ([childId, parentId]) => visibleIds.has(childId) && visibleIds.has(parentId)
    )
  );
  const depths = new Map(
    Array.from(graph.depths).filter(([id]) => visibleIds.has(id))
  );

  return {
    byId,
    children,
    depths,
    edges: graph.edges.filter(
      (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)
    ),
    maxDepth: depths.size > 0 ? Math.max(...depths.values()) : 0,
    nodes,
    parents,
    rootId: graph.rootId
  };
}

function makeLayout(graph: MindMapGraph): MindMapLayout {
  if (!graph.rootId) {
    return { byId: new Map(), height: MIN_CANVAS_HEIGHT, nodes: [], width: MIN_CANVAS_WIDTH };
  }

  const spanMemo = new Map<string, number>();
  function leafSpan(id: string): number {
    const cached = spanMemo.get(id);
    if (cached) return cached;
    const childIds = graph.children.get(id) ?? [];
    const span = childIds.length
      ? childIds.reduce((total, childId) => total + leafSpan(childId), 0)
      : 1;
    spanMemo.set(id, span);
    return span;
  }

  const sideById = new Map<string, NodeSide>([[graph.rootId, 0]]);
  const rootChildren = graph.children.get(graph.rootId) ?? [];
  let leftWeight = 0;
  let rightWeight = 0;

  function assignBranch(id: string, side: Exclude<NodeSide, 0>) {
    sideById.set(id, side);
    (graph.children.get(id) ?? []).forEach((childId) => assignBranch(childId, side));
  }

  rootChildren.forEach((childId) => {
    const span = leafSpan(childId);
    const side: Exclude<NodeSide, 0> = rightWeight <= leftWeight ? 1 : -1;
    assignBranch(childId, side);
    if (side === 1) rightWeight += span;
    else leftWeight += span;
  });

  const maximumRows = Math.max(leftWeight, rightWeight, 1);
  const contentHeight = maximumRows * NODE_HEIGHT + Math.max(0, maximumRows - 1) * ROW_GAP;
  const height = Math.max(MIN_CANVAS_HEIGHT, contentHeight + CANVAS_PADDING_Y * 2);
  const width = Math.max(
    MIN_CANVAS_WIDTH,
    (graph.maxDepth * COLUMN_STRIDE + NODE_WIDTH / 2 + CANVAS_PADDING_X) * 2
  );
  const centerX = width / 2;
  const positions = new Map<string, { x: number; y: number }>();

  function placeSide(side: Exclude<NodeSide, 0>, branches: string[], rowCount: number) {
    const sideHeight = rowCount * NODE_HEIGHT + Math.max(0, rowCount - 1) * ROW_GAP;
    const startY = (height - sideHeight) / 2;
    let leafIndex = 0;

    function placeBranch(id: string): number {
      const childIds = graph.children.get(id) ?? [];
      let centerY: number;
      if (childIds.length === 0) {
        centerY = startY + leafIndex * ROW_STRIDE + NODE_HEIGHT / 2;
        leafIndex += 1;
      } else {
        const childCenters = childIds.map(placeBranch);
        centerY = (childCenters[0] + childCenters[childCenters.length - 1]) / 2;
      }
      const depth = graph.depths.get(id) ?? 1;
      positions.set(id, {
        x: centerX + side * depth * COLUMN_STRIDE - NODE_WIDTH / 2,
        y: centerY - NODE_HEIGHT / 2
      });
      return centerY;
    }

    branches.forEach(placeBranch);
  }

  placeSide(
    -1,
    rootChildren.filter((id) => sideById.get(id) === -1),
    leftWeight
  );
  placeSide(
    1,
    rootChildren.filter((id) => sideById.get(id) === 1),
    rightWeight
  );
  positions.set(graph.rootId, {
    x: centerX - NODE_WIDTH / 2,
    y: height / 2 - NODE_HEIGHT / 2
  });

  const nodes = graph.nodes.map((node) => ({
    ...node,
    depth: graph.depths.get(node.id) ?? 0,
    side: sideById.get(node.id) ?? 0,
    x: positions.get(node.id)?.x ?? centerX - NODE_WIDTH / 2,
    y: positions.get(node.id)?.y ?? height / 2 - NODE_HEIGHT / 2
  }));

  return {
    byId: new Map(nodes.map((node) => [node.id, node])),
    height,
    nodes,
    width
  };
}

function edgePath(source: PositionedNode, target: PositionedNode): string {
  const travelsRight = target.x >= source.x;
  const direction = travelsRight ? 1 : -1;
  const sourceX = travelsRight ? source.x + NODE_WIDTH : source.x;
  const targetX = travelsRight ? target.x : target.x + NODE_WIDTH;
  const sourceY = source.y + NODE_HEIGHT / 2;
  const targetY = target.y + NODE_HEIGHT / 2;
  const bend = Math.max(54, Math.abs(targetX - sourceX) * 0.48);
  return `M ${sourceX} ${sourceY} C ${sourceX + direction * bend} ${sourceY}, ${targetX - direction * bend} ${targetY}, ${targetX} ${targetY}`;
}

interface OutlineNodeProps {
  graph: MindMapGraph;
  nodeId: string;
  onSelect: (id: string) => void;
}

function OutlineNode({ graph, nodeId, onSelect }: OutlineNodeProps) {
  const node = graph.byId.get(nodeId);
  if (!node) return null;
  const style = styleFor(node, graph.rootId);
  const childIds = graph.children.get(nodeId) ?? [];
  const description = nonEmptyText(node.description);

  return (
    <li>
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <button
          type="button"
          onClick={() => onSelect(node.id)}
          className="flex w-full items-start gap-2 text-left"
        >
          <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} aria-hidden />
          <span>
            <span className="block text-xs font-black uppercase tracking-wide text-slate-500">
              {style.label}
            </span>
            <span className="font-extrabold text-ink">{nonEmptyText(node.label) ?? "Ý kiến thức"}</span>
          </span>
        </button>
        {description && <p className="mt-1 pl-[1.125rem] text-sm text-slate-600">{description}</p>}
      </div>
      {childIds.length > 0 && (
        <ul className="ml-4 mt-3 space-y-3 border-l-2 border-brand-100 pl-4 sm:ml-6">
          {childIds.map((childId) => (
            <OutlineNode key={childId} graph={graph} nodeId={childId} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function MindMap({ data }: Props) {
  const markerId = `arrow-${useId().replace(/:/g, "")}`;
  const helpId = `${markerId}-help`;
  const canvasRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const fullGraph = useMemo(
    () => makeGraph(data.nodes ?? [], data.edges ?? []),
    [data.edges, data.nodes]
  );
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => new Set());
  const graph = useMemo(
    () => collapseGraph(fullGraph, collapsedIds),
    [collapsedIds, fullGraph]
  );
  const layout = useMemo(() => makeLayout(graph), [graph]);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [selectedId, setSelectedId] = useState(graph.rootId);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    if (!selectedId || !graph.byId.has(selectedId)) setSelectedId(graph.rootId);
  }, [graph, selectedId]);

  useEffect(() => {
    function updateFullscreenState() {
      setIsFullscreen(document.fullscreenElement === canvasRef.current);
    }

    document.addEventListener("fullscreenchange", updateFullscreenState);
    return () => document.removeEventListener("fullscreenchange", updateFullscreenState);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const fitInitialView = () => {
      if (canvas.clientWidth <= 0 || canvas.clientHeight <= 0) return;
      const horizontalPadding = canvas.clientWidth < 640 ? 24 : 56;
      const verticalPadding = canvas.clientWidth < 640 ? 56 : 72;
      const fittedZoom = Math.min(
        Math.max(1, canvas.clientWidth - horizontalPadding) / layout.width,
        Math.max(1, canvas.clientHeight - verticalPadding) / layout.height
      );
      setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(fittedZoom.toFixed(2)))));
      setPan({ x: 0, y: 0 });
    };
    const frame = window.requestAnimationFrame(fitInitialView);
    const observer = typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(fitInitialView);
    observer?.observe(canvas);
    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [layout.height, layout.width]);

  const selectedNode = selectedId ? graph.byId.get(selectedId) : undefined;
  const selectedStyle = selectedNode ? styleFor(selectedNode, graph.rootId) : undefined;
  const selectedParent = selectedId ? graph.byId.get(graph.parents.get(selectedId) ?? "") : undefined;
  const selectedChildren = (selectedId ? graph.children.get(selectedId) : undefined) ?? [];
  const availableTypes = typeOrder.filter((type) =>
    graph.nodes.some((node) =>
      node.id === graph.rootId ? type === "root" : canonicalType(node.type) === type
    )
  );
  const activeNodeIds = useMemo(() => {
    const ids = new Set<string>();
    if (!selectedId) return ids;
    ids.add(selectedId);
    (graph.children.get(selectedId) ?? []).forEach((id) => ids.add(id));
    let currentId = selectedId;
    while (graph.parents.has(currentId)) {
      currentId = graph.parents.get(currentId) as string;
      ids.add(currentId);
    }
    return ids;
  }, [graph, selectedId]);

  function clampZoom(value: number) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(2))));
  }

  function zoomBy(amount: number) {
    setZoom((value) => clampZoom(value + amount));
  }

  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if ((event.target as HTMLElement).closest("button")) return;
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    dragRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.panX + event.clientX - dragRef.current.x,
      y: dragRef.current.panY + event.clientY - dragRef.current.y
    });
  }

  function stopDrag(event: PointerEvent<HTMLDivElement>) {
    dragRef.current = null;
    if (
      typeof event.currentTarget.hasPointerCapture === "function" &&
      typeof event.currentTarget.releasePointerCapture === "function" &&
      event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function resetView() {
    setZoom(DEFAULT_ZOOM);
    setPan({ x: 0, y: 0 });
  }

  function fitView() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const horizontalPadding = canvas.clientWidth < 640 ? 24 : 56;
    const verticalPadding = canvas.clientWidth < 640 ? 56 : 72;
    const availableWidth = Math.max(1, canvas.clientWidth - horizontalPadding);
    const availableHeight = Math.max(1, canvas.clientHeight - verticalPadding);
    const fittedZoom = Math.min(
      availableWidth / layout.width,
      availableHeight / layout.height
    );
    setZoom(clampZoom(fittedZoom));
    setPan({ x: 0, y: 0 });
  }

  function focusNode(id: string) {
    const node = layout.byId.get(id);
    if (!node) return;
    const readableZoom = Math.max(zoom, 0.72);
    setSelectedId(id);
    setZoom(readableZoom);
    setPan({
      x: -(node.x + NODE_WIDTH / 2 - layout.width / 2) * readableZoom,
      y: -(node.y + NODE_HEIGHT / 2 - layout.height / 2) * readableZoom
    });
  }

  function handleWheel(event: WheelEvent<HTMLDivElement>) {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP);
  }

  function handleCanvasKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const movement = 28;
    if (event.key === "ArrowLeft") setPan((value) => ({ ...value, x: value.x - movement }));
    else if (event.key === "ArrowRight") setPan((value) => ({ ...value, x: value.x + movement }));
    else if (event.key === "ArrowUp") setPan((value) => ({ ...value, y: value.y - movement }));
    else if (event.key === "ArrowDown") setPan((value) => ({ ...value, y: value.y + movement }));
    else if (event.key === "+" || event.key === "=") {
      zoomBy(ZOOM_STEP);
    } else if (event.key === "-") {
      zoomBy(-ZOOM_STEP);
    } else if (event.key === "0" || event.key === "Home") fitView();
    else if (event.key === "1") resetView();
    else return;
    event.preventDefault();
  }

  async function toggleFullscreen() {
    if (!canvasRef.current) return;
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (canvasRef.current.requestFullscreen) {
        await canvasRef.current.requestFullscreen();
        window.setTimeout(fitView, 80);
      }
    } catch {
      // Browser or device policy can block fullscreen; the inline map remains usable.
    }
  }

  function selectType(type: MindMapNodeType) {
    const node = graph.nodes.find((item) =>
      item.id === graph.rootId ? type === "root" : canonicalType(item.type) === type
    );
    if (node) focusNode(node.id);
  }

  function toggleBranch(id: string) {
    const hasChildren = (fullGraph.children.get(id) ?? []).length > 0;
    if (!hasChildren) return;
    setCollapsedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setSelectedId(id);
    setPan({ x: 0, y: 0 });
  }

  const mainBranches = learningSections.flatMap((section) => {
    const node = fullGraph.nodes.find(
      (candidate) =>
        fullGraph.parents.get(candidate.id) === fullGraph.rootId &&
        canonicalType(candidate.type) === section.key
    );
    return node ? [{ section, node }] : [];
  });

  const selectedDetails = textList(selectedNode?.details);
  const selectedPeople = textList(selectedNode?.people);
  const selectedMemoryPoints = textList(selectedNode?.memory_points);
  const selectedTime = nonEmptyText(selectedNode?.time);
  const selectedDescription = nonEmptyText(selectedNode?.description);
  const mapTitle = nonEmptyText(data.title) ?? "Chủ đề lịch sử";
  const selectedType = selectedNode
    ? selectedNode.id === graph.rootId
      ? "root"
      : canonicalType(selectedNode.type)
    : undefined;

  return (
    <section className="section-card overflow-hidden p-5 sm:p-7" aria-labelledby="mindmap-heading">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="history-serif grid h-11 w-11 place-items-center rounded-full border border-brand-200 bg-brand-50 text-sm font-bold text-brand-700" aria-hidden>
            02
          </span>
          <div>
            <h2 id="mindmap-heading" className="history-serif text-xl font-bold text-ink sm:text-2xl">
              Sơ đồ tư duy
            </h2>
            <p className="text-sm font-semibold text-slate-700">{mapTitle}</p>
            {graph.nodes.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">
                {graph.nodes.length === fullGraph.nodes.length
                  ? `${fullGraph.nodes.length} ý kiến thức`
                  : `${graph.nodes.length}/${fullGraph.nodes.length} ý đang hiển thị`} · {graph.maxDepth + 1} tầng liên kết
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label="Điều khiển sơ đồ">
          <div className="flex items-center rounded-xl border border-brand-100 bg-white p-1 shadow-sm" role="group" aria-label="Thu phóng">
            <button
              type="button"
              onClick={() => zoomBy(-ZOOM_STEP)}
              disabled={zoom <= MIN_ZOOM}
              className="grid h-9 min-w-9 place-items-center rounded-lg font-black text-slate-700 transition hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:cursor-not-allowed disabled:opacity-35"
              aria-label="Thu nhỏ sơ đồ"
              aria-keyshortcuts="-"
            >
              −
            </button>
            <output className="grid h-9 min-w-14 place-items-center border-x border-brand-100 px-2 text-xs font-black tabular-nums text-brand-700" aria-live="polite" aria-label="Mức thu phóng">
              {Math.round(zoom * 100)}%
            </output>
            <button
              type="button"
              onClick={() => zoomBy(ZOOM_STEP)}
              disabled={zoom >= MAX_ZOOM}
              className="grid h-9 min-w-9 place-items-center rounded-lg font-black text-slate-700 transition hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:cursor-not-allowed disabled:opacity-35"
              aria-label="Phóng to sơ đồ"
              aria-keyshortcuts="+"
            >
              +
            </button>
          </div>
          <button
            type="button"
            onClick={fitView}
            aria-keyshortcuts="0 Home"
            className="h-11 rounded-xl border border-brand-200 bg-brand-50 px-3 text-sm font-extrabold text-brand-700 transition hover:border-brand-300 hover:bg-brand-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <span aria-hidden>⌗</span> Vừa khung
          </button>
          <button
            type="button"
            onClick={resetView}
            aria-label="Đặt lại góc nhìn"
            aria-keyshortcuts="1"
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <span aria-hidden>↺</span> <span className="hidden sm:inline">Mặc định</span>
          </button>
          <button
            type="button"
            onClick={toggleFullscreen}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            aria-label={isFullscreen ? "Thoát toàn màn hình" : "Mở sơ đồ toàn màn hình"}
          >
            <span aria-hidden>{isFullscreen ? "⊙" : "⛶"}</span>{" "}
            <span className="hidden sm:inline">{isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}</span>
          </button>
        </div>
      </div>

      {layout.nodes.length === 0 ? (
        <p className="mt-5 rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
          Chưa có dữ liệu để vẽ sơ đồ tư duy.
        </p>
      ) : (
        <>
          <div className="mt-5 rounded-2xl border border-brand-100 bg-brand-50/50 p-3" aria-label="Bốn nhánh chính của sơ đồ">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-black uppercase tracking-wide text-brand-800">
                Bốn nhánh kiến thức
              </p>
              <button
                type="button"
                onClick={() => setCollapsedIds(new Set())}
                disabled={collapsedIds.size === 0}
                className="min-h-9 rounded-full px-3 text-xs font-bold text-brand-700 hover:bg-white disabled:cursor-default disabled:opacity-40"
              >
                Mở tất cả
              </button>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {mainBranches.map(({ section, node }) => {
                const isOpen = !collapsedIds.has(node.id);
                const childCount = fullGraph.children.get(node.id)?.length ?? 0;
                const style = typeStyle[section.key];
                return (
                  <button
                    key={section.key}
                    type="button"
                    onClick={() => toggleBranch(node.id)}
                    aria-expanded={isOpen}
                    aria-controls={`mindmap-branch-${node.id}`}
                    className={`flex min-h-12 items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm font-extrabold transition hover:-translate-y-0.5 hover:shadow-sm ${isOpen ? "border-brand-200 bg-white text-brand-900" : "border-slate-200 bg-slate-100 text-slate-600"}`}
                  >
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{section.label}</span>
                      <span className="block text-[11px] font-semibold text-slate-500">
                        {childCount} ý · {isOpen ? "đang mở" : "đã thu gọn"}
                      </span>
                    </span>
                    <span aria-hidden>{isOpen ? "−" : "+"}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2" aria-label="Nhóm kiến thức có trong sơ đồ">
            {availableTypes.map((type) => {
              const style = typeStyle[type];
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => selectType(type)}
                  aria-pressed={selectedType === type}
                  className={`inline-flex min-h-10 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-bold transition hover:-translate-y-0.5 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${selectedType === type ? "border-brand-300 bg-brand-50 text-brand-800 shadow-sm" : "border-slate-200 bg-white text-slate-700"}`}
                >
                  <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} aria-hidden />
                  {style.label}
                </button>
              );
            })}
          </div>

          <div className="mt-4 grid gap-4">
            <div
              ref={canvasRef}
            onPointerDown={startDrag}
            onPointerMove={moveDrag}
            onPointerUp={stopDrag}
            onPointerCancel={stopDrag}
            onWheel={handleWheel}
            onKeyDown={handleCanvasKeyDown}
            role="region"
            tabIndex={0}
              className="relative h-[30rem] touch-none cursor-grab overflow-hidden rounded-3xl border border-brand-200 bg-[#fbf7ee] shadow-inner outline-none active:cursor-grabbing focus-visible:ring-4 focus-visible:ring-brand-200 fullscreen:h-screen fullscreen:rounded-none sm:h-[34rem]"
            style={{
              backgroundImage:
                "radial-gradient(circle at center, rgba(255,255,255,.96) 0, rgba(255,250,240,.9) 60%, rgba(237,199,180,.38) 100%), linear-gradient(rgba(116,35,31,.055) 1px, transparent 1px), linear-gradient(90deg, rgba(116,35,31,.055) 1px, transparent 1px)",
              backgroundSize: "auto, 28px 28px, 28px 28px"
            }}
            aria-label={`Sơ đồ tư duy: ${mapTitle}. Kéo hoặc dùng các phím mũi tên để di chuyển.`}
            aria-describedby={helpId}
            aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown + - 0 1 Home"
            >
            <div className="pointer-events-none absolute left-3 top-3 z-20 rounded-full border border-brand-100 bg-white/90 px-3 py-1.5 text-[11px] font-extrabold text-brand-700 shadow-sm backdrop-blur" aria-hidden>
              {isFullscreen ? "Chế độ toàn màn hình" : "Bản đồ kiến thức tương tác"}
            </div>
            <div
              className="absolute left-1/2 top-1/2 origin-center transition-transform duration-200"
              style={{
                height: layout.height,
                width: layout.width,
                transform: `translate(calc(-50% + ${pan.x}px), calc(-50% + ${pan.y}px)) scale(${zoom})`
              }}
            >
              <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${layout.width} ${layout.height}`} aria-hidden="true">
                <defs>
                  <marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                    <path d="M 0 0 L 8 4 L 0 8 z" fill="#7c9eb8" />
                  </marker>
                </defs>
                {graph.edges.map((edge) => {
                  const source = layout.byId.get(edge.source);
                  const target = layout.byId.get(edge.target);
                  if (!source || !target) return null;
                  const targetStyle = styleFor(target, graph.rootId);
                  const isSelected = activeNodeIds.has(edge.source) && activeNodeIds.has(edge.target);
                  return (
                    <path
                      key={`${edge.source}-${edge.target}-${edge.secondary ? "secondary" : "tree"}`}
                      d={edgePath(source, target)}
                      fill="none"
                      stroke={edge.secondary ? "#aab8c4" : targetStyle.line}
                      strokeDasharray={edge.secondary ? "7 7" : undefined}
                      strokeLinecap="round"
                      strokeWidth={isSelected ? 4 : edge.secondary ? 2 : 3}
                      opacity={isSelected ? 1 : edge.secondary ? 0.55 : 0.78}
                      markerEnd={`url(#${markerId})`}
                    />
                  );
                })}
              </svg>

              {layout.nodes.map((node) => {
                const nodeStyle = styleFor(node, graph.rootId);
                const label = nonEmptyText(node.label) ?? "Ý kiến thức";
                const description = nonEmptyText(node.description);
                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => focusNode(node.id)}
                    aria-label={`Xem ${nodeStyle.label.toLowerCase()}: ${label}`}
                    aria-pressed={selectedId === node.id}
                    className={`absolute flex flex-col rounded-2xl border-2 px-4 py-3 text-left shadow-lg transition duration-200 hover:z-20 hover:-translate-y-1 hover:opacity-100 hover:shadow-xl focus:z-20 focus:outline-none focus:ring-4 focus:ring-sun-400/70 ${nodeStyle.className} ${activeNodeIds.has(node.id) ? "opacity-100" : "opacity-[0.65]"} ${selectedId === node.id ? "z-10 ring-4 ring-sun-400/70" : ""}`}
                    style={{
                      height: NODE_HEIGHT,
                      left: node.x,
                      top: node.y,
                      width: NODE_WIDTH
                    }}
                    title={description}
                    id={`mindmap-branch-${node.id}`}
                  >
                    <span className="flex w-full items-center justify-between gap-2 text-[10px] font-black uppercase tracking-[0.12em] opacity-75">
                      <span>{nodeStyle.icon} {nodeStyle.label}</span>
                      <span>{node.id === graph.rootId ? "Chủ đề" : `Tầng ${node.depth}`}</span>
                    </span>
                    <span className="mt-1 line-clamp-2 text-sm font-black leading-5">{label}</span>
                    {description && (
                      <span className="mt-1 line-clamp-2 text-[11px] font-medium leading-4 opacity-75">
                        {description}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <div id={helpId} className="pointer-events-none absolute bottom-3 left-1/2 z-20 w-max max-w-[calc(100%-1.5rem)] -translate-x-1/2 rounded-full border border-white/80 bg-white/95 px-3 py-1.5 text-center text-[11px] font-semibold text-slate-600 shadow-sm backdrop-blur">
              <span className="sm:hidden">Chạm thẻ để đọc · Kéo để di chuyển</span>
              <span className="hidden sm:inline">Chọn thẻ để đọc · Kéo để di chuyển · Ctrl + cuộn để thu phóng</span>
            </div>
            </div>

            {selectedNode && selectedStyle && (
              <article className={`rounded-3xl border bg-slate-50/90 p-4 sm:p-5 ${selectedType && ["time", "person", "event", "meaning"].includes(selectedType) ? "border-red-200" : "border-slate-200"}`} aria-live="polite" aria-labelledby="mindmap-detail-title">
              <div className="flex min-w-0 flex-col gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span className={`mt-1 h-3 w-3 shrink-0 rounded-full ${selectedStyle.dot}`} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-black uppercase leading-5 tracking-[0.12em] text-slate-500">
                      {selectedStyle.label} · {selectedNode.id === graph.rootId ? "Chủ đề" : `Tầng ${graph.depths.get(selectedNode.id) ?? 1}`}
                    </p>
                    <h3 id="mindmap-detail-title" className={`mt-0.5 break-words text-lg font-black leading-6 ${selectedType && ["time", "person", "event", "meaning"].includes(selectedType) ? "text-red-800" : "text-ink"}`}>
                      {nonEmptyText(selectedNode.label) ?? "Ý kiến thức"}
                    </h3>
                    {selectedDescription && <p className="mt-1 w-full break-words text-sm leading-6 text-slate-700">{selectedDescription}</p>}
                  </div>
                </div>
                {selectedParent && (
                  <button
                    type="button"
                    onClick={() => focusNode(selectedParent.id)}
                    title={`Quay lại: ${nonEmptyText(selectedParent.label) ?? "Nhánh trước"}`}
                    className="inline-flex max-w-full self-start overflow-hidden rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 hover:border-brand-200 hover:text-brand-700"
                  >
                    <span className="shrink-0" aria-hidden>←&nbsp;</span>
                    <span className="truncate">{nonEmptyText(selectedParent.label) ?? "Nhánh trước"}</span>
                  </button>
                )}
              </div>

              {(selectedTime || selectedPeople.length > 0 || selectedDetails.length > 0 || selectedMemoryPoints.length > 0) && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {selectedTime && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-3">
                      <p className="text-xs font-black uppercase tracking-wide text-red-700">Mốc thời gian</p>
                      <p className="mt-1 text-base font-black text-red-800">{selectedTime}</p>
                    </div>
                  )}
                  {selectedPeople.length > 0 && (
                    <div className="rounded-2xl border border-red-200 bg-white p-3">
                      <p className="text-xs font-black uppercase tracking-wide text-red-700">Nhân vật liên quan</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedPeople.map((person) => (
                          <span key={person} className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-black text-red-800 ring-1 ring-red-100">
                            {person}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedDetails.length > 0 && (
                    <div className="rounded-2xl border border-brand-100 bg-white p-3 sm:col-span-2">
                      <p className="text-xs font-black uppercase tracking-wide text-brand-700">Chi tiết cần hiểu</p>
                      <ul className="mt-2 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                        {selectedDetails.map((detail) => (
                          <li key={detail} className="flex gap-2">
                            <span className="font-black text-brand-500" aria-hidden>•</span>
                            <span>{detail}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedMemoryPoints.length > 0 && (
                    <div className="rounded-2xl border border-orange-200 bg-orange-50 p-3 sm:col-span-2">
                      <p className="text-xs font-black uppercase tracking-wide text-orange-800">Ghi nhớ nhanh</p>
                      <ul className="mt-2 space-y-1 text-sm font-semibold text-orange-950">
                        {selectedMemoryPoints.map((point) => <li key={point}>✓ {point}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {selectedChildren.length > 0 && (
                <div className="mt-4 border-t border-slate-200 pt-3">
                  <p className="text-xs font-black uppercase tracking-wide text-slate-500">Các ý phát triển từ nhánh này</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedChildren.map((childId) => {
                      const child = graph.byId.get(childId);
                      if (!child) return null;
                      const childStyle = styleFor(child, graph.rootId);
                      return (
                        <button
                          key={childId}
                          type="button"
                          onClick={() => focusNode(childId)}
                          className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 hover:border-brand-200 hover:text-brand-700"
                        >
                          <span className={`h-2 w-2 rounded-full ${childStyle.dot}`} aria-hidden />
                          {nonEmptyText(child.label) ?? "Ý kiến thức"}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              {selectedNode.id !== graph.rootId && (fullGraph.children.get(selectedNode.id)?.length ?? 0) > 0 && (
                <button
                  type="button"
                  onClick={() => toggleBranch(selectedNode.id)}
                  className="mt-4 min-h-11 w-full rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-extrabold text-brand-700 hover:bg-brand-50"
                  aria-expanded={!collapsedIds.has(selectedNode.id)}
                >
                  {collapsedIds.has(selectedNode.id) ? "Mở các ý trong nhánh" : "Thu gọn nhánh này"}
                </button>
              )}
              </article>
            )}
          </div>

          <details className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer font-extrabold text-brand-700">Xem sơ đồ dạng danh sách</summary>
            <p className="mt-2 text-sm text-slate-500">Các ý được thụt vào để thể hiện quan hệ từ khái quát đến chi tiết.</p>
            {graph.rootId && (
              <ul className="mt-4">
                <OutlineNode graph={graph} nodeId={graph.rootId} onSelect={focusNode} />
              </ul>
            )}
          </details>
        </>
      )}
    </section>
  );
}
