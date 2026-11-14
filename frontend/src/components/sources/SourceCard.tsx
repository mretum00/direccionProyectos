import { ChevronRight } from 'lucide-react';
import type { Source } from '@/types/chat';
import { SOURCE_TYPES } from '@/utils/sourceTypes';

interface SourceCardProps {
  source: Source;
  onView: (source: Source) => void;
}

export function SourceCard({ source, onView }: SourceCardProps) {
  const { label, icon: Icon, color } = SOURCE_TYPES[source.source_type] ?? SOURCE_TYPES.manual;
  // Los fragmentos vienen con viñetas (•) pegadas: en la ficha se leen mejor como una sola línea.
  const excerpt = source.excerpt?.replace(/\s*•\s*/g, ' · ').replace(/^\s*·\s*/, '');

  return (
    <button
      type="button"
      onClick={() => onView(source)}
      title="Ver detalle de la fuente"
      className="group w-full text-left rounded-lg bg-elevado border border-contraste/5 p-3 hover:border-marca-500/30 transition-colors"
    >
      <div className="flex items-start gap-2.5">
        <div className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-texto-200 truncate">{source.document}</span>
            <span className={`text-[11px] px-1.5 py-0.5 rounded ${color} flex-shrink-0`}>{label}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-[11px] text-texto-500">
            {source.section && <span>{source.section}</span>}
            {source.page !== undefined && <span>· pág. {source.page}</span>}
            {source.engine_version && <span className="text-marca-400">· {source.engine_version}</span>}
          </div>
          {excerpt && <p className="text-xs text-texto-500 mt-1.5 line-clamp-2">{excerpt}</p>}
        </div>
        <ChevronRight className="w-4 h-4 mt-2 flex-shrink-0 text-texto-600 group-hover:text-marca-400 transition-colors" />
      </div>
    </button>
  );
}
