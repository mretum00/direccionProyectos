import { FileText, BookOpen, GitBranch, History, Shield, BookMarked, ExternalLink } from 'lucide-react';
import type { Source, SourceType } from '@/types/chat';

const TYPE_CONFIG: Record<SourceType, { label: string; icon: typeof FileText; color: string }> = {
  manual: { label: 'Manual técnico', icon: FileText, color: 'text-cyan-400 bg-cyan-500/10' },
  dtc_catalog: { label: 'Catálogo DTC', icon: BookOpen, color: 'text-blue-400 bg-blue-500/10' },
  decision_tree: { label: 'Árbol de decisión', icon: GitBranch, color: 'text-teal-400 bg-teal-500/10' },
  historical_case: { label: 'Caso histórico', icon: History, color: 'text-purple-400 bg-purple-500/10' },
  safety_manual: { label: 'Manual de seguridad', icon: Shield, color: 'text-orange-400 bg-orange-500/10' },
  glossary: { label: 'Glosario', icon: BookMarked, color: 'text-texto-400 bg-texto-500/10' },
};

interface SourceCardProps {
  source: Source;
  onView: (source: Source) => void;
}

export function SourceCard({ source, onView }: SourceCardProps) {
  const config = TYPE_CONFIG[source.source_type] ?? TYPE_CONFIG.manual;
  const Icon = config.icon;

  return (
    <div className="rounded-lg bg-elevado border border-contraste/5 p-3 hover:border-cyan-500/20 transition-colors">
      <div className="flex items-start gap-2.5">
        <div className={`w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 ${config.color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-texto-200 truncate">{source.document}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${config.color} flex-shrink-0`}>{config.label}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-[10px] text-texto-500">
            {source.section && <span>{source.section}</span>}
            {source.page !== undefined && <span>· pág. {source.page}</span>}
            {source.engine_version && (
              <span className="text-cyan-400/60">· {source.engine_version}</span>
            )}
          </div>
          {source.excerpt && (
            <p className="text-xs text-texto-500 mt-1.5 line-clamp-2">{source.excerpt}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 mt-2.5 pt-2.5 border-t border-contraste/5">
        <button
          onClick={() => onView(source)}
          className="text-xs text-cyan-400 hover:text-cyan-300 font-medium"
        >
          Ver fuente
        </button>
        {source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-texto-500 hover:text-texto-300"
          >
            <ExternalLink className="w-3 h-3" />
            Abrir PDF
          </a>
        )}
      </div>
    </div>
  );
}
