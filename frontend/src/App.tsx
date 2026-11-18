import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/services/api';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { sortByUpdated } from '@/utils/conversation';
import { AppStoreContext, type AppStore } from '@/store/appStore';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { SystemInfoPage } from '@/pages/SystemInfoPage';
import { Header } from '@/components/ui/Header';
import { useToast } from '@/toast';
import { Sidebar } from '@/components/conversations/ConversationSidebar';

export type Page = 'chat' | 'documents' | 'system';

export default function App() {
  const toast = useToast();
  const [versions, setVersions] = useState<string[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [engineSelection, setEngineSelection] = useState<EngineSelection>({ engine_version: '', profile: '' });
  const [engineSelectorOpen, setSelectorOpen] = useState(false);
  const [engineSelectorPrompted, setSelectorPrompted] = useState(false);
  const [page, setPage] = useState<Page>('chat');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Versiones que admite el backend. Ninguna queda preseleccionada: el usuario elige versión y tipo de usuario
  // en cada chat nuevo (al abrir un chat guardado, el selector recupera los últimos que se usaron en él).
  useEffect(() => {
    let active = true;
    api
      .listVersions()
      .then((list) => {
        if (active) setVersions(list);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  /** Carga del backend los chats del usuario (al entrar y si una operación sobre ellos falla). */
  const reloadConversations = useCallback(async () => {
    const stored = await api.listConversations();
    setConversations((prev) => {
      // Se conservan los chats que aún no están guardados (primera pregunta en curso o fallida).
      const known = new Set(stored.map((c) => c.id));
      return sortByUpdated([...stored, ...prev.filter((c) => c.local && !known.has(c.id) && c.messages.length > 0)]);
    });
  }, []);

  useEffect(() => {
    reloadConversations().catch(() =>
      toast.show({
        tone: 'peligro',
        title: 'No se han podido cargar tus conversaciones',
        description: 'Comprueba que el backend está en marcha y recarga la página.',
      }),
    );
  }, [reloadConversations, toast]);

  const setEngineSelectorOpen = useCallback((open: boolean, prompted = false) => {
    setSelectorOpen(open);
    setSelectorPrompted(open && prompted);
  }, []);

  const upsertConversation = useCallback((c: Conversation) => {
    setConversations((prev) => sortByUpdated([c, ...prev.filter((x) => x.id !== c.id)]));
  }, []);

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, []);

  // Sin useMemo el valor del contexto era un objeto nuevo en cada render y
  // forzaba el re-render de todos los consumidores (abrir el menú móvil, cambiar de página...).
  const store: AppStore = useMemo(
    () => ({
      versions,
      conversations,
      activeConversationId,
      engineSelection,
      engineSelectorOpen,
      engineSelectorPrompted,
      setActiveConversationId,
      setEngineSelection,
      setEngineSelectorOpen,
      upsertConversation,
      deleteConversation,
      reloadConversations,
    }),
    [versions, conversations, activeConversationId, engineSelection, engineSelectorOpen, engineSelectorPrompted, setEngineSelectorOpen, upsertConversation, deleteConversation, reloadConversations],
  );

  return (
    <AppStoreContext.Provider value={store}>
      <div className="flex h-screen bg-fondo text-texto-100 overflow-hidden">
        {/* Sidebar - desktop */}
        <div className="hidden lg:flex w-72 flex-shrink-0">
          <Sidebar onNavigate={() => setPage('chat')} />
        </div>

        {/* Sidebar - mobile drawer */}
        {sidebarOpen && (
          <>
            <div className="capa-fondo z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
            <div className="fixed left-0 top-0 bottom-0 w-72 z-50 lg:hidden">
              <Sidebar onNavigate={() => { setPage('chat'); setSidebarOpen(false); }} />
            </div>
          </>
        )}

        {/* Main */}
        <div className="flex-1 flex flex-col min-w-0">
          <Header
            page={page}
            onPageChange={setPage}
            onMenuClick={() => setSidebarOpen(true)}
          />
          <div className="flex-1 overflow-hidden">
            {page === 'chat' && <ChatWindow />}
            {page === 'documents' && <DocumentsPage />}
            {page === 'system' && <SystemInfoPage />}
          </div>
        </div>
      </div>
    </AppStoreContext.Provider>
  );
}
