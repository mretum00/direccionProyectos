import type { AssistantResponse, ChatRequest } from './chat';
import type { Conversation } from './conversation';
import type { TechnicalDocument } from './document';

export interface HealthResponse {
  status: string;
  version?: string;
}

export interface ApiClient {
  health(): Promise<HealthResponse>;
  chat(request: ChatRequest): Promise<AssistantResponse>;
  listDocuments(): Promise<TechnicalDocument[]>;
  uploadDocument(file: File): Promise<TechnicalDocument>;
  getSource(id: string): Promise<{ excerpt: string; url?: string }>;
}

export interface ConversationRepository {
  list(): Promise<Conversation[]>;
  get(id: string): Promise<Conversation | null>;
  save(conversation: Conversation): Promise<void>;
  delete(id: string): Promise<void>;
}

export const API_CONTRACT_VERSION = '1.0.0';
