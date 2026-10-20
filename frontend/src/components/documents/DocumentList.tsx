import { useState } from 'react';
import { FileText, BookOpen, GitBranch, History, Shield, BookMarked, Loader2, Upload, AlertCircle } from 'lucide-react';
import type { TechnicalDocument, DocumentType, DocumentStatus } from '@/types/document';
import { api } from '@/services/api';
import { config } from '@/config';

const TYPE_CONFIG: Record<DocumentType, { label: string; icon: typeof FileText }> = {
  manual: { label: 'Manual técnico', icon: FileText },
  dtc_catalog: { label: 'Catálogo DTC', icon: BookOpen },
  decision_tree: { label: 'Árbol de decisión', icon: GitBranch },
  historical_case: { label: 'Casos históricos', icon: History },
  safety_manual: { label: 'Manual de seguridad', icon: Shield },
  glossary: { label: 'Glosario', icon: BookMarked },
};

const STATUS_CONFIG: Record<DocumentStatus, { label: string; color: string }> = {
  processed: { label: 'Procesado', color: 'text-green-400 bg-green-500/10' },
  pending: { label: 'Pendiente', color: 'text-amber-400 bg-amber-500/10' },
  failed: { label: 'Fallido', color: 'text-red-400 bg-red-500/10' },
};

interface DocumentListProps {
  documents: TechnicalDocument[];
  loading: boolean;
  endpointAvailable: boolean;
}

export function DocumentList({ documents, loading, endpointAvailable }: DocumentListProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await api.uploadDocument(file);
    } catch {
      setUploadError('No se ha podido subir el documento');
    } finally {
      setUploading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
      </div>
    );
  }

  if (!endpointAvailable) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-8 h-8 text-texto-600 mx-auto mb-3" />
        <p className="text-sm text-texto-400">El endpoint de documentación no está disponible</p>
        <p className="text-xs text-texto-600 mt-1">Cuando el backend lo soporte, los documentos aparecerán aquí</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {config.enableDocumentUpload && (
        <div className="flex items-center gap-3">
          <label className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
            uploading ? 'bg-texto-500/10 text-texto-500' : 'bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20'
          }`}>
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploading ? 'Subiendo...' : 'Añadir documento'}
            <input type="file" accept=".pdf" onChange={handleUpload} disabled={uploading} className="hidden" />
          </label>
          {uploadError && <span className="text-xs text-red-400">{uploadError}</span>}
        </div>
      )}

      <div className="grid grid-cols-1 gap-2">
        {documents.map((doc) => {
          const typeConfig = TYPE_CONFIG[doc.type] ?? TYPE_CONFIG.manual;
          const statusConfig = STATUS_CONFIG[doc.status] ?? STATUS_CONFIG.pending;
          const Icon = typeConfig.icon;
          return (
            <div key={doc.id} className="flex items-center gap-3 p-3 rounded-lg bg-tarjeta border border-contraste/5 hover:border-contraste/10 transition-colors">
              <div className="w-9 h-9 rounded-md bg-contraste/5 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-texto-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-texto-200 truncate">{doc.filename}</div>
                <div className="flex items-center gap-2 text-[10px] text-texto-500 mt-0.5">
                  <span>{typeConfig.label}</span>
                  <span>· {doc.engine} {doc.engine_version}</span>
                  <span>· {doc.pages} pág.</span>
                  <span>· {new Date(doc.uploaded_at).toLocaleDateString('es-ES')}</span>
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded ${statusConfig.color} flex-shrink-0`}>
                {statusConfig.label}
              </span>
            </div>
          );
        })}
      </div>

      {documents.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-texto-500">No hay documentos disponibles</p>
        </div>
      )}
    </div>
  );
}
