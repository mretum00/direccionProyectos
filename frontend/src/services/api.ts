import { config } from '@/config';
import { currentToken } from '@/services/session';
import type { AssistantResponse, ChatRequest } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import type { TechnicalDocument } from '@/types/document';
import type { LoginResponse, User } from '@/types/user';

/** El servidor respondió con un error (4xx/5xx). Sin conexión, `fetch` lanza un TypeError. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** En un 422 (validación), los campos del cuerpo que el backend ha rechazado: ['password']... */
    readonly fields: string[] = [],
  ) {
    super(message);
  }
}

/** Campos rechazados de un 422 de FastAPI: `detail` es una lista de errores con `loc: ['body', campo]`. */
function invalidFields(detail: unknown): string[] {
  if (!Array.isArray(detail)) return [];
  return detail
    .map((item) => (Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null))
    .filter((field): field is string => typeof field === 'string');
}

/** Lo registra el AuthProvider: se llama cuando el backend responde 401 (sesión caducada o cerrada). */
let onUnauthorized: () => void = () => undefined;

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

/**
 * Todas las llamadas al backend (FastAPI) están en este archivo.
 * Añade el token de la sesión a cada petición (cabecera Authorization).
 */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  const token = currentToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${config.apiUrl}${path}`, { ...init, headers });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === 'string' ? body.detail : `Error ${response.status} en ${path}`;
    // Un 401 del login son credenciales incorrectas, no una sesión caducada.
    if (response.status === 401 && token && !path.startsWith('/api/auth/login')) onUnauthorized();
    throw new ApiError(response.status, detail, invalidFields(body?.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function json(method: string, body?: unknown): RequestInit {
  return { method, body: body === undefined ? undefined : JSON.stringify(body) };
}

export const api = {
  // --- Usuarios ---

  /** POST /api/auth/register: crea la cuenta (no inicia sesión). */
  register(username: string, password: string): Promise<User> {
    return request<User>('/api/auth/register', json('POST', { username, password }));
  },

  /** POST /api/auth/login: devuelve el token de la sesión y el usuario. */
  login(username: string, password: string): Promise<LoginResponse> {
    return request<LoginResponse>('/api/auth/login', json('POST', { username, password }));
  },

  /** POST /api/auth/logout: invalida el token en el servidor. */
  logout(): Promise<void> {
    return request<void>('/api/auth/logout', json('POST'));
  },

  /** GET /api/auth/me: comprueba que la sesión guardada sigue siendo válida. */
  me(): Promise<User> {
    return request<User>('/api/auth/me');
  },

  // --- Chat y conversaciones ---

  /** POST /api/chat: envía la pregunta; el backend la guarda junto con la respuesta. */
  async chat(body: ChatRequest, signal?: AbortSignal): Promise<AssistantResponse> {
    const reply = await request<AssistantResponse>('/api/chat', { ...json('POST', body), signal });
    if (typeof reply.message?.content !== 'string' || !reply.conversation) {
      throw new Error('Respuesta inválida del servidor');
    }
    return reply;
  },

  /** POST /api/chat/{message_id}/cancel: la pregunta no se guarda (y se borra si ya estaba guardada). */
  cancelChat(messageId: string): Promise<void> {
    return request<void>(`/api/chat/${encodeURIComponent(messageId)}/cancel`, json('POST'));
  },

  /** GET /api/conversations: chats del usuario, los más recientes primero. */
  async listConversations(): Promise<Conversation[]> {
    const data = await request<{ conversations: Conversation[] }>('/api/conversations');
    return data.conversations;
  },

  /** PATCH /api/conversations/{id}: renombrar o marcar como favorita. */
  updateConversation(id: string, changes: { title?: string; favorite?: boolean }): Promise<Conversation> {
    return request<Conversation>(`/api/conversations/${encodeURIComponent(id)}`, json('PATCH', changes));
  },

  /** POST /api/conversations/{id}/duplicate */
  duplicateConversation(id: string): Promise<Conversation> {
    return request<Conversation>(`/api/conversations/${encodeURIComponent(id)}/duplicate`, json('POST'));
  },

  /** DELETE /api/conversations/{id} */
  deleteConversation(id: string): Promise<void> {
    return request<void>(`/api/conversations/${encodeURIComponent(id)}`, json('DELETE'));
  },

  // --- Versiones y documentos (públicos) ---

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

  /** URL del PDF de un documento (GET /api/documents/{id}/file): se usa como enlace, no hace fetch. */
  documentFileUrl(id: string): string {
    return `${config.apiUrl}/api/documents/${encodeURIComponent(id)}/file`;
  },
};
