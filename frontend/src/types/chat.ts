export type Role = 'user' | 'assistant';

export type EvidenceStatus = 'high' | 'medium' | 'insufficient';

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
  response?: AssistantResponse;
}

export interface ChatRequest {
  conversation_id: string;
  message: string;
  engine: string;
  engine_version: string;
  profile: Profile;
  history: { role: Role; content: string }[];
}

export interface ClarificationMissingField {
  key: string;
  label: string;
  options?: string[];
}

export interface Clarification {
  message?: string;
  missing_fields: ClarificationMissingField[];
}

export interface Source {
  id: string;
  document: string;
  source_type: SourceType;
  section?: string;
  page?: number;
  engine?: string;
  engine_version?: string;
  excerpt?: string;
  url?: string;
}

export interface AssistantResponse {
  message: { id: string; role: 'assistant'; content: string };
  evidence_status?: EvidenceStatus;
  needs_clarification?: boolean;
  documents_consulted?: number;
  clarification?: Clarification;
  sources?: Source[];
}
