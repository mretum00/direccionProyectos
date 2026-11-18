import type { ChatMessage } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { uuid } from './uuid';

const NEW_CONVERSATION_TITLE = 'Nueva conversación';

/** Título provisional de un chat nuevo: el principio de su primera pregunta (el backend usa el mismo). */
export function conversationTitle(firstQuestion: string): string {
  return firstQuestion.slice(0, 50);
}

/**
 * Crea una conversación vacía con la versión y el perfil actualmente seleccionados.
 * Es local hasta que el backend la guarde con su primera pregunta.
 */
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
    local: true,
  };
}

/** Versiones por las que se ha preguntado en el chat, en orden de uso y sin repetir. */
export function versionsUsed(conversation: Conversation): string[] {
  const versions = conversation.messages
    .filter((m) => m.role === 'user' && m.engine_version)
    .map((m) => m.engine_version as string);
  if (versions.length === 0 && conversation.engine_version) versions.push(conversation.engine_version);
  return [...new Set(versions)];
}

/** Más recientes primero, sin mutar el array original. */
export function sortByUpdated(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

/** Índice de la pregunta anterior a `index` (o -1 si es la primera). */
function previousQuestion(messages: ChatMessage[], index: number): number {
  for (let i = index - 1; i >= 0; i--) {
    if (messages[i].role === 'user') return i;
  }
  return -1;
}

export function isFirstQuestion(messages: ChatMessage[], index: number): boolean {
  return previousQuestion(messages, index) === -1;
}

/**
 * La versión y el perfil se pueden cambiar a mitad del chat: se marca cada pregunta que
 * empieza a usar una selección distinta de la anterior (y la primera, para saber con cuál empezó).
 */
export function startsNewSelection(messages: ChatMessage[], index: number): boolean {
  const message = messages[index];
  if (message.role !== 'user' || !message.engine_version) return false;
  const prev = previousQuestion(messages, index);
  if (prev === -1) return true;
  return messages[prev].engine_version !== message.engine_version || messages[prev].profile !== message.profile;
}
