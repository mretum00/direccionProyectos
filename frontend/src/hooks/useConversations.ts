import { useCallback } from 'react';
import { api } from '@/services/api';
import { useAppStore } from '@/store/appStore';
import { useToast } from '@/toast';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { versionsUsed } from '@/utils/conversation';

interface SearchFilters {
  engine_version?: string;
  favoriteOnly?: boolean;
  dateFrom?: string;
  dateTo?: string;
}

const EMPTY_SELECTION: EngineSelection = { engine_version: '', profile: '' };

/**
 * Acciones sobre las conversaciones del usuario. Los cambios se ven al momento en la
 * interfaz y se guardan en el backend; si el backend los rechaza, se avisa con un toast y se
 * vuelve a cargar la lista desde el servidor para no mostrar datos que no están guardados.
 * La carga inicial se hace una sola vez en <App />.
 */
export function useConversations() {
  const store = useAppStore();
  const toast = useToast();

  const resyncOnError = useCallback(
    (promise: Promise<unknown>) => {
      promise.catch(() => {
        toast.show({
          tone: 'peligro',
          title: 'No se ha podido guardar el cambio',
          description: 'Se ha vuelto a cargar la lista con lo que hay guardado en el servidor.',
        });
        store.reloadConversations().catch(() => undefined);
      });
    },
    [store, toast],
  );

  /** Un chat local (primera pregunta en curso o fallida) no existe en el backend: solo se cambia en local. */
  const isSaved = useCallback(
    (id: string) => store.conversations.some((c) => c.id === id && !c.local),
    [store.conversations],
  );

  /** Aplica el cambio en local y lo envía al backend, que devuelve la conversación guardada. */
  const update = useCallback(
    (id: string, changes: { title?: string; favorite?: boolean }) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (!conv) return;
      store.upsertConversation({ ...conv, ...changes, updated_at: new Date().toISOString() });
      if (!isSaved(id)) return;
      resyncOnError(api.updateConversation(id, changes).then(store.upsertConversation));
    },
    [store, isSaved, resyncOnError],
  );

  /**
   * "Nueva conversación": deja el chat vacío, sin versión ni tipo de usuario (hay que elegirlos).
   * La conversación se crea en el backend al enviar la primera pregunta.
   */
  const createConversation = useCallback(() => {
    store.setActiveConversationId(null);
    store.setEngineSelection(EMPTY_SELECTION);
  }, [store]);

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
    (id: string, title: string) => update(id, { title }),
    [update],
  );

  const toggleFavorite = useCallback(
    (id: string) => {
      const conv = store.conversations.find((c) => c.id === id);
      if (conv) update(id, { favorite: !conv.favorite });
    },
    [store.conversations, update],
  );

  /** Si se borra la conversación abierta, el selector vuelve a quedar vacío (como en un chat nuevo). */
  const deleteConversation = useCallback(
    (id: string) => {
      const saved = isSaved(id);
      const title = store.conversations.find((c) => c.id === id)?.title ?? '';
      store.deleteConversation(id);
      if (store.activeConversationId === id) {
        store.setActiveConversationId(null);
        store.setEngineSelection(EMPTY_SELECTION);
      }
      if (saved) {
        resyncOnError(
          api.deleteConversation(id).then(() =>
            toast.show({
              tone: 'info',
              title: 'Conversación eliminada',
              description: `Se ha borrado «${title}» junto con todos sus mensajes.`,
            }),
          ),
        );
      }
    },
    [store, isSaved, resyncOnError, toast],
  );

  const duplicateConversation = useCallback(
    (id: string) => {
      if (!isSaved(id)) return;
      resyncOnError(
        api.duplicateConversation(id).then((copy) => {
          store.upsertConversation(copy);
          toast.show({
            tone: 'exito',
            title: 'Conversación duplicada',
            description: `Se ha creado «${copy.title}» con todos sus mensajes.`,
          });
        }),
      );
    },
    [store, isSaved, resyncOnError, toast],
  );

  const searchConversations = useCallback(
    (query: string, filters: SearchFilters = {}): Conversation[] => {
      const q = query.toLowerCase().trim();
      return store.conversations.filter((c) => {
        if (filters.favoriteOnly && !c.favorite) return false;
        // Un chat puede haber cambiado de versión: vale si en algún momento se preguntó por ella.
        const versions = versionsUsed(c);
        if (filters.engine_version && !versions.includes(filters.engine_version)) return false;
        if (filters.dateFrom && c.updated_at < filters.dateFrom) return false;
        if (filters.dateTo && c.updated_at > filters.dateTo) return false;
        if (!q) return true;
        return (
          c.title.toLowerCase().includes(q) ||
          versions.some((v) => v.toLowerCase().includes(q)) ||
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
