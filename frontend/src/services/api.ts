import type { ApiClient } from '@/types/contract';
import {
  chatController,
  documentsController,
  healthController,
  sourcesController,
} from '@/controllers';

/** Fachada que usa la UI. Toda la comunicación real vive en `src/controllers`. */
export const api: ApiClient = {
  health: () => healthController.check(),
  chat: (request, signal) => chatController.send(request, signal),
  listDocuments: () => documentsController.list(),
  uploadDocument: (file) => documentsController.upload(file),
  getSource: (id) => sourcesController.get(id),
};

export { ApiError } from '@/controllers';
export type { ApiClient } from '@/types/contract';
