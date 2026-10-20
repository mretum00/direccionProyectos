import { useCallback } from 'react';
import { conversationRepository } from '@/services/conversationRepository';
import { useAppStore } from '@/store/appStore';
import type { Conversation } from '@/types/conversation';
import { buildConversation } from '@/utils/conversation';
import { uuid } from '@/utils/uuid';

/** Acciones sobre conversaciones. La carga inicial se hace una sola vez en <App />. */
export function useConversations() {
  const store = useAppStore();
  const createConversation = useCallback((): Conversation => {
    const conv = buildConversation(store.engineSelection);
    store.upsertConversation(conv);
    store.setActiveConversationId(conv.id);
    conversationRepository.save(conv).catch(() => {});
    return conv;
  }, [store]);

  const selectConversation = useCallback(
    (id: string) => {
      store.setActiveConversationId(id);
    },
    [store],
  );

  const renameConversation = useCallback(
    (id: string, title: string) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (!conv) return;
      const updated = { ...conv, title, updated_at: new Date().toISOString() };
      store.upsertConversation(updated);
      conversationRepository.save(updated).catch(() => {});
    },
    [store],
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      store.deleteConversation(id);
      if (store.activeConversationId === id) store.setActiveConversationId(null);
      try {
        await conversationRepository.delete(id);
      } catch {
        // notify silently
      }
    },
    [store],
  );

  const duplicateConversation = useCallback(
    (id: string) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (!conv) return;
      const now = new Date().toISOString();
      const copy: Conversation = {
        ...conv,
        id: uuid(),
        title: `${conv.title} (copia)`,
        created_at: now,
        updated_at: now,
        favorite: false,
      };
      store.upsertConversation(copy);
      conversationRepository.save(copy).catch(() => {});
    },
    [store],
  );

  const toggleFavorite = useCallback(
    (id: string) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (!conv) return;
      const updated = { ...conv, favorite: !conv.favorite, updated_at: new Date().toISOString() };
      store.upsertConversation(updated);
      conversationRepository.save(updated).catch(() => {});
    },
    [store],
  );

  const searchConversations = useCallback(
    (query: string, filters?: { engine_version?: string; favoriteOnly?: boolean; dateFrom?: string; dateTo?: string }): Conversation[] => {
      const q = query.toLowerCase().trim();
      return store.conversations.filter((c) => {
        if (filters?.favoriteOnly && !c.favorite) return false;
        if (filters?.engine_version && c.engine_version !== filters.engine_version) return false;
        if (filters?.dateFrom && c.updated_at < filters.dateFrom) return false;
        if (filters?.dateTo && c.updated_at > filters.dateTo) return false;
        if (!q) return true;
        if (c.title.toLowerCase().includes(q)) return true;
        if (c.engine.toLowerCase().includes(q)) return true;
        if (c.engine_version.toLowerCase().includes(q)) return true;
        return c.messages.some((m) => m.content.toLowerCase().includes(q));
      });
    },
    [store.conversations],
  );

  return {
    createConversation,
    selectConversation,
    renameConversation,
    deleteConversation,
    duplicateConversation,
    toggleFavorite,
    searchConversations,
  };
}
