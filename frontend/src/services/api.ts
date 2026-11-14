import { config } from '@/config';
import type { AssistantResponse, ChatRequest } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import type { TechnicalDocument } from '@/types/document';

/**
 * Todas las llamadas al backend (FastAPI) están en este archivo.
 * - Sin conexión con el servidor: `fetch` lanza un TypeError.
 * - El servidor responde con error (4xx/5xx): lanzamos un Error normal.
 */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // Con FormData (subida de archivos) el navegador pone el Content-Type él solo.
  const headers = init.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' };
  const response = await fetch(`${config.apiUrl}${path}`, { ...init, headers });
  if (!response.ok) throw new Error(`Error ${response.status} en ${path}`);
  // 204 No Content (guardar y borrar conversaciones): no hay cuerpo que leer.
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  /** POST /api/chat: envía la pregunta y devuelve la respuesta del asistente. */
  async chat(body: ChatRequest, signal?: AbortSignal): Promise<AssistantResponse> {
    const reply = await request<AssistantResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(body),
      signal,
    });
    if (typeof reply.message?.content !== 'string') {
      throw new Error('Respuesta inválida del servidor: falta message.content');
    }
    return reply;
  },

  /** GET /api/versions: versiones del sistema que admite el backend. */
  async listVersions(): Promise<string[]> {
    const data = await request<{ versions: string[] }>('/api/versions');
    return data.versions;
  },

  /** GET /api/documents */
  async listDocuments(): Promise<TechnicalDocument[]> {
    const data = await request<{ documents: TechnicalDocument[] }>('/api/documents');
    return data.documents;
  },

  /** POST /api/documents (subida de un PDF) */
  uploadDocument(file: File): Promise<TechnicalDocument> {
    const formData = new FormData();
    formData.append('file', file);
    return request<TechnicalDocument>('/api/documents', { method: 'POST', body: formData });
  },

  /** GET /api/conversations */
  async listConversations(): Promise<Conversation[]> {
    const data = await request<{ conversations: Conversation[] }>('/api/conversations');
    return data.conversations;
  },

  /** PUT /api/conversations: la crea si no existe y la reemplaza si ya existe. */
  saveConversation(conversation: Conversation): Promise<void> {
    return request<void>('/api/conversations', { method: 'PUT', body: JSON.stringify(conversation) });
  },

  /** DELETE /api/conversations/{id} */
  deleteConversation(id: string): Promise<void> {
    return request<void>(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },
};
