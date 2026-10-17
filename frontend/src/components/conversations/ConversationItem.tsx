import { useState, useRef, useEffect } from 'react';
import { MoreVertical, Star, Pencil, Trash2, Copy, MessageSquare } from 'lucide-react';
import type { Conversation } from '@/types/conversation';
import { useAppStore } from '@/store/appStore';
import { useConversations } from '@/hooks/useConversations';
import { relativeDate } from '@/utils/dateUtils';
import { toPlainPreview } from '@/utils/text';
import { ConfirmationModal } from './ConfirmationModal';

interface ConversationItemProps {
  conversation: Conversation;
}

export function ConversationItem({ conversation }: ConversationItemProps) {
  const store = useAppStore();
  const { selectConversation, renameConversation, deleteConversation, duplicateConversation, toggleFavorite } = useConversations();
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(conversation.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isActive = store.activeConversationId === conversation.id;
  const lastMessage = conversation.messages[conversation.messages.length - 1];

  // Un listener global por ítem de la lista era innecesario: solo existe con el menú abierto.
  useEffect(() => {
    if (!menuOpen) return;
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  function commitRename() {
    if (renameValue.trim()) renameConversation(conversation.id, renameValue.trim());
    setRenaming(false);
  }

  return (
    <>
      <div
        onClick={() => selectConversation(conversation.id)}
        className={`group relative flex items-start gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${
          isActive ? 'bg-cyan-500/10' : 'hover:bg-white/5'
        }`}
      >
        <MessageSquare className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${isActive ? 'text-cyan-400' : 'text-gray-500'}`} />

        <div className="flex-1 min-w-0">
          {renaming ? (
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename();
                if (e.key === 'Escape') setRenaming(false);
              }}
              onClick={(e) => e.stopPropagation()}
              className="w-full bg-[#0a0a0b] border border-cyan-500/30 rounded px-1.5 py-0.5 text-xs text-white outline-none"
            />
          ) : (
            <div className={`text-xs font-medium truncate ${isActive ? 'text-cyan-300' : 'text-gray-200'}`}>
              {conversation.title}
            </div>
          )}
          <div className="flex items-center gap-1.5 mt-0.5">
            {conversation.favorite && <Star className="w-2.5 h-2.5 text-amber-400 fill-amber-400 flex-shrink-0" />}
            <span className="text-[10px] text-gray-500 truncate">
              {lastMessage ? toPlainPreview(lastMessage.content).slice(0, 40) : 'Sin mensajes'}
            </span>
            <span className="text-[10px] text-gray-600 flex-shrink-0">{relativeDate(conversation.updated_at)}</span>
          </div>
          {conversation.engine_version && (
            <span className="inline-block mt-0.5 text-[9px] text-gray-600">{conversation.engine_version}</span>
          )}
        </div>

        <div ref={menuRef} className="relative flex-shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 text-gray-500 transition-opacity"
          >
            <MoreVertical className="w-3.5 h-3.5" />
          </button>
          {menuOpen && (
            <div
              className="absolute right-0 top-full mt-1 w-40 bg-[#1a1a1d] border border-white/10 rounded-lg shadow-xl z-50 py-1"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => { setRenaming(true); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-white/5"
              >
                <Pencil className="w-3 h-3" /> Renombrar
              </button>
              <button
                onClick={() => { duplicateConversation(conversation.id); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-white/5"
              >
                <Copy className="w-3 h-3" /> Duplicar
              </button>
              <button
                onClick={() => { toggleFavorite(conversation.id); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-white/5"
              >
                <Star className="w-3 h-3" /> {conversation.favorite ? 'Quitar favorita' : 'Marcar favorita'}
              </button>
              <div className="h-px bg-white/5 my-1" />
              <button
                onClick={() => { setConfirmDelete(true); setMenuOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10"
              >
                <Trash2 className="w-3 h-3" /> Eliminar
              </button>
            </div>
          )}
        </div>
      </div>

      <ConfirmationModal
        open={confirmDelete}
        title="Eliminar conversación"
        message={`¿Seguro que quieres eliminar "${conversation.title}"? Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        onConfirm={() => { deleteConversation(conversation.id); setConfirmDelete(false); }}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}
