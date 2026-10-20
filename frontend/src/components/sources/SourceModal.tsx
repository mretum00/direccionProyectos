import { FileText, ExternalLink } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { Source, SourceType } from '@/types/chat';

const TYPE_LABELS: Record<SourceType, string> = {
  manual: 'Manual técnico',
  dtc_catalog: 'Catálogo DTC',
  decision_tree: 'Árbol de decisión',
  historical_case: 'Caso histórico',
  safety_manual: 'Manual de seguridad',
  glossary: 'Glosario',
};

interface SourceModalProps {
  source: Source | null;
  onClose: () => void;
}

export function SourceModal({ source, onClose }: SourceModalProps) {
  if (!source) return null;

  return (
    <Modal open={!!source} onClose={onClose} title="Detalle de fuente" maxWidth="max-w-xl">
      <div className="space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-cyan-400" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-texto">{source.document}</h4>
            <span className="text-xs text-texto-500">{TYPE_LABELS[source.source_type] ?? 'Documento'}</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          {source.section && (
            <div>
              <span className="text-texto-500">Sección</span>
              <p className="text-texto-200">{source.section}</p>
            </div>
          )}
          {source.page !== undefined && (
            <div>
              <span className="text-texto-500">Página</span>
              <p className="text-texto-200">{source.page}</p>
            </div>
          )}
          {source.engine && (
            <div>
              <span className="text-texto-500">Motor</span>
              <p className="text-texto-200">{source.engine}</p>
            </div>
          )}
          {source.engine_version && (
            <div>
              <span className="text-texto-500">Versión</span>
              <p className="text-cyan-400">{source.engine_version}</p>
            </div>
          )}
          {source.system && (
            <div>
              <span className="text-texto-500">Sistema</span>
              <p className="text-texto-200">{source.system}</p>
            </div>
          )}
        </div>

        {source.excerpt && (
          <div>
            <span className="text-xs text-texto-500">Fragmento</span>
            <div className="mt-1.5 p-3 rounded-lg bg-fondo border border-contraste/5">
              <p className="text-sm text-texto-300 leading-relaxed whitespace-pre-wrap">{source.excerpt}</p>
            </div>
          </div>
        )}

        {source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-cyan-500/10 text-cyan-400 text-sm font-medium hover:bg-cyan-500/20 transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            Abrir documento original
          </a>
        )}
      </div>
    </Modal>
  );
}
