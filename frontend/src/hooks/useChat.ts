import { useCallback, useRef, useState } from 'react';
import { api } from '@/services/api';
import { conversationRepository } from '@/services/conversationRepository';
import { useAppStore } from '@/store/appStore';
import type { AssistantResponse, ChatMessage } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import { uuid } from '@/services/mockData';

type ChatError = { type: 'network' | 'server' | 'unknown'; message: string } | null;

export function useChat() {
  const store = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ChatError>(null);
  const abortRef = useRef(false);

  const getActive = useCallback((): Conversation | null => {
    if (!store.activeConversationId) return null;
    return store.conversations.find((c) => c.id === store.activeConversationId) ?? null;
  }, [store.activeConversationId, store.conversations]);

  const ensureConversation = useCallback((): Conversation => {
    let conv = getActive();
    if (conv) return conv;
    const now = new Date().toISOString();
    conv = {
      id: uuid(),
      title: 'Nueva conversación',
      created_at: now,
      updated_at: now,
      favorite: false,
      engine: store.engineSelection.engine,
      engine_version: store.engineSelection.engine_version,
      system: store.engineSelection.system,
      profile: store.engineSelection.profile,
      messages: [],
    };
    store.upsertConversation(conv);
    store.setActiveConversationId(conv.id);
    return conv;
  }, [getActive, store]);

  const sendMessage = useCallback(
    async (text: string, clarificationAnswers?: Record<string, string>) => {
      if (!text.trim()) return;
      setError(null);
      setLoading(true);
      abortRef.current = false;

      const conv = ensureConversation();
      const userMsg: ChatMessage = {
        id: uuid(),
        role: 'user',
        content: clarificationAnswers ? `${text}` : text,
        created_at: new Date().toISOString(),
      };

      const updatedMessages = [...conv.messages, userMsg];
      const updatedConv: Conversation = {
        ...conv,
        messages: updatedMessages,
        updated_at: new Date().toISOString(),
        engine: store.engineSelection.engine,
        engine_version: store.engineSelection.engine_version,
        system: store.engineSelection.system,
        profile: store.engineSelection.profile,
        title: conv.messages.length === 0 ? text.slice(0, 50) : conv.title,
      };
      store.upsertConversation(updatedConv);

      try {
        const response = await api.chat({
          conversation_id: updatedConv.id,
          message: text,
          engine: store.engineSelection.engine,
          engine_version: store.engineSelection.engine_version,
          system: store.engineSelection.system,
          profile: store.engineSelection.profile,
          history: updatedMessages.slice(-7).map((m) => ({ role: m.role, content: m.content })),
          vehicle: {
            brand: store.engineSelection.vehicle.brand,
            model: store.engineSelection.vehicle.model,
            year: store.engineSelection.vehicle.year,
            vin: store.engineSelection.vehicle.vin,
          },
        });

        if (abortRef.current) return;

        const assistantMsg: ChatMessage = {
          id: response.message.id,
          role: 'assistant',
          content: response.message.content,
          created_at: new Date().toISOString(),
          response,
        };

        const finalConv: Conversation = {
          ...updatedConv,
          messages: [...updatedMessages, assistantMsg],
          updated_at: new Date().toISOString(),
        };
        store.upsertConversation(finalConv);
        await conversationRepository.save(finalConv);
      } catch (e) {
        if (abortRef.current) return;
        if (e instanceof TypeError) {
          setError({ type: 'network', message: 'No se ha podido conectar con el servidor' });
        } else {
          setError({ type: 'server', message: 'No se ha podido procesar la consulta' });
        }
      } finally {
        setLoading(false);
      }
    },
    [ensureConversation, store],
  );

  const retry = useCallback(() => {
    const conv = getActive();
    if (!conv || conv.messages.length === 0) return;
    const lastUser = [...conv.messages].reverse().find((m) => m.role === 'user');
    if (!lastUser) return;
    // Remove last user message and resend
    const trimmed = conv.messages.slice(0, conv.messages.lastIndexOf(lastUser));
    const trimmedConv = { ...conv, messages: trimmed };
    store.upsertConversation(trimmedConv);
    sendMessage(lastUser.content);
  }, [getActive, sendMessage, store]);

  const cancel = useCallback(() => {
    abortRef.current = true;
    setLoading(false);
  }, []);

  return { loading, error, sendMessage, retry, cancel };
}
