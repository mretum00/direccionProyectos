import { useEffect, useState } from 'react';
import { FileText } from 'lucide-react';
import { DocumentList } from '@/components/documents/DocumentList';
import { PageLayout } from '@/components/ui/PageLayout';
import { api } from '@/services/api';
import type { TechnicalDocument } from '@/types/document';

export function DocumentsPage() {
  const [documents, setDocuments] = useState<TechnicalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    let mounted = true;
    api
      .listDocuments()
      .then((docs) => {
        if (mounted) setDocuments(docs);
      })
      .catch(() => {
        if (mounted) setAvailable(false);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <PageLayout icon={FileText} title="Documentación" subtitle="Documentos técnicos indexados en el sistema">
      <DocumentList documents={documents} loading={loading} available={available} />
    </PageLayout>
  );
}
