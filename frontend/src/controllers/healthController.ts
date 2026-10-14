import type { HealthResponse } from '@/types/contract';

export const healthController = {
  async check(): Promise<HealthResponse> {
    // TODO: GET /api/health
    throw new Error('healthController.check no implementado');
  },
};
