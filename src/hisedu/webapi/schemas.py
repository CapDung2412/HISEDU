from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ShortText = Annotated[str, Field(min_length=1, max_length=500)]
Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


_MINDMAP_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_MINDMAP_TYPE_ALIASES = {
    "character": "person",
    "consequence": "result",
    "date": "time",
    "development": "event",
    "key-point": "memory",
    "key_point": "memory",
    "memory-point": "memory",
    "memory_point": "memory",
    "outcome": "result",
    "people": "person",
    "significance": "meaning",
    "timeline": "time",
}
_MINDMAP_TYPES = {
    "root",
    "time",
    "person",
    "cause",
    "event",
    "result",
    "meaning",
    "memory",
}


def _safe_mindmap_id(value: object, index: int, used: set[str]) -> str:
    raw = str(value or "").strip()
    if _MINDMAP_ID_PATTERN.fullmatch(raw) and len(raw) <= 100:
        base = raw
    else:
        ascii_text = unicodedata.normalize("NFKD", raw)
        ascii_text = "".join(char for char in ascii_text if not unicodedata.combining(char))
        ascii_text = ascii_text.replace("đ", "d").replace("Đ", "D")
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", ascii_text).strip("-_")[:90]
        if not base:
            base = f"node-{index}"
    candidate = base
    suffix = 2
    while candidate in used:
        tail = f"-{suffix}"
        candidate = f"{base[:100 - len(tail)]}{tail}"
        suffix += 1
    used.add(candidate)
    return candidate


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QuestionRequest(ApiModel):
    question: Annotated[str, Field(min_length=3, max_length=2_000)]
    top_k: int = Field(default=3, ge=1, le=10)


class AnswerSection(ApiModel):
    heading: ShortText
    content: Annotated[str, Field(min_length=1, max_length=5_000)]
    citation_ids: list[Identifier] = Field(max_length=20)


class AnswerContent(ApiModel):
    summary: Annotated[str, Field(min_length=1, max_length=3_000)]
    sections: list[AnswerSection] = Field(max_length=10)
    key_points: list[ShortText] = Field(max_length=12)
    citation_ids: list[Identifier] = Field(max_length=30)


class MindmapNode(ApiModel):
    id: Identifier
    label: ShortText
    description: Annotated[str, Field(min_length=1, max_length=1_000)]
    type: Literal[
        "root",
        "time",
        "person",
        "cause",
        "event",
        "result",
        "meaning",
        "memory",
    ]


class MindmapEdge(ApiModel):
    source: Identifier
    target: Identifier


class Mindmap(ApiModel):
    title: ShortText
    # The prompt asks for 10-15 nodes. Runtime validation accepts a smaller
    # partial map so one formatting mistake does not discard a valid lesson.
    nodes: list[MindmapNode] = Field(min_length=1, max_length=20)
    edges: list[MindmapEdge] = Field(max_length=40)

    @model_validator(mode="before")
    @classmethod
    def normalize_graph_shape(cls, value: Any) -> Any:
        """Repair harmless model-formatting mistakes without changing facts."""
        if not isinstance(value, dict):
            return value
        raw_nodes = value.get("nodes")
        fallback_title = str(value.get("title") or "").strip()[:500] or "Sơ đồ tư duy"
        if not isinstance(raw_nodes, list) or not raw_nodes:
            return {
                "title": fallback_title,
                "nodes": [
                    {
                        "id": "root",
                        "label": fallback_title,
                        "description": fallback_title,
                        "type": "root",
                    }
                ],
                "edges": [],
            }

        nodes: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        first_id_for_raw: dict[str, str] = {}
        root_seen = False
        for index, raw_node in enumerate(raw_nodes[:20], start=1):
            if not isinstance(raw_node, dict):
                continue
            raw_id = str(raw_node.get("id") or "").strip()
            node_id = _safe_mindmap_id(raw_id, index, used_ids)
            if raw_id and raw_id not in first_id_for_raw:
                first_id_for_raw[raw_id] = node_id

            raw_type = str(raw_node.get("type") or "event").strip().casefold()
            node_type = _MINDMAP_TYPE_ALIASES.get(raw_type, raw_type)
            if node_type not in _MINDMAP_TYPES:
                node_type = "event"
            if node_type == "root":
                if root_seen:
                    node_type = "event"
                else:
                    root_seen = True

            label = str(raw_node.get("label") or "").strip()[:500]
            description = str(raw_node.get("description") or "").strip()[:1_000]
            nodes.append(
                {
                    "id": node_id,
                    "label": label or f"Ý kiến thức {index}",
                    "description": description or label or "Thông tin trong sơ đồ tư duy.",
                    "type": node_type,
                }
            )

        if not nodes:
            return {
                "title": fallback_title,
                "nodes": [
                    {
                        "id": "root",
                        "label": fallback_title,
                        "description": fallback_title,
                        "type": "root",
                    }
                ],
                "edges": [],
            }
        if not root_seen:
            nodes[0]["type"] = "root"

        known_ids = {node["id"] for node in nodes}
        edges: list[dict[str, str]] = []
        raw_edges = value.get("edges")
        if isinstance(raw_edges, list):
            for raw_edge in raw_edges[:40]:
                if not isinstance(raw_edge, dict):
                    continue
                raw_source = str(raw_edge.get("source") or "").strip()
                raw_target = str(raw_edge.get("target") or "").strip()
                source = first_id_for_raw.get(raw_source, raw_source)
                target = first_id_for_raw.get(raw_target, raw_target)
                if source in known_ids and target in known_ids:
                    edges.append({"source": source, "target": target})

        return {
            "title": fallback_title,
            "nodes": nodes,
            "edges": edges,
        }

    @model_validator(mode="after")
    def validate_graph(self) -> "Mindmap":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("mindmap node ids must be unique")
        known = set(node_ids)
        roots = [node.id for node in self.nodes if node.type == "root"]
        if len(roots) != 1:
            raise ValueError("mindmap must contain exactly one root node")
        # Structured Outputs guarantees the edge shape, but graph invariants
        # such as reachability are not expressible in JSON Schema. Filter
        # dangling/duplicate edges, then repair an invalid orientation into a
        # small root-connected tree instead of rejecting the whole lesson.
        pairs: list[tuple[str, str]] = []
        for edge in self.edges:
            pair = (edge.source, edge.target)
            if (
                edge.source in known
                and edge.target in known
                and edge.source != edge.target
                and edge.target != roots[0]
                and pair not in pairs
            ):
                pairs.append(pair)
        reachable = {roots[0]}
        while True:
            expanded = reachable | {
                target for source, target in pairs if source in reachable
            }
            if expanded == reachable:
                break
            reachable = expanded
        # Keep valid multi-level branches. If the model leaves a disconnected
        # branch, attach only that branch's first node instead of flattening the
        # whole graph into a root star.
        while reachable != known:
            orphan = next(node_id for node_id in node_ids if node_id not in reachable)
            pairs.append((roots[0], orphan))
            while True:
                expanded = reachable | {
                    target for source, target in pairs if source in reachable
                }
                if expanded == reachable:
                    break
                reachable = expanded
        self.edges = [MindmapEdge(source=source, target=target) for source, target in pairs]
        return self


class Source(ApiModel):
    id: Identifier
    title: ShortText
    publisher: ShortText
    type: Literal["dataset", "sgk", "government", "museum", "wikipedia", "news", "other"]
    url: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    book_series: str | None = Field(default=None, max_length=500)
    page: int | None = Field(default=None, ge=1, le=10_000)
    page_status: Literal["verified", "unverified", "not_applicable"] = "not_applicable"
    locator: str | None = Field(default=None, max_length=500)
    accessed_at: str | None = Field(default=None, max_length=40)
    supports: list[ShortText] = Field(max_length=20)
    evidence_excerpt: str | None = Field(default=None, max_length=1_000)
    review_status: str | None = Field(default=None, max_length=500)
    provenance_note: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_textbook_identity(self) -> "Source":
        if self.type == "sgk":
            if self.grade is None or not self.book_series or self.page is None:
                raise ValueError("sgk sources require grade, book_series, and verified page")
            if self.page_status != "verified":
                raise ValueError("sgk page_status must be verified")
        if self.page_status == "verified" and self.page is None:
            raise ValueError("verified page_status requires page")
        if self.page_status == "unverified" and self.page is not None:
            raise ValueError("unverified page_status cannot include page")
        return self


class Video(ApiModel):
    title: ShortText
    url: Annotated[str, Field(min_length=8, max_length=2_000)]
    publisher: ShortText
    relevance: Annotated[str, Field(min_length=1, max_length=1_000)]
    label: Literal["cause", "event", "result", "meaning"]


class QuizOption(ApiModel):
    id: Identifier
    text: Annotated[str, Field(min_length=1, max_length=1_000)]


class QuizQuestion(ApiModel):
    id: Identifier
    prompt: Annotated[str, Field(min_length=1, max_length=2_000)]
    options: list[QuizOption] = Field(min_length=4, max_length=4)
    difficulty: Literal["remember", "understand", "apply"] = "understand"

    @model_validator(mode="after")
    def validate_options(self) -> "QuizQuestion":
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("quiz option ids must be unique")
        return self


class Quiz(ApiModel):
    quiz_id: Identifier
    questions: list[QuizQuestion] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_question_count(self) -> "Quiz":
        if len(self.questions) not in {0, 5}:
            raise ValueError("quiz must contain zero or five questions")
        return self


class RetrievalInfo(ApiModel):
    matched_ids: list[str]
    score_kind: Literal["cosine", "reciprocal_rank_fusion", "mixed"]
    low_confidence: bool


class AskResponse(ApiModel):
    request_id: str
    answer_id: Identifier
    question: str
    answer: AnswerContent
    mindmap: Mindmap
    videos: list[Video] = Field(max_length=6)
    sources: list[Source] = Field(max_length=20)
    quiz: Quiz
    retrieval: RetrievalInfo
    limitations: list[str] = Field(max_length=20)


class QuizSubmitRequest(ApiModel):
    answers: dict[Identifier, Identifier] = Field(min_length=1, max_length=5)


class QuizAnswerRequest(ApiModel):
    question_id: Identifier
    option_id: Identifier


class QuizResult(ApiModel):
    question_id: Identifier
    selected_option_id: str | None
    correct: bool
    correct_option_id: Identifier
    explanation: str
    source_ids: list[Identifier]


class QuizSubmitResponse(ApiModel):
    quiz_id: Identifier
    score: int = Field(ge=0, le=5)
    max_score: Literal[5] = 5
    results: list[QuizResult] = Field(min_length=5, max_length=5)


class QuizAnswerResponse(ApiModel):
    quiz_id: Identifier
    result: QuizResult
    next_question: QuizQuestion | None
    answered_count: int = Field(ge=1, le=5)
    total_questions: Literal[5] = 5
    score_so_far: int = Field(ge=0, le=5)
    completed: bool
    adaptive_message: Annotated[str, Field(min_length=1, max_length=500)]


class AnswerFeedbackRequest(ApiModel):
    rating: Literal["helpful", "not_helpful"]
    comment: str | None = Field(default=None, max_length=2_000)


class AnswerFeedbackResponse(ApiModel):
    feedback_id: Identifier
    status: Literal["pending_teacher_review"] = "pending_teacher_review"


class OcrPreviewResponse(ApiModel):
    text: Annotated[str, Field(min_length=3, max_length=2_000)]
    line_count: int = Field(ge=1, le=500)
    mean_score: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_review: bool


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    services: dict[str, str]


class ErrorDetail(ApiModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(ApiModel):
    error: ErrorDetail


# Internal Structured Output models. Optional-looking values remain required so
# the generated JSON Schema is compatible with OpenAI strict Structured Outputs.
class GeneratedSource(ApiModel):
    id: Identifier
    title: ShortText
    publisher: ShortText
    type: Literal["dataset", "sgk", "government", "museum", "wikipedia", "news", "other"]
    url: str | None
    grade: int | None = Field(ge=1, le=12)
    book_series: str | None
    page: int | None = Field(ge=1, le=10_000)
    page_status: Literal["verified", "unverified", "not_applicable"]
    locator: str | None
    accessed_at: str | None
    supports: list[ShortText]


class GeneratedQuizQuestion(QuizQuestion):
    # Required in strict Structured Outputs even though the public response
    # keeps a default for compatibility with older cached quizzes.
    difficulty: Literal["remember", "understand", "apply"]
    correct_option_id: Identifier
    explanation: Annotated[str, Field(min_length=1, max_length=2_000)]
    source_ids: list[Identifier]

    @model_validator(mode="after")
    def validate_correct_option(self) -> "GeneratedQuizQuestion":
        if self.correct_option_id not in {option.id for option in self.options}:
            raise ValueError("correct_option_id must reference one of the four options")
        return self


class GeneratedLessonCore(ApiModel):
    answer: AnswerContent
    mindmap: Mindmap
    videos: list[Video] = Field(max_length=6)
    sources: list[GeneratedSource] = Field(max_length=20)
    limitations: list[str] = Field(max_length=20)


class GeneratedQuizBatch(ApiModel):
    quiz: list[GeneratedQuizQuestion] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_quiz_ids(self) -> "GeneratedQuizBatch":
        question_ids = [question.id for question in self.quiz]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("quiz question ids must be unique")
        return self


class GeneratedLesson(GeneratedLessonCore):
    # An empty quiz is allowed only as a degraded response when the optional
    # parallel quiz task is slower than the main lesson. Normal AI output is
    # validated by GeneratedQuizBatch and always contains exactly five items.
    quiz: list[GeneratedQuizQuestion] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_quiz_ids(self) -> "GeneratedLesson":
        if len(self.quiz) not in {0, 5}:
            raise ValueError("lesson quiz must contain zero or five questions")
        question_ids = [question.id for question in self.quiz]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("quiz question ids must be unique")
        return self
