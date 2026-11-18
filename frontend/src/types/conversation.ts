import type { ChatMessage, Profile } from './chat';

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  favorite: boolean;
  engine_version: string;
  profile: Profile | '';
  messages: ChatMessage[];
}
