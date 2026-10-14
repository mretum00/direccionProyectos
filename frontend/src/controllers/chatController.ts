import type { AssistantResponse, ChatRequest } from '@/types/chat';

export const chatController = {
  async send(_request: ChatRequest): Promise<AssistantResponse> {
    // TODO: POST /api/chat
    throw new Error('chatController.send no implementado');
  },
};
