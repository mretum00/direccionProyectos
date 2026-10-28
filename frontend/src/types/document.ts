export type DocumentType =
  | 'manual'
  | 'dtc_catalog'
  | 'decision_tree'
  | 'historical_case'
  | 'safety_manual'
  | 'glossary';

export type DocumentStatus = 'processed' | 'pending' | 'failed';

export interface TechnicalDocument {
  id: string;
  filename: string;
  type: DocumentType;
  engine: string;
  engine_version: string;
  pages: number;
  uploaded_at: string;
  status: DocumentStatus;
}

export interface DocumentsListResponse {
  documents: TechnicalDocument[];
}
