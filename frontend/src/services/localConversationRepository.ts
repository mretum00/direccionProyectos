import type { ConversationRepository } from '@/types/contract';
import type { Conversation } from '@/types/conversation';

const STORAGE_KEY = 'arsoft_conversations';

function read(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as Conversation[];
  } catch {
    return [];
  }
}

function write(data: Conversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // degrade silently
  }
}

export const localConversationRepository: ConversationRepository = {
  async list(): Promise<Conversation[]> {
    return read().sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  },

  async get(id: string): Promise<Conversation | null> {
    return read().find((c) => c.id === id) ?? null;
  },

  async save(conversation: Conversation): Promise<void> {
    const all = read();
    const idx = all.findIndex((c) => c.id === conversation.id);
    if (idx >= 0) all[idx] = conversation;
    else all.push(conversation);
    write(all);
  },

  async delete(id: string): Promise<void> {
    write(read().filter((c) => c.id !== id));
  },
};
