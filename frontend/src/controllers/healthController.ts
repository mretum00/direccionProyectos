import type { HealthResponse } from '@/types/contract';
import { apiRequest } from './httpClient';

export const healthController = {
  check(): Promise<HealthResponse> {
    return apiRequest<HealthResponse>('/api/health');
  },
};
