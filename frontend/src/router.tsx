import { useEffect, useState, type MouseEvent, type ReactNode } from 'react';

/**
 * Router mínimo basado en la History API (sin dependencias).
 * Rutas: "/" (asistente), "/login" (inicio de sesión) y "/register" (registro).
 */
export type Route = '/' | '/login' | '/register';

const ROUTES: Route[] = ['/', '/login', '/register'];
const NAVIGATE_EVENT = 'app:navigate';

function currentRoute(): Route {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  return (ROUTES as string[]).includes(path) ? (path as Route) : '/';
}

export function navigate(to: Route, { replace = false } = {}) {
  if (to === currentRoute()) return;
  if (replace) window.history.replaceState(null, '', to);
  else window.history.pushState(null, '', to);
  window.dispatchEvent(new Event(NAVIGATE_EVENT));
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(currentRoute);

  useEffect(() => {
    const update = () => setRoute(currentRoute());
    window.addEventListener('popstate', update);
    window.addEventListener(NAVIGATE_EVENT, update);
    return () => {
      window.removeEventListener('popstate', update);
      window.removeEventListener(NAVIGATE_EVENT, update);
    };
  }, []);

  return route;
}

interface LinkProps {
  to: Route;
  className?: string;
  children: ReactNode;
}

/** Enlace interno: navega sin recargar la página. */
export function Link({ to, className, children }: LinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  }

  return (
    <a href={to} onClick={handleClick} className={className}>
      {children}
    </a>
  );
}
