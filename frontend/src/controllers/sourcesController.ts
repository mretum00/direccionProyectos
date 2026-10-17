import { apiRequest } from './httpClient';

export const sourcesController = {
  get(id: string): Promise<{ excerpt: string; url?: string }> {
    return apiRequest<{ excerpt: string; url?: string }>(`/api/sources/${encodeURIComponent(id)}`);
  },
};
