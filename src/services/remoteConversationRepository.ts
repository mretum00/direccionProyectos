import type { ConversationRepository } from '@/types/contract';
import type { Conversation } from '@/types/conversation';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const remoteConversationRepository: ConversationRepository = {
  async list(): Promise<Conversation[]> {
    const data = await req<Conversation[] | { conversations: Conversation[] }>('/api/conversations');
    return Array.isArray(data) ? data : data.conversations;
  },

  async get(id: string): Promise<Conversation | null> {
    try {
      return await req<Conversation>(`/api/conversations/${id}`);
    } catch {
      return null;
    }
  },

  async save(conversation: Conversation): Promise<void> {
    await req(`/api/conversations`, {
      method: conversation.id ? 'PUT' : 'POST',
      body: JSON.stringify(conversation),
    });
  },

  async delete(id: string): Promise<void> {
    await req(`/api/conversations/${id}`, { method: 'DELETE' });
  },
};
