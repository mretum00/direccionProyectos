import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { uuid } from './uuid';

export const NEW_CONVERSATION_TITLE = 'Nueva conversación';

/** Crea una conversación vacía con el motor/versión/perfil actualmente seleccionados. */
export function buildConversation(selection: EngineSelection): Conversation {
  const now = new Date().toISOString();
  return {
    id: uuid(),
    title: NEW_CONVERSATION_TITLE,
    created_at: now,
    updated_at: now,
    favorite: false,
    engine: selection.engine,
    engine_version: selection.engine_version,
    system: selection.system,
    profile: selection.profile,
    messages: [],
  };
}

/** Más recientes primero, sin mutar el array original. */
export function sortByUpdated(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}
