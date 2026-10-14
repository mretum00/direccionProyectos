export type Role = 'user' | 'assistant';

export type EvidenceStatus = 'high' | 'medium' | 'insufficient';

export type Criticality = 'low' | 'medium' | 'high' | 'critical';

export type SafetyLevel = 'warning' | 'critical';

export type SourceType =
  | 'manual'
  | 'dtc_catalog'
  | 'decision_tree'
  | 'historical_case'
  | 'safety_manual'
  | 'glossary';

export type EngineSystem = 'CIR-01' | 'CIR-02' | 'CIR-03' | null;

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
  system?: EngineSystem;
  profile: Profile;
  history: { role: Role; content: string }[];
  vehicle?: {
    brand?: string;
    model?: string;
    year?: number | null;
    vin?: string;
  };
}

export interface SafetyItem {
  level: SafetyLevel;
  text: string;
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

export interface InterpretedQuery {
  original: string;
  technical_terms: string[];
}

export interface DetectedDTC {
  code: string;
  description: string;
}

export interface ResponseSections {
  diagnosis?: string;
  possible_causes?: string[];
  criticality?: Criticality;
  safety?: SafetyItem[];
  ppe?: string[];
  checks?: string[];
  decision_tree_id?: string;
  procedure?: string;
}

export interface Source {
  id: string;
  document: string;
  source_type: SourceType;
  section?: string;
  page?: number;
  engine?: string;
  engine_version?: string;
  system?: string;
  excerpt?: string;
  url?: string;
}

export interface DiscardedSource {
  document: string;
  reason: 'obsolete_version' | 'version_mismatch';
  detail?: string;
}

export interface AssistantResponse {
  message: { id: string; role: 'assistant'; content: string };
  evidence_status?: EvidenceStatus;
  needs_clarification?: boolean;
  confidence?: number;
  documents_consulted?: number;
  interpreted_query?: InterpretedQuery;
  detected_dtc?: DetectedDTC[];
  sections?: ResponseSections;
  clarification?: Clarification;
  sources?: Source[];
  discarded_sources?: DiscardedSource[];
}
