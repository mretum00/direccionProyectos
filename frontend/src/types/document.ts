import type { SourceType } from './chat';

export type DocumentStatus = 'processed' | 'pending' | 'failed';

export interface TechnicalDocument {
  id: string;
  filename: string;
  type: SourceType;
  engine_version: string;
  pages: number;
  uploaded_at: string;
  status: DocumentStatus;
}
