import { useCallback, useState } from 'react';
import type { Conversation } from '@/types/conversation';
import type { EngineSelection } from '@/types/engine';
import { AppStoreContext, type AppStore } from '@/store/appStore';
import { ChatPage } from '@/pages/ChatPage';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { Header } from '@/components/ui/Header';
import { Sidebar } from '@/components/conversations/ConversationSidebar';

const DEFAULT_SELECTION: EngineSelection = {
  engine: 'ThermoDrive HTM-240',
  engine_version: 'V2.0',
  system: null,
  profile: 'mechanic',
  vehicle: { brand: '', model: '', year: null, vin: '' },
};

export type Page = 'chat' | 'documents' | 'settings';

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [engineSelection, setEngineSelection] = useState<EngineSelection>(DEFAULT_SELECTION);
  const [page, setPage] = useState<Page>('chat');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const upsertConversation = useCallback((c: Conversation) => {
    setConversations((prev) => {
      const idx = prev.findIndex((x) => x.id === c.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = c;
        return next.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      }
      return [c, ...prev].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    });
  }, []);

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, []);

  const store: AppStore = {
    conversations,
    activeConversationId,
    engineSelection,
    setConversations,
    setActiveConversationId,
    setEngineSelection,
    upsertConversation,
    deleteConversation,
  };

  return (
    <AppStoreContext.Provider value={store}>
      <div className="flex h-screen bg-[#0a0a0b] text-gray-100 overflow-hidden">
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
            {page === 'chat' && <ChatPage />}
            {page === 'documents' && <DocumentsPage />}
            {page === 'settings' && <SettingsPage />}
          </div>
        </div>
      </div>
    </AppStoreContext.Provider>
  );
}
