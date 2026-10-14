import type { Conversation } from '@/types/conversation';

export const conversationsController = {
  async list(): Promise<Conversation[]> {
    // TODO: GET /api/conversations
    throw new Error('conversationsController.list no implementado');
  },

  async get(_id: string): Promise<Conversation | null> {
    // TODO: GET /api/conversations/{id}
    throw new Error('conversationsController.get no implementado');
  },

  async create(_conversation: Conversation): Promise<Conversation> {
    // TODO: POST /api/conversations
    throw new Error('conversationsController.create no implementado');
  },

  async update(_conversation: Conversation): Promise<void> {
    // TODO: PUT /api/conversations
    throw new Error('conversationsController.update no implementado');
  },

  async remove(_id: string): Promise<void> {
    // TODO: DELETE /api/conversations/{id}
    throw new Error('conversationsController.remove no implementado');
  },
};
