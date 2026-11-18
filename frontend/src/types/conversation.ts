import type { ChatMessage, Profile } from './chat';

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  favorite: boolean;
  /** Últimos usados: al abrir el chat, el selector se reanuda con ellos. Cada mensaje guarda los suyos. */
  engine_version: string;
  profile: Profile | '';
  messages: ChatMessage[];
  /**
   * Solo en el frontend: chat que aún no existe en el backend (su primera pregunta está en curso o
   * falló). Las conversaciones que devuelve la API nunca lo llevan.
   */
  local?: true;
}
