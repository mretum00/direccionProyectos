import { useState } from 'react';
import type { Source } from '@/types/chat';
import { SourceCard } from './SourceCard';
import { SourceModal } from './SourceModal';

interface EvidencePanelProps {
  sources: Source[];
}

// Sección "Fuentes" al final de la respuesta: las fichas de los documentos
// recuperados. Su título imita los encabezados ### de la respuesta.
export function EvidencePanel({ sources }: EvidencePanelProps) {
  const [selected, setSelected] = useState<Source | null>(null);

  return (
    <div className="space-y-2">
      <h3 className="text-cyan-400 font-bold text-xs tracking-wider uppercase">
        Fuentes
        <span className="text-texto-500 font-normal ml-1.5">({sources.length})</span>
      </h3>

      <div className="grid grid-cols-1 gap-2">
        {sources.map((source) => (
          <SourceCard key={source.id} source={source} onView={setSelected} />
        ))}
      </div>

      <SourceModal source={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
