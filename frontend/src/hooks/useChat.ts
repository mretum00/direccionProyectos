import { useCallback, useEffect, useRef, useState } from 'react';
import { config } from '@/config';
import { api } from '@/services/api';
import { conversationRepository } from '@/services/conversationRepository';
import { useAppStore, type AppStore } from '@/store/appStore';
import type { ChatMessage } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import { isComplete, PROFILES, ENGINES, type CompleteSelection } from '@/types/engine';
import { buildConversation } from '@/utils/conversation';
import { uuid } from '@/utils/uuid';

export type ChatError = { type: 'network' | 'server' | 'cancelled' | 'selection'; message: string } | null;

function findActive(store: AppStore): Conversation | null {
  if (!store.activeConversationId) return null;
  return store.conversations.find((c) => c.id === store.activeConversationId) ?? null;
}

/**
 * Lógica del chat. Debe instanciarse UNA sola vez por pantalla (ChatWindow):
 * `loading` y `error` son estado local del hook y no se comparten entre instancias.
 */
export function useChat() {
  const store = useAppStore();
  // Siempre apunta al store más reciente: los callbacks no se recrean en cada cambio.
  const storeRef = useRef(store);
  storeRef.current = store;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ChatError>(null);
  const inFlight = useRef<AbortController | null>(null);

  // Al cambiar de chat (o crear uno nuevo) se descarta el aviso del chat anterior.
  const activeConversationId = store.activeConversationId;
  useEffect(() => {
    setError(null);
  }, [activeConversationId]);

  // El aviso de selección desaparece en cuanto el usuario elige la versión y el perfil.
  const selectionComplete = isComplete(store.engineSelection);
  useEffect(() => {
    if (selectionComplete) setError((e) => (e?.type === 'selection' ? null : e));
  }, [selectionComplete]);

  const performSend = useCallback(async (text: string, selection: CompleteSelection, baseConversation?: Conversation) => {
    const current = storeRef.current;
    const conversation = baseConversation ?? findActive(current) ?? buildConversation(selection);

    const now = new Date().toISOString();
    const userMessage: ChatMessage = { id: uuid(), role: 'user', content: text, created_at: now };
    const history = conversation.messages
      .slice(-config.chatHistoryLimit)
      .map(({ role, content }) => ({ role, content }));

    const pending: Conversation = {
      ...conversation,
      messages: [...conversation.messages, userMessage],
      updated_at: now,
      engine: selection.engine,
      engine_version: selection.engine_version,
      system: selection.system,
      profile: selection.profile,
      title: conversation.messages.length === 0 ? text.slice(0, 50) : conversation.title,
    };
    current.upsertConversation(pending);
    current.setActiveConversationId(pending.id);

    const controller = new AbortController();
    inFlight.current = controller;
    setError(null);
    setLoading(true);

    try {
      const response = await api.chat(
        {
          conversation_id: pending.id,
          message: text,
          engine: selection.engine,
          engine_version: selection.engine_version,
          system: selection.system,
          profile: selection.profile,
          history,
          vehicle: { ...selection.vehicle },
        },
        controller.signal,
      );

      const assistantMessage: ChatMessage = {
        id: response.message.id,
        role: 'assistant',
        content: response.message.content,
        created_at: new Date().toISOString(),
        response,
      };
      const finalConversation: Conversation = {
        ...pending,
        messages: [...pending.messages, assistantMessage],
        updated_at: assistantMessage.created_at ?? now,
      };
      storeRef.current.upsertConversation(finalConversation);
      // Un fallo al guardar no invalida la respuesta ya recibida.
      conversationRepository.save(finalConversation).catch(() => undefined);
    } catch (e) {
      if (controller.signal.aborted) {
        setError({ type: 'cancelled', message: 'Consulta cancelada' });
      } else if (e instanceof TypeError) {
        setError({ type: 'network', message: 'No se ha podido conectar con el servidor' });
      } else {
        setError({ type: 'server', message: 'No se ha podido procesar la consulta' });
      }
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setLoading(false);
      }
    }
  }, []);

  /**
   * Envía la pregunta del usuario junto con el motor, la versión y el perfil
   * actualmente seleccionados. Sin versión o sin perfil no se envía nada: se
   * muestra un error que indica qué falta y qué opciones hay. Devuelve `true` si la consulta salió, para que el input
   * sepa si debe vaciarse. `baseConversation` permite reenviar partiendo de un
   * estado distinto al del store (lo usa `retry`, cuyo upsert aún no se ha renderizado).
   */
  const sendMessage = useCallback(
    (rawText: string, baseConversation?: Conversation): boolean => {
      const text = rawText.trim();
      if (!text || inFlight.current) return false;

      const selection = storeRef.current.engineSelection;
      if (!isComplete(selection)) {
        const faltan: string[] = [];
        if (!selection.engine_version) {
          const versions = ENGINES.find((e) => e.name === selection.engine)?.versions ?? [];
          const options = versions.map((v) => v.label).join(', ');
          faltan.push(`la versión del motor${options ? ` (${options})` : ''}`);
        }
        if (!selection.profile) {
          faltan.push(`el perfil de respuesta (${PROFILES.map((p) => p.label).join(' o ')})`);
        }
        storeRef.current.requestSelection();
        setError({
          type: 'selection',
          message: `Falta elegir ${faltan.join(' y ')}. Complétalo en el selector de arriba a la derecha.`,
        });
        return false;
      }

      void performSend(text, selection, baseConversation);
      return true;
    },
    [performSend],
  );

  /** Reenvía la última pregunta del usuario sin duplicarla en la conversación. */
  const retry = useCallback(() => {
    const conversation = findActive(storeRef.current);
    if (!conversation) return;
    let lastUserIndex = -1;
    for (let i = conversation.messages.length - 1; i >= 0; i--) {
      if (conversation.messages[i].role === 'user') {
        lastUserIndex = i;
        break;
      }
    }
    if (lastUserIndex < 0) return;
    const withoutLastQuestion: Conversation = {
      ...conversation,
      messages: conversation.messages.slice(0, lastUserIndex),
    };
    void sendMessage(conversation.messages[lastUserIndex].content, withoutLastQuestion);
  }, [sendMessage]);

  /** Cancela la petición en curso (aborta el fetch de verdad). */
  const cancel = useCallback(() => {
    inFlight.current?.abort();
  }, []);

  return { loading, error, sendMessage, retry, cancel };
}
