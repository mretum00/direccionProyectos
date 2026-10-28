import type { ChatMessage, EngineSystem, Profile } from './chat';

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  favorite: boolean;
  engine: string;
  engine_version: string;
  system: EngineSystem;
  profile: Profile;
  messages: ChatMessage[];
}
