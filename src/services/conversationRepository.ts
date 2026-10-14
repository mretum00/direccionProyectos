import type { ConversationRepository } from '@/types/contract';
import { localConversationRepository } from './localConversationRepository';
import { remoteConversationRepository } from './remoteConversationRepository';

const REMOTE = import.meta.env.VITE_REMOTE_CONVERSATIONS === 'true';

export const conversationRepository: ConversationRepository = REMOTE
  ? remoteConversationRepository
  : localConversationRepository;
