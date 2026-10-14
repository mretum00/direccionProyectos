import { useState, useEffect } from 'react';
import { FileText, AlertCircle } from 'lucide-react';
import { DocumentList } from '@/components/documents/DocumentList';
import { api, ApiError } from '@/services/api';
import type { TechnicalDocument } from '@/types/document';

export function DocumentsPage() {
  const [documents, setDocuments] = useState<TechnicalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [endpointAvailable, setEndpointAvailable] = useState(true);

  useEffect(() => {
    let mounted = true;
    api
      .listDocuments()
      .then((docs) => {
        if (mounted) {
          setDocuments(docs);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!mounted) return;
        setLoading(false);
        if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
          setEndpointAvailable(false);
        } else {
          setEndpointAvailable(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center">
            <FileText className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Documentación</h2>
            <p className="text-xs text-gray-500">Documentos técnicos indexados en el sistema</p>
          </div>
        </div>

        {!endpointAvailable && !loading && (
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 mb-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-amber-400 font-medium">Endpoint no disponible</p>
              <p className="text-xs text-gray-400 mt-1">
                El endpoint GET /api/documents aún no está implementado en el backend.
                Cuando esté disponible, los documentos indexados aparecerán aquí.
              </p>
            </div>
          </div>
        )}

        <DocumentList documents={documents} loading={loading} endpointAvailable={endpointAvailable} />
      </div>
    </div>
  );
}
