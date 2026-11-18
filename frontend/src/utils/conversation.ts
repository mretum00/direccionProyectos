import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { uuid } from './uuid';

const NEW_CONVERSATION_TITLE = 'Nueva conversación';

/** Crea una conversación vacía con la versión y el perfil actualmente seleccionados. */
export function buildConversation(selection: EngineSelection): Conversation {
  const now = new Date().toISOString();
  return {
    id: uuid(),
    title: NEW_CONVERSATION_TITLE,
    created_at: now,
    updated_at: now,
    favorite: false,
    engine_version: selection.engine_version,
    profile: selection.profile,
    messages: [],
  };
}

/** Más recientes primero, sin mutar el array original. */
export function sortByUpdated(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}
