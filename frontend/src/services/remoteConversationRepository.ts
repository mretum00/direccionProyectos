import type { ConversationRepository } from '@/types/contract';
import { conversationsController } from '@/controllers';

export const remoteConversationRepository: ConversationRepository = {
  list: () => conversationsController.list(),
  get: (id) => conversationsController.get(id),
  save: (conversation) => conversationsController.save(conversation),
  delete: (id) => conversationsController.remove(id),
};
