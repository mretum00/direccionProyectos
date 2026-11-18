import { useCallback, useEffect, useMemo, useState } from 'react';
import { config } from '@/config';
import { api } from '@/services/api';
import { conversationRepository } from '@/services/conversationRepository';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { sortByUpdated } from '@/utils/conversation';
import { AppStoreContext, type AppStore } from '@/store/appStore';
import { ChatWindow } from '@/components/chat/ChatWindow';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { Header } from '@/components/ui/Header';
import { Sidebar } from '@/components/conversations/ConversationSidebar';

export type Page = 'chat' | 'documents' | 'settings';

export default function App() {
  const [versions, setVersions] = useState<string[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [engineSelection, setEngineSelection] = useState<EngineSelection>({ engine_version: '', profile: '' });
  const [engineSelectorOpen, setSelectorOpen] = useState(false);
  const [engineSelectorPrompted, setSelectorPrompted] = useState(false);
  const [page, setPage] = useState<Page>('chat');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Versiones que admite el backend. Si el .env define una (VITE_DEFAULT_ENGINE_VERSION) y el backend la admite,
  // queda preseleccionada al abrir la app.
  useEffect(() => {
    let active = true;
    api
      .listVersions()
      .then((list) => {
        if (!active) return;
        setVersions(list);
        if (list.includes(config.defaultEngineVersion)) {
          setEngineSelection((prev) =>
            prev.engine_version ? prev : { ...prev, engine_version: config.defaultEngineVersion },
          );
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  // Carga única de las conversaciones guardadas (antes se repetía en cada ítem de la lista).
  useEffect(() => {
    let active = true;
    conversationRepository
      .list()
      .then((stored) => {
        if (!active) return;
        setConversations((prev) => {
          const known = new Set(prev.map((c) => c.id));
          return sortByUpdated([...prev, ...stored.filter((c) => !known.has(c.id))]);
        });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

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
    }),
    [versions, conversations, activeConversationId, engineSelection, engineSelectorOpen, engineSelectorPrompted, setEngineSelectorOpen, upsertConversation, deleteConversation],
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
            <div className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
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
            {page === 'settings' && <SettingsPage />}
          </div>
        </div>
      </div>
    </AppStoreContext.Provider>
  );
}
