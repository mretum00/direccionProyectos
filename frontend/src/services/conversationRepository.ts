import { config } from '@/config';
import type { ConversationRepository } from '@/types/contract';
import { localConversationRepository } from './localConversationRepository';
import { remoteConversationRepository } from './remoteConversationRepository';

export const conversationRepository: ConversationRepository = config.remoteConversations
  ? remoteConversationRepository
  : localConversationRepository;
