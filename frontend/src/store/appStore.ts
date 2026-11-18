import { createContext, useContext } from 'react';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';

interface AppState {
  /** Versiones que admite el backend (GET /api/versions); vacío hasta que cargan. */
  versions: string[];
  conversations: Conversation[];
  activeConversationId: string | null;
  engineSelection: EngineSelection;
  /** Panel del selector de motor (cabecera): lo abre también el chat cuando falta la versión. */
  engineSelectorOpen: boolean;
  /** true si se abrió porque se intentó consultar sin configurar: el panel lo explica. */
  engineSelectorPrompted: boolean;
}

export interface AppStore extends AppState {
  setActiveConversationId: (id: string | null) => void;
  setEngineSelection: (s: EngineSelection) => void;
  setEngineSelectorOpen: (open: boolean, prompted?: boolean) => void;
  upsertConversation: (c: Conversation) => void;
  deleteConversation: (id: string) => void;
}

export const AppStoreContext = createContext<AppStore | null>(null);

export function useAppStore(): AppStore {
  const ctx = useContext(AppStoreContext);
  if (!ctx) throw new Error('useAppStore must be used within AppStoreProvider');
  return ctx;
}
