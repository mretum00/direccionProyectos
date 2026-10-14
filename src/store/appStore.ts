import { createContext, useContext } from 'react';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';

export interface AppState {
  conversations: Conversation[];
  activeConversationId: string | null;
  engineSelection: EngineSelection;
}

export interface AppStore extends AppState {
  setConversations: (c: Conversation[]) => void;
  setActiveConversationId: (id: string | null) => void;
  setEngineSelection: (s: EngineSelection) => void;
  upsertConversation: (c: Conversation) => void;
  deleteConversation: (id: string) => void;
}

export const AppStoreContext = createContext<AppStore | null>(null);

export function useAppStore(): AppStore {
  const ctx = useContext(AppStoreContext);
  if (!ctx) throw new Error('useAppStore must be used within AppStoreProvider');
  return ctx;
}
