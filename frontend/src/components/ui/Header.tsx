import { Menu, MessageSquare, FileText, Settings } from 'lucide-react';
import type { Page } from '@/App';
import { EngineSelector } from '@/components/engine/EngineSelector';
import { ProfileSwitch } from '@/components/engine/ProfileSwitch';
import { Logo } from './Logo';

interface HeaderProps {
  page: Page;
  onPageChange: (p: Page) => void;
  onMenuClick: () => void;
}

export function Header({ page, onPageChange, onMenuClick }: HeaderProps) {
  const navItems: { id: Page; label: string; icon: typeof MessageSquare }[] = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'documents', label: 'Documentación', icon: FileText },
    { id: 'settings', label: 'Ajustes', icon: Settings },
  ];

  return (
    <header className="flex items-center justify-between gap-3 px-4 h-14 border-b border-contraste/5 bg-panel/80 backdrop-blur-sm flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-1.5 rounded-md hover:bg-contraste/5 text-texto-400"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:block">
          <Logo />
        </div>
      </div>

      <nav className="flex items-center gap-1">
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onPageChange(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              page === id
                ? 'bg-cyan-500/10 text-cyan-400'
                : 'text-texto-400 hover:text-texto-200 hover:bg-contraste/5'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-2 min-w-0">
        <ProfileSwitch />
        <EngineSelector />
      </div>
    </header>
  );
}
