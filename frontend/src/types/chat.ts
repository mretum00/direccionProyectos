import type { Conversation } from './conversation';

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
  /** Versión y perfil con los que se hizo la pregunta (se pueden cambiar a mitad del chat). */
  engine_version?: string;
  profile?: Profile | '';
  /** Solo en los mensajes del asistente: evidencia, fuentes... (el texto ya va en `content`). */
  response?: AnswerMeta;
}

/** Cuerpo de POST /api/chat. El historial no se envía: el backend lo lee de la conversación guardada. */
export interface ChatRequest {
  conversation_id: string;
  /** Id de la pregunta: reenviarla con el mismo id (reintento) devuelve lo guardado sin duplicarla. */
  message_id: string;
  message: string;
  engine_version: string;
  profile: Profile;
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
  /** La conversación ya guardada en el backend, con la pregunta y esta respuesta. */
  conversation: Conversation;
}

/** La respuesta sin el texto: es lo que se guarda en cada mensaje, para no duplicar el contenido. */
export type AnswerMeta = Omit<AssistantResponse, 'message' | 'conversation'>;
