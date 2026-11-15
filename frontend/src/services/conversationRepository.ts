import type { Conversation } from '@/types/conversation';

/**
 * Las conversaciones se guardan en el localStorage del navegador (no en el backend):
 * solo las ve quien usa ese navegador.
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
    return readLocal();
  },

  async save(conversation: Conversation): Promise<void> {
    const others = readLocal().filter((c) => c.id !== conversation.id);
    writeLocal([...others, conversation]);
  },

  async delete(id: string): Promise<void> {
    writeLocal(readLocal().filter((c) => c.id !== id));
  },
};
