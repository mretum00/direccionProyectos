import { config } from '@/config';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Único punto de salida HTTP hacia el backend.
 * - Errores de red: `fetch` lanza TypeError (se propaga tal cual).
 * - Errores HTTP: se lanza ApiError con el status.
 * - FormData: no se fija Content-Type para que el navegador añada el boundary.
 */
export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(`${config.apiUrl}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json() as Promise<T>;
}
