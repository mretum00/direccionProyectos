import type { TechnicalDocument } from '@/types/document';

export const documentsController = {
  async list(): Promise<TechnicalDocument[]> {
    // TODO: GET /api/documents
    throw new Error('documentsController.list no implementado');
  },

  async upload(_file: File): Promise<TechnicalDocument> {
    // TODO: POST /api/documents (multipart)
    throw new Error('documentsController.upload no implementado');
  },
};
