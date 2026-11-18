import type { User } from '@/types/user';

/**
 * Sesión iniciada: el token que devuelve POST /api/auth/login y el usuario.
 * Se guarda en el localStorage para no tener que iniciar sesión en cada recarga;
 * los chats NO se guardan aquí, están en el backend.
 */
export interface StoredSession {
  token: string;
  user: User;
}

const STORAGE_KEY = 'arsoft_session';

let current: StoredSession | null = loadSession();

export function loadSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: StoredSession): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // localStorage bloqueado: la sesión dura hasta que se recargue la página.
  }
  current = session;
}

export function clearSession(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nada que borrar
  }
  current = null;
}

/** Token de la sesión actual (lo añade api.ts a cada petición). */
export function currentToken(): string | null {
  return current?.token ?? null;
}
