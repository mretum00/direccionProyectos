import { FileText } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { Source } from '@/types/chat';
import { SOURCE_TYPES } from '@/utils/sourceTypes';
import { api } from '@/services/api';

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
          <div className="w-10 h-10 rounded-lg bg-marca-500/10 flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-marca-400" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-texto">{source.document}</h4>
            <span className="text-xs text-texto-500">{SOURCE_TYPES[source.source_type]?.label ?? 'Documento'}</span>
          </div>
        </div>

        <div className="rounded-lg bg-fondo border border-contraste/5 p-3">
          <span className="text-xs text-texto-500">Relación con la respuesta</span>
          <p className="text-sm text-texto-200 mt-1">
            {source.citation_status === 'cited'
              ? 'El modelo la ha señalado expresamente en su apartado FUENTE. Esto no verifica automáticamente que cada afirmación esté respaldada.'
              : 'Este fragmento se recuperó y se entregó al modelo como contexto, pero no fue citado expresamente en su apartado FUENTE.'}
          </p>
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
          {source.engine_version && (
            <div>
              <span className="text-texto-500">Versión</span>
              <p className="text-marca-400">{source.engine_version}</p>
            </div>
          )}
        </div>

        {source.excerpt && (
          <div>
            <span className="text-xs text-texto-500">Fragmento</span>
            <div className="mt-1.5 p-3 rounded-lg bg-fondo border border-contraste/5">
              <p className="text-sm text-texto-300 leading-relaxed whitespace-pre-wrap">{source.excerpt.replace(/\s*•\s*/g, '\n• ').trim()}</p>
            </div>
          </div>
        )}

        <a
          href={`${api.documentFileUrl(source.document)}#page=${source.page ?? 1}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm font-medium text-marca-400 hover:text-marca-300 transition-colors"
        >
          <FileText className="w-4 h-4" />
          Abrir PDF en la página {source.page ?? 1}
        </a>
      </div>
    </Modal>
  );
}
