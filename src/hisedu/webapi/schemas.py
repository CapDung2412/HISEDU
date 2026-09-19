from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ShortText = Annotated[str, Field(min_length=1, max_length=500)]
Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QuestionRequest(ApiModel):
    question: Annotated[str, Field(min_length=3, max_length=2_000)]
    top_k: int = Field(default=5, ge=1, le=10)


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
    type: Literal["root", "cause", "event", "result", "meaning"]


class MindmapEdge(ApiModel):
    source: Identifier
    target: Identifier


class Mindmap(ApiModel):
    title: ShortText
    nodes: list[MindmapNode] = Field(min_length=6, max_length=15)
    edges: list[MindmapEdge] = Field(max_length=30)

    @model_validator(mode="after")
    def validate_graph(self) -> "Mindmap":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("mindmap node ids must be unique")
        known = set(node_ids)
        if any(edge.source not in known or edge.target not in known for edge in self.edges):
            raise ValueError("mindmap edges must reference existing nodes")
        roots = [node.id for node in self.nodes if node.type == "root"]
        if len(roots) != 1:
            raise ValueError("mindmap must contain exactly one root node")
        pairs = [(edge.source, edge.target) for edge in self.edges]
        if len(pairs) != len(set(pairs)) or any(source == target for source, target in pairs):
            raise ValueError("mindmap edges must be unique and cannot be self-references")
        reachable = {roots[0]}
        while True:
            expanded = reachable | {
                target for source, target in pairs if source in reachable
            }
            if expanded == reachable:
                break
            reachable = expanded
        if reachable != known:
            raise ValueError("every mindmap node must be reachable from the root")
        return self


class Source(ApiModel):
    id: Identifier
    title: ShortText
    publisher: ShortText
    type: Literal["dataset", "sgk", "government", "museum", "wikipedia", "news", "other"]
    url: str | None = None
    page: int | None = Field(default=None, ge=1, le=10_000)
    locator: str | None = Field(default=None, max_length=500)
    accessed_at: str | None = Field(default=None, max_length=40)
    supports: list[ShortText] = Field(max_length=20)


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

    @model_validator(mode="after")
    def validate_options(self) -> "QuizQuestion":
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("quiz option ids must be unique")
        return self


class Quiz(ApiModel):
    quiz_id: Identifier
    questions: list[QuizQuestion] = Field(min_length=5, max_length=5)


class RetrievalInfo(ApiModel):
    matched_ids: list[str]
    score_kind: Literal["cosine", "reciprocal_rank_fusion", "mixed"]
    low_confidence: bool


class AskResponse(ApiModel):
    request_id: str
    question: str
    answer: AnswerContent
    mindmap: Mindmap
    videos: list[Video] = Field(max_length=3)
    sources: list[Source] = Field(max_length=20)
    quiz: Quiz
    retrieval: RetrievalInfo
    limitations: list[str] = Field(max_length=20)


class QuizSubmitRequest(ApiModel):
    answers: dict[Identifier, Identifier] = Field(min_length=1, max_length=5)


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
    page: int | None = Field(ge=1, le=10_000)
    locator: str | None
    accessed_at: str | None
    supports: list[ShortText]


class GeneratedQuizQuestion(QuizQuestion):
    correct_option_id: Identifier
    explanation: Annotated[str, Field(min_length=1, max_length=2_000)]
    source_ids: list[Identifier]

    @model_validator(mode="after")
    def validate_correct_option(self) -> "GeneratedQuizQuestion":
        if self.correct_option_id not in {option.id for option in self.options}:
            raise ValueError("correct_option_id must reference one of the four options")
        return self


class GeneratedLesson(ApiModel):
    answer: AnswerContent
    mindmap: Mindmap
    videos: list[Video] = Field(max_length=3)
    sources: list[GeneratedSource] = Field(max_length=20)
    quiz: list[GeneratedQuizQuestion] = Field(min_length=5, max_length=5)
    limitations: list[str] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_quiz_ids(self) -> "GeneratedLesson":
        question_ids = [question.id for question in self.quiz]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("quiz question ids must be unique")
        return self
