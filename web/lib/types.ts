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
  | "cause"
  | "event"
  | "result"
  | "meaning";

export interface MindMapNode {
  id: string;
  label: string;
  description: string;
  type: MindMapNodeType;
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
  page?: number | null;
  locator?: string | null;
  accessed_at?: string | null;
  supports: string[];
}

export interface QuizOption {
  id: string;
  text: string;
}

/** Deliberately contains no correct-answer field. */
export interface QuizQuestion {
  id: string;
  prompt: string;
  options: QuizOption[];
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
  question: string;
  answer: LearningAnswer;
  mindmap: MindMapData;
  videos: LearningVideo[];
  sources: ReferenceSource[];
  quiz: QuizData;
  retrieval: RetrievalInfo;
  limitations: string[];
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

export interface QuestionSubmission {
  question: string;
  image?: File;
}
