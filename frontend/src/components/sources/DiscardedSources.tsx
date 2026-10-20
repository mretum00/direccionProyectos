import { useState } from 'react';
import { ChevronDown, FileX2 } from 'lucide-react';
import type { DiscardedSource } from '@/types/chat';

interface DiscardedSourcesProps {
  sources: DiscardedSource[];
}

const REASON_LABELS: Record<string, string> = {
  obsolete_version: 'Versión obsoleta',
  version_mismatch: 'Versión no coincide',
};

export function DiscardedSources({ sources }: DiscardedSourcesProps) {
  const [expanded, setExpanded] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left"
      >
        <FileX2 className="w-4 h-4 text-amber-400 flex-shrink-0" />
        <span className="text-xs text-amber-400 font-medium flex-1">
          Documentación descartada por no aplicar a tu versión ({sources.length})
        </span>
        <ChevronDown className={`w-3.5 h-3.5 text-amber-400/60 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {sources.map((src, i) => (
            <div key={i} className="flex items-start gap-2 text-xs p-2 rounded-md bg-amber-500/5">
              <div className="min-w-0 flex-1">
                <span className="text-texto-300">{src.document}</span>
                <span className="text-amber-400/70 ml-1.5">· {REASON_LABELS[src.reason] ?? src.reason}</span>
                {src.detail && <p className="text-texto-500 mt-0.5">{src.detail}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
