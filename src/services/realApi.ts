import type { ApiClient, HealthResponse } from '@/types/contract';
import type { AssistantResponse, ChatRequest } from '@/types/chat';
import type { TechnicalDocument } from '@/types/document';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function safeResponse(raw: unknown): AssistantResponse {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Respuesta inválida del servidor');
  }
  const obj = raw as Record<string, unknown>;
  const message = obj.message;
  if (typeof message !== 'object' || message === null) {
    throw new Error('Respuesta sin campo message');
  }
  const msg = message as Record<string, unknown>;
  if (typeof msg.content !== 'string') {
    throw new Error('Respuesta sin message.content');
  }
  return obj as unknown as AssistantResponse;
}

export const realApi: ApiClient = {
  async health(): Promise<HealthResponse> {
    return request<HealthResponse>('/api/health');
  },

  async chat(req: ChatRequest): Promise<AssistantResponse> {
    const raw = await request<unknown>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(req),
    });
    return safeResponse(raw);
  },

  async listDocuments(): Promise<TechnicalDocument[]> {
    try {
      const data = await request<{ documents: TechnicalDocument[] } | TechnicalDocument[]>('/api/documents');
      return Array.isArray(data) ? data : data.documents;
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) return [];
      throw e;
    }
  },

  async uploadDocument(file: File): Promise<TechnicalDocument> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_URL}/api/documents`, { method: 'POST', body: formData });
    if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''));
    return res.json() as Promise<TechnicalDocument>;
  },

  async getSource(id: string): Promise<{ excerpt: string; url?: string }> {
    return request<{ excerpt: string; url?: string }>(`/api/sources/${id}`);
  },
};
