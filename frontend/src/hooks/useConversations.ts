import { useCallback } from 'react';
import { conversationRepository } from '@/services/conversationRepository';
import { useAppStore } from '@/store/appStore';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { buildConversation } from '@/utils/conversation';
import { uuid } from '@/utils/uuid';

interface SearchFilters {
  engine_version?: string;
  favoriteOnly?: boolean;
  dateFrom?: string;
  dateTo?: string;
}

/** Acciones sobre conversaciones. La carga inicial se hace una sola vez en <App />. */
export function useConversations() {
  const store = useAppStore();

  /** Actualiza el store y guarda la conversación. Un fallo al guardar se ignora: sigue en memoria. */
  const persist = useCallback(
    (conversation: Conversation) => {
      store.upsertConversation(conversation);
      conversationRepository.save(conversation).catch(() => undefined);
    },
    [store],
  );

  /** Aplica `change` a una conversación existente y la marca como modificada ahora. */
  const update = useCallback(
    (id: string, change: (conv: Conversation) => Partial<Conversation>) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (!conv) return;
      persist({ ...conv, ...change(conv), updated_at: new Date().toISOString() });
    },
    [store.conversations, persist],
  );

  /** Cada chat nuevo empieza sin versión ni tipo de usuario: hay que elegirlos de nuevo. */
  const createConversation = useCallback(() => {
    const selection: EngineSelection = { engine_version: '', profile: '' };
    const conv = buildConversation(selection);
    persist(conv);
    store.setActiveConversationId(conv.id);
    store.setEngineSelection(selection);
  }, [store, persist]);

  /** Al abrir una conversación, el selector recupera su versión y tipo de usuario. */
  const selectConversation = useCallback(
    (id: string) => {
      const conv = store.conversations.find((c) => c.id === id);
      store.setActiveConversationId(id);
      if (conv) {
        store.setEngineSelection({ engine_version: conv.engine_version, profile: conv.profile });
      }
    },
    [store],
  );

  const renameConversation = useCallback(
    (id: string, title: string) => update(id, () => ({ title })),
    [update],
  );

  const toggleFavorite = useCallback(
    (id: string) => update(id, (conv) => ({ favorite: !conv.favorite })),
    [update],
  );

  const deleteConversation = useCallback(
    (id: string) => {
      store.deleteConversation(id);
      if (store.activeConversationId === id) store.setActiveConversationId(null);
      conversationRepository.delete(id).catch(() => undefined);
    },
    [store],
  );

  const duplicateConversation = useCallback(
    (id: string) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (!conv) return;
      const now = new Date().toISOString();
      persist({
        ...conv,
        id: uuid(),
        title: `${conv.title} (copia)`,
        created_at: now,
        updated_at: now,
        favorite: false,
      });
    },
    [store.conversations, persist],
  );

  const searchConversations = useCallback(
    (query: string, filters: SearchFilters = {}): Conversation[] => {
      const q = query.toLowerCase().trim();
      return store.conversations.filter((c) => {
        if (filters.favoriteOnly && !c.favorite) return false;
        if (filters.engine_version && c.engine_version !== filters.engine_version) return false;
        if (filters.dateFrom && c.updated_at < filters.dateFrom) return false;
        if (filters.dateTo && c.updated_at > filters.dateTo) return false;
        if (!q) return true;
        return (
          c.title.toLowerCase().includes(q) ||
          c.engine_version.toLowerCase().includes(q) ||
          c.messages.some((m) => m.content.toLowerCase().includes(q))
        );
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
