import { useCallback, useRef, useState } from 'react';
import { config } from '@/config';
import { api } from '@/services/api';
import { conversationRepository } from '@/services/conversationRepository';
import { useAppStore, type AppStore } from '@/store/appStore';
import type { ChatMessage } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import { isSelectionComplete } from '@/types/engine';
import { buildConversation } from '@/utils/conversation';
import { uuid } from '@/utils/uuid';

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
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  /**
   * Envía la pregunta del usuario junto con el motor/versión actualmente
   * seleccionados. `baseConversation` permite reenviar partiendo de un estado
   * distinto al del store (lo usa `retry`, cuyo upsert aún no se ha renderizado).
   */
  const sendMessage = useCallback(async (rawText: string, baseConversation?: Conversation) => {
    const text = rawText.trim();
    const current = storeRef.current;
    const selection = current.engineSelection;
    // Versión y tipo de usuario son obligatorios (ChatWindow no deja enviar sin ellos).
    if (!text || inFlight.current || !isSelectionComplete(selection)) return;

    const conversation = baseConversation ?? findActive(current) ?? buildConversation(selection);

    const now = new Date().toISOString();
    const userMessage: ChatMessage = { id: uuid(), role: 'user', content: text, created_at: now };
    // Los avisos de aclaración (respuestas con needs_clarification) no se envían al modelo: no le aportan nada.
    const history = conversation.messages
      .filter((m) => !m.response?.needs_clarification)
      .slice(-config.chatHistoryLimit)
      .map(({ role, content }) => ({ role, content }));

    const pending: Conversation = {
      ...conversation,
      messages: [...conversation.messages, userMessage],
      updated_at: now,
      engine_version: selection.engine_version,
      profile: selection.profile,
      title: conversation.messages.length === 0 ? text.slice(0, 50) : conversation.title,
    };
    current.setActiveConversationId(pending.id);
    current.upsertConversation(pending);

    const controller = new AbortController();
    inFlight.current = controller;
    setError(null);
    setLoading(true);

    try {
      const { message: answer, ...meta } = await api.chat(
        {
          message: text,
          engine_version: selection.engine_version,
          profile: selection.profile,
          history,
        },
        controller.signal,
      );

      const answeredAt = new Date().toISOString();
      const assistantMessage: ChatMessage = {
        id: answer.id,
        role: 'assistant',
        content: answer.content,
        created_at: answeredAt,
        response: meta,
      };
      const finalConversation: Conversation = {
        ...pending,
        messages: [...pending.messages, assistantMessage],
        updated_at: answeredAt,
      };
      storeRef.current.upsertConversation(finalConversation);
      // Un fallo al guardar no invalida la respuesta ya recibida.
      conversationRepository.save(finalConversation).catch(() => undefined);
    } catch (e) {
      if (controller.signal.aborted) {
        setError('Consulta cancelada');
      } else if (e instanceof TypeError) {
        // Sin conexión con el servidor, `fetch` lanza un TypeError.
        setError('No se ha podido conectar con el servidor');
      } else {
        setError('No se ha podido procesar la consulta');
      }
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setLoading(false);
      }
    }
  }, []);

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
