import { useState, useMemo } from 'react';
import { Search, X, Star, Calendar, Filter } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { useConversations } from '@/hooks/useConversations';
import { useAppStore } from '@/store/appStore';
import { relativeDate } from '@/utils/dateUtils';
import { ENGINES } from '@/types/engine';

interface ConversationSearchProps {
  open: boolean;
  onClose: () => void;
}

export function ConversationSearch({ open, onClose }: ConversationSearchProps) {
  const { searchConversations, selectConversation } = useConversations();
  const store = useAppStore();
  const [query, setQuery] = useState('');
  const [engineVersion, setEngineVersion] = useState('');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const results = useMemo(() => {
    return searchConversations(query, {
      engine_version: engineVersion || undefined,
      favoriteOnly,
      dateFrom: dateFrom ? new Date(dateFrom).toISOString() : undefined,
      dateTo: dateTo ? new Date(dateTo + 'T23:59:59').toISOString() : undefined,
    });
  }, [query, engineVersion, favoriteOnly, dateFrom, dateTo, searchConversations]);

  const versions = ENGINES[0]?.versions ?? [];

  function handleSelect(id: string) {
    selectConversation(id);
    onClose();
  }

  function clearAll() {
    setQuery('');
    setEngineVersion('');
    setFavoriteOnly(false);
    setDateFrom('');
    setDateTo('');
  }

  return (
    <Modal open={open} onClose={onClose} title="Buscar conversaciones" maxWidth="max-w-2xl">
      <div className="space-y-4">
        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por título, contenido, motor, versión..."
            className="w-full pl-10 pr-10 py-2.5 bg-[#0a0a0b] border border-white/10 rounded-lg text-sm text-white outline-none focus:border-cyan-500/50"
          />
          {query && (
            <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Filter toggle */}
        <button
          onClick={() => setShowFilters((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200"
        >
          <Filter className="w-3.5 h-3.5" />
          {showFilters ? 'Ocultar filtros' : 'Mostrar filtros'}
        </button>

        {showFilters && (
          <div className="grid grid-cols-2 gap-3 p-3 bg-white/5 rounded-lg">
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">Versión</label>
              <select
                value={engineVersion}
                onChange={(e) => setEngineVersion(e.target.value)}
                className="w-full bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none"
              >
                <option value="">Todas</option>
                {versions.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">Favoritas</label>
              <button
                onClick={() => setFavoriteOnly((v) => !v)}
                className={`w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-colors ${
                  favoriteOnly
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : 'bg-[#0a0a0b] text-gray-400 border-white/10'
                }`}
              >
                <Star className="w-3 h-3" /> Solo favoritas
              </button>
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">Desde</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none"
              />
            </div>
            <div>
              <label className="block text-[10px] text-gray-500 mb-1">Hasta</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none"
              />
            </div>
          </div>
        )}

        {/* Results */}
        <div className="max-h-80 overflow-y-auto space-y-2">
          {results.length === 0 ? (
            <div className="text-center py-8">
              <Calendar className="w-8 h-8 text-gray-700 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No se encontraron conversaciones</p>
              {(query || engineVersion || favoriteOnly || dateFrom || dateTo) && (
                <button onClick={clearAll} className="text-xs text-cyan-400 hover:text-cyan-300 mt-2">
                  Limpiar filtros
                </button>
              )}
            </div>
          ) : (
            results.map((conv) => {
              const matchSnippet = query
                ? conv.messages.find((m) => m.content.toLowerCase().includes(query.toLowerCase()))
                : undefined;
              return (
                <button
                  key={conv.id}
                  onClick={() => handleSelect(conv.id)}
                  className="w-full text-left p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-200 truncate">
                      {conv.favorite && <Star className="w-3 h-3 text-amber-400 inline mr-1 fill-amber-400" />}
                      {conv.title}
                    </span>
                    <span className="text-[10px] text-gray-500 flex-shrink-0">{relativeDate(conv.updated_at)}</span>
                  </div>
                  {conv.engine_version && (
                    <span className="text-[10px] text-cyan-400/70">{conv.engine} · {conv.engine_version}</span>
                  )}
                  {matchSnippet && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                      ...{matchSnippet.content.slice(0, 80)}...
                    </p>
                  )}
                </button>
              );
            })
          )}
        </div>

        {(query || engineVersion || favoriteOnly || dateFrom || dateTo) && results.length > 0 && (
          <button onClick={clearAll} className="text-xs text-gray-400 hover:text-gray-200">
            Limpiar filtros
          </button>
        )}
      </div>
    </Modal>
  );
}
