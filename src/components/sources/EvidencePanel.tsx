import { useState } from 'react';
import { BookOpen } from 'lucide-react';
import type { Source } from '@/types/chat';
import { SourceCard } from './SourceCard';
import { SourceModal } from './SourceModal';

interface EvidencePanelProps {
  sources: Source[];
}

export function EvidencePanel({ sources }: EvidencePanelProps) {
  const [selected, setSelected] = useState<Source | null>(null);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <BookOpen className="w-4 h-4 text-cyan-400" />
        <h4 className="text-sm font-semibold text-gray-200">
          Evidencia utilizada
          <span className="text-gray-500 font-normal ml-1.5">({sources.length})</span>
        </h4>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {sources.map((source) => (
          <SourceCard key={source.id} source={source} onView={setSelected} />
        ))}
      </div>

      <SourceModal source={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
