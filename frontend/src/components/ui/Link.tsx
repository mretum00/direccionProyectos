
import type { MouseEvent, ReactNode } from 'react';
import { navigate, type Route } from '../../router';

interface LinkProps {
  to: Route;
  className?: string;
  children: ReactNode;
}

/** Enlace interno que navega sin recargar la página. */
export function Link({ to, className, children }: LinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    event.preventDefault();
    navigate(to);
  }

  return (
    <a href={to} onClick={handleClick} className={className}>
      {children}
    </a>
  );
}
