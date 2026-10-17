import { Plus, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useConversations } from '@/hooks/useConversations';
import { useAppStore } from '@/store/appStore';
import { ConversationItem } from './ConversationItem';
import { ConversationSearch } from './ConversationSearch';
import { Logo } from '@/components/ui/Logo';
import { groupConversationsByDate } from '@/utils/dateUtils';

interface SidebarProps {
  onNavigate: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const { createConversation } = useConversations();
  const store = useAppStore();
  const [searchOpen, setSearchOpen] = useState(false);

  const grouped = useMemo(() => groupConversationsByDate(store.conversations), [store.conversations]);

  return (
    <div className="flex flex-col w-full h-full bg-[#0d0d0f] border-r border-white/5">
      <div className="p-4 flex-shrink-0">
        <Logo />
      </div>

      <div className="px-3 pb-3 flex gap-2 flex-shrink-0">
        <button
          onClick={() => {
            createConversation();
            onNavigate();
          }}
          className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium hover:from-cyan-400 hover:to-blue-500 transition-all shadow-lg shadow-cyan-500/10"
        >
          <Plus className="w-4 h-4" />
          Nueva conversación
        </button>
      </div>

      <div className="px-3 pb-3 flex-shrink-0">
        <button
          onClick={() => setSearchOpen(true)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-gray-200 text-xs transition-colors"
        >
          <Search className="w-3.5 h-3.5" />
          Buscar conversaciones...
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {store.conversations.length === 0 ? (
          <div className="text-center py-8 px-4">
            <p className="text-xs text-gray-500">No hay conversaciones aún</p>
            <p className="text-xs text-gray-600 mt-1">Crea una nueva para empezar</p>
          </div>
        ) : (
          grouped.map(({ label, items }) => (
            <div key={label} className="mb-4">
              <div className="px-2 py-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                {label}
              </div>
              {items.map((conv) => (
                <ConversationItem key={conv.id} conversation={conv} />
              ))}
            </div>
          ))
        )}
      </div>

      <ConversationSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
