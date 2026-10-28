import type { Conversation } from '@/types/conversation';
import { ApiError, apiRequest } from './httpClient';

const BASE = '/api/conversations';

async function list(): Promise<Conversation[]> {
  const data = await apiRequest<Conversation[] | { conversations: Conversation[] }>(BASE);
  return Array.isArray(data) ? data : data.conversations;
}

async function get(id: string): Promise<Conversation | null> {
  try {
    return await apiRequest<Conversation>(`${BASE}/${encodeURIComponent(id)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

async function create(conversation: Conversation): Promise<void> {
  await apiRequest(BASE, { method: 'POST', body: JSON.stringify(conversation) });
}

async function update(conversation: Conversation): Promise<void> {
  await apiRequest(BASE, { method: 'PUT', body: JSON.stringify(conversation) });
}

/** Actualiza y, si el backend aún no la conoce (404), la crea. */
async function save(conversation: Conversation): Promise<void> {
  try {
    await update(conversation);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return create(conversation);
    throw e;
  }
}

async function remove(id: string): Promise<void> {
  await apiRequest(`${BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export const conversationsController = { list, get, create, update, save, remove };
