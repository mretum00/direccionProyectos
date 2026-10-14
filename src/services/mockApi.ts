import type { ApiClient, HealthResponse } from '@/types/contract';
import type { AssistantResponse, ChatRequest } from '@/types/chat';
import type { TechnicalDocument } from '@/types/document';
import { MOCK_DOCUMENTS, mockChatResponse, uuid } from './mockData';

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export const mockApi: ApiClient = {
  async health(): Promise<HealthResponse> {
    await delay(200);
    return { status: 'ok', version: 'mock-1.0.0' };
  },

  async chat(request: ChatRequest): Promise<AssistantResponse> {
    await delay(800 + Math.random() * 700);
    void request;
    return mockChatResponse(request.message);
  },

  async listDocuments(): Promise<TechnicalDocument[]> {
    await delay(300);
    return MOCK_DOCUMENTS;
  },

  async uploadDocument(file: File): Promise<TechnicalDocument> {
    await delay(500);
    return {
      id: uuid(),
      filename: file.name,
      type: 'manual',
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      pages: 0,
      uploaded_at: new Date().toISOString(),
      status: 'pending',
    };
  },

  async getSource(id: string): Promise<{ excerpt: string; url?: string }> {
    await delay(200);
    void id;
    return {
      excerpt: 'Fragmento de demostración. En el entorno real, este contenido provendría del backend.',
    };
  },
};
