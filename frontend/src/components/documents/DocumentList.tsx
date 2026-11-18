import { AlertCircle, ExternalLink, Loader2 } from 'lucide-react';
import type { DocumentStatus, TechnicalDocument } from '@/types/document';
import { api } from '@/services/api';
import { SOURCE_TYPES } from '@/utils/sourceTypes';
import { InfoRow } from '@/components/ui/PageLayout';

const STATUS_CONFIG: Record<DocumentStatus, { label: string; color: string }> = {
  processed: { label: 'Procesado', color: 'insignia-exito' },
  pending: { label: 'Pendiente', color: 'insignia-aviso' },
  failed: { label: 'Fallido', color: 'insignia-peligro' },
};

interface DocumentListProps {
  documents: TechnicalDocument[];
  loading: boolean;
  /** false si no se ha podido pedir la lista al backend. */
  available: boolean;
}

export function DocumentList({ documents, loading, available }: DocumentListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-marca-400 animate-spin" />
      </div>
    );
  }

  if (!available) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-8 h-8 text-texto-600 mx-auto mb-3" />
        <p className="text-sm text-texto-400">No se ha podido cargar la documentación</p>
        <p className="text-xs text-texto-600 mt-1">Comprueba que el backend está en marcha y recarga la página</p>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-texto-500">No hay documentos indexados</p>
        <p className="text-xs text-texto-600 mt-1">Genera la base de datos con backend/db/database_generator.py</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-2">
      {documents.map((doc) => {
        const typeConfig = SOURCE_TYPES[doc.type] ?? SOURCE_TYPES.manual;
        const statusConfig = STATUS_CONFIG[doc.status] ?? STATUS_CONFIG.pending;
        return (
          <a
            key={doc.id}
            href={api.documentFileUrl(doc.id)}
            target="_blank"
            rel="noopener noreferrer"
            title="Abrir PDF"
            className="tarjeta-interactiva fila cursor-pointer"
          >
            <InfoRow
              icon={typeConfig.icon}
              title={doc.filename}
              detail={
                <>
                  <span>{typeConfig.label}</span>
                  <span>· {doc.engine_version}</span>
                  {doc.pages > 0 && <span>· {doc.pages} pág.</span>}
                  <span>· {new Date(doc.uploaded_at).toLocaleDateString('es-ES')}</span>
                </>
              }
              badge={<span className={`${statusConfig.color} flex-shrink-0`}>{statusConfig.label}</span>}
              actionIcon={ExternalLink}
            />
          </a>
        );
      })}
    </div>
  );
}
