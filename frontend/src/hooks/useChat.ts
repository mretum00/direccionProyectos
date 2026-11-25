import { useCallback, useRef, useState } from 'react';
import { api, ApiError } from '@/services/api';
import { useAppStore, type AppStore } from '@/store/appStore';
import { useToast } from '@/useToast';
import type { ChatMessage } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import { isSelectionComplete, type EngineSelection } from '@/types/engine';
import { buildConversation, conversationTitle } from '@/utils/conversation';
import { uuid } from '@/utils/uuid';

function findConversation(store: AppStore, id: string | null): Conversation | null {
  if (!id) return null;
  return store.conversations.find((c) => c.id === id) ?? null;
}

/** Error de la última consulta: pertenece a una conversación y solo se muestra en ella. */
export interface ChatFailure {
  conversationId: string;
  message: string;
}

/**
 * Lógica del chat. Debe instanciarse UNA sola vez por pantalla (ChatWindow): el estado de la
 * consulta en curso y del último error es local del hook y no se comparte entre instancias.
 */
export function useChat() {
  const store = useAppStore();
  const toast = useToast();
  // Siempre apunta al store más reciente: los callbacks no se recrean en cada cambio.
  const storeRef = useRef(store);
  storeRef.current = store;

  /** Conversación cuya pregunta se está consultando (solo puede haber una a la vez). */
  const [busyConversationId, setBusyConversationId] = useState<string | null>(null);
  const [failure, setFailure] = useState<ChatFailure | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  /**
   * Añade `question` a `base`, la muestra al momento y la envía. El backend guarda pregunta y
   * respuesta juntas y devuelve la conversación guardada, que sustituye a la local.
   */
  const ask = useCallback(async (base: Conversation, question: ChatMessage, selection: EngineSelection) => {
    if (inFlight.current || !isSelectionComplete(selection)) return;
    const current = storeRef.current;

    const pending: Conversation = {
      ...base,
      messages: [...base.messages, question],
      updated_at: question.created_at ?? new Date().toISOString(),
      engine_version: selection.engine_version,
      profile: selection.profile,
      title: base.local && base.messages.length === 0 ? conversationTitle(question.content) : base.title,
    };
    current.setActiveConversationId(pending.id);
    current.upsertConversation(pending);

    const controller = new AbortController();
    inFlight.current = controller;
    setFailure(null);
    setBusyConversationId(pending.id);

    try {
      const { conversation: saved } = await api.chat(
        {
          conversation_id: pending.id,
          message_id: question.id,
          message: question.content,
          engine_version: selection.engine_version,
          profile: selection.profile,
        },
        controller.signal,
      );
      if (findConversation(storeRef.current, saved.id)) {
        storeRef.current.upsertConversation(saved);
      } else {
        // Se borró mientras se esperaba la respuesta: el backend la acaba de guardar, se borra allí también.
        void api.deleteConversation(saved.id).catch(() => undefined);
      }
    } catch (e) {
      if (controller.signal.aborted) {
        // Cancelada: la pregunta desaparece del chat y el backend no la guarda (ni la deja guardada).
        void api.cancelChat(question.id).catch(() => storeRef.current.reloadConversations().catch(() => undefined));
        const now = storeRef.current;
        if (base.local && base.messages.length === 0) {
          now.deleteConversation(base.id);
          if (now.activeConversationId === base.id) now.setActiveConversationId(null);
        } else {
          now.upsertConversation(base);
        }
        toast.show({
          tone: 'info',
          title: 'Consulta cancelada',
          description: 'La pregunta no se ha guardado en la conversación.',
        });
        return;
      }
      let message = 'No se ha podido procesar la consulta';
      if (e instanceof TypeError) {
        // Sin conexión con el backend, `fetch` suele lanzar un TypeError.
        message = 'No se ha podido conectar con el servidor';
      } else if (e instanceof ApiError) {
        // El backend devuelve mensajes seguros y específicos para errores del proveedor IA.
        if ([429, 502, 503].includes(e.status)) {
          message = e.message;
        } else if (e.status >= 500) {
          message = 'Se ha producido un error interno. Inténtalo de nuevo.';
        } else {
          message = e.message;
        }
      }
      setFailure({ conversationId: pending.id, message });
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setBusyConversationId(null);
      }
    }
  }, [toast]);

  /** Envía una pregunta nueva con la versión y el perfil seleccionados en la conversación abierta. */
  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      const current = storeRef.current;
      const selection = current.engineSelection;
      // Versión y tipo de usuario son obligatorios (ChatWindow no deja enviar sin ellos).
      if (!text || !isSelectionComplete(selection)) return;

      const conversation = findConversation(current, current.activeConversationId) ?? buildConversation(selection);
      const question: ChatMessage = {
        id: uuid(),
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
        engine_version: selection.engine_version,
        profile: selection.profile,
      };
      await ask(conversation, question, selection);
    },
    [ask],
  );

  /**
   * Reenvía la pregunta que falló (error del servidor o sin conexión), con su mismo id y la versión y
   * el perfil con los que se hizo: si el backend llegó a responderla, devuelve lo guardado sin duplicarla.
   */
  const retry = useCallback(() => {
    if (!failure) return;
    const conversation = findConversation(storeRef.current, failure.conversationId);
    const question = conversation?.messages[conversation.messages.length - 1];
    if (!conversation || question?.role !== 'user') {
      setFailure(null);
      return;
    }
    const original = { engine_version: question.engine_version ?? '', profile: question.profile ?? '' };
    const selection = isSelectionComplete(original) ? original : storeRef.current.engineSelection;
    void ask({ ...conversation, messages: conversation.messages.slice(0, -1) }, question, selection);
  }, [ask, failure]);

  /** Cancela la pregunta en curso: se quita del chat y el backend no la guarda. */
  const cancel = useCallback(() => {
    inFlight.current?.abort();
  }, []);

  return { busyConversationId, failure, sendMessage, retry, cancel };
}
