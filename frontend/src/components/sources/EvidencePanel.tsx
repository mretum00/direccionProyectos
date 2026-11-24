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

  const citadas = sources.filter((source) => source.citation_status === 'cited');
  const ordenadas = [...citadas, ...sources.filter((source) => source.citation_status !== 'cited')];
  const hidden = ordenadas.length - VISIBLE_SOURCES;
  const shown = expanded || hidden <= 0 ? ordenadas : ordenadas.slice(0, VISIBLE_SOURCES);

  return (
    <div className="space-y-2">
      <h3 className="text-marca-400 font-bold text-[11px] tracking-wider uppercase">
        Fuentes y contexto documental
        <span className="text-texto-500 font-normal ml-1.5">({sources.length})</span>
      </h3>
      <p className="text-[11px] text-texto-500 leading-relaxed">
        {citadas.length > 0
          ? `${citadas.length} referencia(s) señalada(s) por el modelo en su apartado FUENTE. Las demás son fragmentos recuperados que también recibió como contexto.`
          : 'El modelo no ha señalado referencias explícitas en su apartado FUENTE. Se muestran los fragmentos recuperados que recibió como contexto.'}
        {' '}La cita declarada por el modelo no constituye una verificación automática de cada afirmación.
      </p>

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
