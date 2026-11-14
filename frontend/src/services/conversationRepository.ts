import { config } from '@/config';
import type { Conversation } from '@/types/conversation';
import { api } from './api';

/**
 * Dónde se guardan las conversaciones:
 * - VITE_REMOTE_CONVERSATIONS=true  -> en el backend (api.ts)
 * - en cualquier otro caso          -> en el localStorage del navegador
 */
const STORAGE_KEY = 'arsoft_conversations';

function readLocal(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as Conversation[];
  } catch {
    return [];
  }
}

function writeLocal(conversations: Conversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch {
    // Sin espacio o localStorage bloqueado: la conversación solo vive en memoria.
  }
}

export const conversationRepository = {
  async list(): Promise<Conversation[]> {
    return config.remoteConversations ? api.listConversations() : readLocal();
  },

  async save(conversation: Conversation): Promise<void> {
    if (config.remoteConversations) return api.saveConversation(conversation);
    const others = readLocal().filter((c) => c.id !== conversation.id);
    writeLocal([...others, conversation]);
  },

  async delete(id: string): Promise<void> {
    if (config.remoteConversations) return api.deleteConversation(id);
    writeLocal(readLocal().filter((c) => c.id !== id));
  },
};
