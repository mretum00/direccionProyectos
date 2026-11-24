import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError, api, setUnauthorizedHandler } from '@/services/api';
import { clearSession, loadSession, saveSession } from '@/services/session';
import { useToast } from '@/useToast';
import type { ToastData } from '@/components/ui/Toast';
import type { User } from '@/types/user';

import { AuthContext, type AuthStatus } from './authContext';

/** Por qué se cierra la sesión: cada motivo tiene su aviso. Recargar con la sesión guardada no avisa. */
type EndReason = 'logged_out' | 'expired' | 'offline';

const END_TOASTS: Record<EndReason, ToastData> = {
  logged_out: { tone: 'info', title: 'Sesión cerrada', description: 'Has cerrado sesión correctamente.' },
  expired: {
    tone: 'aviso',
    title: 'Sesión cerrada',
    description: 'Has entrado con tu usuario en otro dispositivo. Vuelve a iniciar sesión.',
  },
  offline: {
    tone: 'peligro',
    title: 'No se ha podido comprobar tu sesión',
    description: 'Sin conexión con el servidor. Inicia sesión de nuevo cuando esté disponible.',
  },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [user, setUser] = useState<User | null>(() => loadSession()?.user ?? null);
  const [status, setStatus] = useState<AuthStatus>(() => (loadSession() ? 'checking' : 'anonymous'));

  const endSession = useCallback(
    (reason: EndReason) => {
      clearSession();
      setUser(null);
      setStatus('anonymous');
      toast.show(END_TOASTS[reason]);
    },
    [toast],
  );

  // Cualquier 401 del backend (sesión cerrada o abierta en otro sitio) devuelve al login.
  useEffect(() => {
    setUnauthorizedHandler(() => endSession('expired'));
  }, [endSession]);

  // Al abrir la app se comprueba que el token guardado sigue siendo válido.
  useEffect(() => {
    if (!loadSession()) return;
    let active = true;
    api
      .me()
      .then((me) => {
        if (!active) return;
        setUser(me);
        setStatus('authenticated');
      })
      .catch((e) => {
        // Token que ya no vale: el 401 ya ha cerrado la sesión con el aviso 'expired'.
        if (e instanceof ApiError && e.status === 401) return;
        // Sin conexión no se puede comprobar: se cierra la sesión local para no mostrar una app que no funciona.
        if (active) endSession('offline');
      });
    return () => {
      active = false;
    };
  }, [endSession]);

  const login = useCallback(
    async (username: string, password: string) => {
      const session = await api.login(username, password);
      saveSession(session);
      setUser(session.user);
      setStatus('authenticated');
      // Los "no se ha podido iniciar sesión" de intentos anteriores ya no aplican.
      toast.clearErrors();
      toast.show({
        tone: 'exito',
        title: 'Sesión iniciada',
        description: `Hola, ${session.user.username}. Ya puedes consultar el asistente.`,
      });
    },
    [toast],
  );

  const register = useCallback(async (username: string, password: string) => {
    await api.register(username, password);
  }, []);

  const logout = useCallback(async () => {
    // Aunque falle la llamada (sin conexión), la sesión local se cierra igualmente.
    await api.logout().catch(() => undefined);
    endSession('logged_out');
  }, [endSession]);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

