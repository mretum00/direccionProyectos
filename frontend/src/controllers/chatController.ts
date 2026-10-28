import type { AssistantResponse, ChatRequest } from '@/types/chat';
import { apiRequest } from './httpClient';

/** Valida lo mínimo que exige el contrato: `message.content` como string. */
function parseChatResponse(raw: unknown): AssistantResponse {
  const message = (raw as { message?: { content?: unknown } } | null)?.message;
  if (typeof message?.content !== 'string') {
    throw new Error('Respuesta inválida del servidor: falta message.content');
  }
  return raw as AssistantResponse;
}

export const chatController = {
  async send(request: ChatRequest, signal?: AbortSignal): Promise<AssistantResponse> {
    // Última barrera: la UI ya lo impide, pero ninguna petición debe salir sin versión.
    if (!request.engine_version?.trim()) {
      throw new Error('La consulta no puede enviarse sin versión del motor');
    }
    const raw = await apiRequest<unknown>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(request),
      signal,
    });
    return parseChatResponse(raw);
  },
};
