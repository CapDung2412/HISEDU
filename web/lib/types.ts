export type CitationId = string;

export interface AnswerSection {
  heading: string;
  content: string;
  citation_ids: CitationId[];
}

export interface LearningAnswer {
  summary: string;
  sections: AnswerSection[];
  key_points: string[];
  citation_ids: CitationId[];
}

export type MindMapNodeType =
  | "root"
  | "time"
  | "person"
  | "cause"
  | "event"
  | "result"
  | "meaning"
  | "memory";

export interface MindMapNode {
  id: string;
  label: string;
  description: string;
  type: MindMapNodeType;
  /** Optional structured facts. Older API responses can omit every field below. */
  details?: string[] | null;
  time?: string | null;
  people?: string[] | null;
  memory_points?: string[] | null;
}

export interface MindMapEdge {
  source: string;
  target: string;
}

export interface MindMapData {
  title: string;
  nodes: MindMapNode[];
  edges: MindMapEdge[];
}

export interface LearningVideo {
  title: string;
  url: string;
  publisher: string;
  relevance: string;
  label: "cause" | "event" | "result" | "meaning";
}

export interface ReferenceSource {
  id: CitationId;
  title: string;
  publisher: string;
  type: "dataset" | "sgk" | "government" | "museum" | "wikipedia" | "news" | "other";
  url?: string | null;
  grade?: number | null;
  book_series?: string | null;
  page?: number | null;
  page_status?: "verified" | "unverified" | "not_applicable";
  locator?: string | null;
  accessed_at?: string | null;
  supports: string[];
  evidence_excerpt?: string | null;
  review_status?: string | null;
  provenance_note?: string | null;
}

export type AnswerFeedbackRating = "helpful" | "not_helpful";

export interface AnswerFeedbackResponse {
  feedback_id: string;
  status: "pending_teacher_review";
}

export interface QuizOption {
  id: string;
  text: string;
}

export type QuizDifficulty = "remember" | "understand" | "apply";

/** Deliberately contains no correct-answer field. */
export interface QuizQuestion {
  id: string;
  prompt: string;
  options: QuizOption[];
  difficulty?: QuizDifficulty;
}

export interface QuizData {
  quiz_id: string;
  questions: QuizQuestion[];
}

export interface RetrievalInfo {
  matched_ids: string[];
  score_kind: "cosine" | "reciprocal_rank_fusion" | "mixed";
  low_confidence: boolean;
}

export interface AskResponse {
  request_id: string;
  answer_id: string;
  question: string;
  answer: LearningAnswer;
  mindmap: MindMapData;
  videos: LearningVideo[];
  sources: ReferenceSource[];
  quiz: QuizData;
  retrieval: RetrievalInfo;
  limitations: string[];
}

/**
 * Safe lesson data emitted as soon as the main answer has been checked.
 * Video and quiz are intentionally absent because they are still being built.
 */
export interface PartialLessonResponse {
  request_id: string;
  question: string;
  answer: LearningAnswer;
  mindmap: MindMapData;
  sources: ReferenceSource[];
  limitations: string[];
}

export interface OcrPreviewResponse {
  text: string;
  line_count: number;
  mean_score: number | null;
  needs_review: boolean;
}

export type LessonProgressStage =
  | "received"
  | "retrieval"
  | "generation"
  | "enrichment"
  | "finalizing";

export interface LessonProgressEvent {
  stage: LessonProgressStage;
  message: string;
}

export interface QuizResultItem {
  question_id: string;
  selected_option_id?: string | null;
  correct: boolean;
  correct_option_id: string;
  explanation: string;
  source_ids: CitationId[];
}

export interface QuizSubmitResponse {
  quiz_id: string;
  score: number;
  max_score: number;
  results: QuizResultItem[];
}

export interface QuizAnswerResponse {
  quiz_id: string;
  result: QuizResultItem;
  next_question: QuizQuestion | null;
  answered_count: number;
  total_questions: 5;
  score_so_far: number;
  completed: boolean;
  adaptive_message: string;
}

export interface QuestionSubmission {
  question: string;
  image?: File;
}
