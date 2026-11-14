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
  async saveConversation(conversation: Conversation): Promise<void> {
    await request('/api/conversations', { method: 'PUT', body: JSON.stringify(conversation) });
  },

  /** DELETE /api/conversations/{id} */
  async deleteConversation(id: string): Promise<void> {
    await request(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },
};
