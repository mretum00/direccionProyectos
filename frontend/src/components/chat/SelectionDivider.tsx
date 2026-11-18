import { SlidersHorizontal } from 'lucide-react';
import type { ChatMessage } from '@/types/chat';
import { formatSelection } from '@/types/engine';

/** Marca en el chat la versión y el perfil con los que se pregunta (al empezar y cada vez que cambian). */
export function SelectionDivider({ message, first }: { message: ChatMessage; first: boolean }) {
  const label = formatSelection(message.engine_version, message.profile);
  return (
    <div className="flex items-center gap-3 py-1" role="separator" aria-label={`Consulta para ${label}`}>
      <div className="h-px flex-1 bg-contraste/5" />
      <span className="flex items-center gap-1.5 text-[11px] text-texto-500">
        <SlidersHorizontal className="h-3 w-3" aria-hidden="true" />
        {first ? 'Consulta para' : 'Cambio a'} <span className="font-medium text-marca-400">{label}</span>
      </span>
      <div className="h-px flex-1 bg-contraste/5" />
    </div>
  );
}
