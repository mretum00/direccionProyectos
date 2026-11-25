import type { Conversation } from './conversation';

type Role = 'user' | 'assistant';

export type EvidenceStatus = 'high' | 'medium' | 'insufficient';

export type ClarificationKind = 'engine_version' | 'technical' | 'version_mismatch' | 'version_comparison';

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

export interface SafetyAlert {
  code: 'real_vehicle' | 'high_voltage' | 'engine_overheating';
  severity: 'warning' | 'critical';
  title: string;
  message: string;
}

export type ClaimCheckStatus = 'supported' | 'conflicting' | 'not_found' | 'uncertain' | 'unverified';

export interface ClaimCheck {
  claim: string;
  status: ClaimCheckStatus;
  source_ids: string[];
  evidence_excerpt?: string | null;
}

export interface ClaimVerification {
  status: 'reviewed' | 'needs_review' | 'unavailable' | 'no_claims' | 'not_run';
  claims_total: number;
  claims_supported: number;
  claims: ClaimCheck[];
  /** Indica que el backend limitó el texto a afirmaciones con cita literal validada. */
  answer_restricted?: boolean;
}

export type RequestedEvidenceStatus = 'supported' | 'not_found' | 'uncertain' | 'conflicting';

export interface RequestedEvidenceItem {
  item: string;
  status: RequestedEvidenceStatus;
  source_ids: string[];
  evidence_excerpt?: string | null;
}

export interface EvidenceSufficiency {
  status: 'sufficient' | 'partial' | 'insufficient' | 'unavailable' | 'not_run';
  requested_items: RequestedEvidenceItem[];
  missing_information: string[];
}

export interface Source {
  id: string;
  document: string;
  source_type: SourceType;
  section?: string;
  page?: number;
  engine_version?: string;
  excerpt?: string;
  /** Citada explícitamente por el modelo o solo recuperada como contexto. */
  citation_status?: 'cited' | 'verified' | 'retrieved';
}

/** Fragmento recuperado durante la búsqueda y si se usó en la respuesta. */
export interface StepFragment {
  document: string;
  source_type: SourceType;
  page?: number;
  section?: string;
  score: number;
  used: boolean;
  /** Por qué aplica a la versión elegida si viene de otra edición del documento. */
  note?: string;
}

/** Resumen breve de una comprobación respaldada por fuentes. */
export interface StepPoint {
  text: string;
  refs?: string[];
  /** Resultado de una comprobación previa: superada, detiene la consulta u omitida. */
  status?: 'ok' | 'stop' | 'skipped';
}

/** Etapa observable de transformación de la consulta. */
export interface QueryStage {
  label: string;
  text: string;
  terms?: string[];
  note?: string;
}

/** Fases observables del proceso RAG; no contiene razonamiento interno del modelo. */
export interface ReasoningStep {
  kind: 'checks' | 'query' | 'interpretation' | 'search' | 'analysis' | 'conclusion';
  title: string;
  detail?: string;
  stages?: QueryStage[];
  terms?: string[];
  fragments?: StepFragment[];
  points?: StepPoint[];
  evidence?: EvidenceStatus;
}

/** Respuesta de POST /api/chat. */
export interface AssistantResponse {
  message: { id: string; content: string };
  evidence_status?: EvidenceStatus;
  needs_clarification?: boolean;
  clarification_kind?: ClarificationKind;
  documents_consulted?: number;
  sources?: Source[];
  /** Avisos deterministas de seguridad calculados por el backend, independientes del LLM. */
  safety_alerts?: SafetyAlert[];
  /** Revisión automática orientativa de afirmaciones frente a fragmentos recuperados. */
  claim_verification?: ClaimVerification;
  /** Comprobación previa de que los fragmentos cubren los datos solicitados (R07). */
  evidence_sufficiency?: EvidenceSufficiency;
  /** Pasos observables del proceso RAG (texto plano en respuestas antiguas). */
  steps?: (ReasoningStep | string)[];
  /** La conversación ya guardada en el backend, con la pregunta y esta respuesta. */
  conversation: Conversation;
}

/** La respuesta sin el texto: es lo que se guarda en cada mensaje, para no duplicar el contenido. */
export type AnswerMeta = Omit<AssistantResponse, 'message' | 'conversation'>;