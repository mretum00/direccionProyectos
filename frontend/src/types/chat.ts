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

/** Fragmento recuperado en la búsqueda: similitud y si se ha usado en la respuesta. */
export interface StepFragment {
  document: string;
  source_type: SourceType;
  page?: number;
  section?: string;
  score: number;
  used: boolean;
}

/** Un paso del razonamiento del modelo y los fragmentos que cita ("HTM240-DIA-001 · pág. 1"). */
export interface StepPoint {
  text: string;
  refs?: string[];
}

/** Una etapa de la transformación de la consulta: original, reformulada o técnica generada. */
export interface QueryStage {
  label: string;
  text: string;
  /** Códigos técnicos que ha añadido esta etapa. */
  terms?: string[];
  note?: string;
}

/** Una fase de los pasos seguidos para llegar a la respuesta. */
export interface ReasoningStep {
  /** 'interpretation' solo aparece en respuestas guardadas antes de `stages`. */
  kind: 'query' | 'interpretation' | 'search' | 'analysis' | 'conclusion';
  title: string;
  detail?: string;
  /** query: de la pregunta original a la consulta técnica generada. */
  stages?: QueryStage[];
  /** interpretation: códigos técnicos detectados en la consulta. */
  terms?: string[];
  /** search: fragmentos recuperados. */
  fragments?: StepFragment[];
  /** analysis: pasos del razonamiento del modelo. */
  points?: StepPoint[];
  /** conclusion: nivel de evidencia. */
  evidence?: EvidenceStatus;
}

/** Respuesta de POST /api/chat. */
export interface AssistantResponse {
  message: { id: string; content: string };
  evidence_status?: EvidenceStatus;
  needs_clarification?: boolean;
  documents_consulted?: number;
  /** Solo las fuentes de las que se ha sacado la información de la respuesta. */
  sources?: Source[];
  /** Pasos seguidos para llegar a la respuesta, por fases (texto plano en respuestas antiguas). */
  steps?: (ReasoningStep | string)[];
  /** La conversación ya guardada en el backend, con la pregunta y esta respuesta. */
  conversation: Conversation;
}

/** La respuesta sin el texto: es lo que se guarda en cada mensaje, para no duplicar el contenido. */
export type AnswerMeta = Omit<AssistantResponse, 'message' | 'conversation'>;
