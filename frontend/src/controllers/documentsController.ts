import type { TechnicalDocument } from '@/types/document';
import { apiRequest } from './httpClient';

export const documentsController = {
  /** Lanza ApiError (404/501) si el backend aún no implementa el endpoint. */
  async list(): Promise<TechnicalDocument[]> {
    const data = await apiRequest<{ documents: TechnicalDocument[] } | TechnicalDocument[]>('/api/documents');
    return Array.isArray(data) ? data : data.documents;
  },

  upload(file: File): Promise<TechnicalDocument> {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest<TechnicalDocument>('/api/documents', { method: 'POST', body: formData });
  },
};
