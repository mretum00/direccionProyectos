import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import type { Source } from '@/types/chat';
import { SourceCard } from './SourceCard';
import { SourceModal } from './SourceModal';

/** Fuentes visibles de entrada: el resto se despliega bajo demanda para no alargar la respuesta. */
const VISIBLE_SOURCES = 3;

interface EvidencePanelProps {
  sources: Source[];
}

// Sección "Fuentes" al final de la respuesta: las fichas de los documentos
// recuperados. Su título imita los encabezados ### de la respuesta.
export function EvidencePanel({ sources }: EvidencePanelProps) {
  const [selected, setSelected] = useState<Source | null>(null);
  const [expanded, setExpanded] = useState(false);

  const hidden = sources.length - VISIBLE_SOURCES;
  const shown = expanded || hidden <= 0 ? sources : sources.slice(0, VISIBLE_SOURCES);

  return (
    <div className="space-y-2">
      <h3 className="text-marca-400 font-bold text-[11px] tracking-wider uppercase">
        Fuentes
        <span className="text-texto-500 font-normal ml-1.5">({sources.length})</span>
      </h3>

      <div className="grid grid-cols-1 gap-2">
        {shown.map((source) => (
          <SourceCard key={source.id} source={source} onView={setSelected} />
        ))}
      </div>

      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1 text-xs font-medium text-marca-400 hover:text-marca-300 transition-colors"
        >
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          {expanded ? 'Mostrar menos' : `Ver ${hidden} fuente${hidden > 1 ? 's' : ''} más`}
        </button>
      )}

      <SourceModal source={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
