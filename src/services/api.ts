import type { ApiClient } from '@/types/contract';
import { mockApi } from './mockApi';
import { realApi } from './realApi';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export const api: ApiClient = USE_MOCK ? mockApi : realApi;

export { ApiError } from './realApi';
export type { ApiClient } from '@/types/contract';
