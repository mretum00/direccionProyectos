type Role = 'user' | 'assistant';

type EvidenceStatus = 'high' | 'medium' | 'insufficient';

export type SourceType =
  | 'manual'
  | 'dtc_catalog'
  | 'decision_tree'
  | 'historical_case'
  | 'safety_manual'
  | 'glossary';

export type Profile = 'mechanic' | 'user';

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  created_at?: string;
  /** Solo en los mensajes del asistente: evidencia, fuentes... (el texto ya va en `content`). */
  response?: AnswerMeta;
}

export interface ChatRequest {
  message: string;
  engine_version: string;
  profile: Profile;
  history: { role: Role; content: string }[];
}

export interface Source {
  id: string;
  document: string;
  source_type: SourceType;
  section?: string;
  page?: number;
  engine_version?: string;
  excerpt?: string;
}

/** Respuesta de POST /api/chat. */
export interface AssistantResponse {
  message: { id: string; content: string };
  evidence_status?: EvidenceStatus;
  needs_clarification?: boolean;
  documents_consulted?: number;
  sources?: Source[];
}

/** La respuesta sin el texto: es lo que se guarda en cada mensaje, para no duplicar el contenido. */
export type AnswerMeta = Omit<AssistantResponse, 'message'>;
