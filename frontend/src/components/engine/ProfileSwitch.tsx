import { Wrench, User } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import type { Profile } from '@/types/chat';

export function ProfileSwitch() {
  const store = useAppStore();
  const isMechanic = store.engineSelection.profile === 'mechanic';

  return (
    <div className="flex items-center bg-contraste/5 rounded-md border border-contraste/5">
      <button
        onClick={() => store.setEngineSelection({ ...store.engineSelection, profile: 'mechanic' as Profile })}
        className={`flex items-center gap-1 px-2 py-1.5 rounded-l-md text-xs transition-colors ${
          isMechanic ? 'text-cyan-400' : 'text-texto-500 hover:text-texto-300'
        }`}
        title="Lenguaje técnico"
      >
        <Wrench className="w-3.5 h-3.5" />
        <span className="hidden xl:inline">Mecánico</span>
      </button>
      <div className="w-px h-4 bg-contraste/10" />
      <button
        onClick={() => store.setEngineSelection({ ...store.engineSelection, profile: 'user' as Profile })}
        className={`flex items-center gap-1 px-2 py-1.5 rounded-r-md text-xs transition-colors ${
          !isMechanic ? 'text-cyan-400' : 'text-texto-500 hover:text-texto-300'
        }`}
        title="Lenguaje sencillo"
      >
        <User className="w-3.5 h-3.5" />
        <span className="hidden xl:inline">Usuario</span>
      </button>
    </div>
  );
}
