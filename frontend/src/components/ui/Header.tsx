import { Menu, MessageSquare, FileText, Info, LogOut, type LucideIcon } from 'lucide-react';
import type { Page } from '@/App';
import { useAuth } from '@/useAuth';
import { EngineSelector } from '@/components/engine/EngineSelector';
import { Logo } from './Logo';

interface HeaderProps {
  page: Page;
  onPageChange: (p: Page) => void;
  onMenuClick: () => void;
}

const NAV_ITEMS: { id: Page; label: string; icon: LucideIcon }[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'documents', label: 'Documentación', icon: FileText },
  { id: 'system', label: 'Sistema', icon: Info },
];

export function Header({ page, onPageChange, onMenuClick }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="flex items-center justify-between gap-3 px-4 h-14 border-b border-contraste/5 bg-panel/80 backdrop-blur-sm flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-1.5 rounded-md hover:bg-contraste/5 text-texto-400"
        >
          <Menu className="w-5 h-5" />
        </button>
        {/* En pantallas grandes el logo ya está en la barra lateral. */}
        <div className="hidden sm:block lg:hidden">
          <Logo />
        </div>
      </div>

      <nav className="flex items-center gap-1">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onPageChange(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              page === id
                ? 'bg-marca-500/10 text-marca-400'
                : 'text-texto-400 hover:text-texto-200 hover:bg-contraste/5'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-2 min-w-0">
        <EngineSelector />
        <div className="flex items-center gap-1 pl-2 border-l border-contraste/10">
          <span className="hidden md:inline max-w-[8rem] truncate text-xs text-texto-400" title={user?.username}>
            {user?.username}
          </span>
          <button
            onClick={() => void logout()}
            className="p-1.5 rounded-md text-texto-400 hover:text-texto-200 hover:bg-contraste/5"
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
