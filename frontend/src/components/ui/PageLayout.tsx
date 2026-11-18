import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface PageLayoutProps {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  children: ReactNode;
}

/**
 * Marco común de las páginas secundarias (Documentación, Información del sistema): mismo ancho,
 * márgenes y cabecera, para que todas queden alineadas igual.
 */
export function PageLayout({ icon: Icon, title, subtitle, children }: PageLayoutProps) {
  return (
    // Hueco de la barra de scroll siempre reservado: con o sin scroll, el contenido queda en el mismo sitio.
    <div className="h-full overflow-y-auto [scrollbar-gutter:stable]">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-9 h-9 rounded-lg bg-marca-500/10 flex items-center justify-center">
            <Icon className="w-5 h-5 text-marca-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-texto">{title}</h2>
            <p className="text-xs text-texto-500">{subtitle}</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

interface InfoRowProps {
  icon: LucideIcon;
  title: string;
  detail: ReactNode;
  /** Insignia de estado que se muestra a la derecha. */
  badge?: ReactNode;
  /** Icono del final de la fila (p. ej. "abrir" en las filas que son enlaces). */
  actionIcon?: LucideIcon;
}

/**
 * Contenido de una fila de estas listas: icono, título, detalle en pequeño, insignia e icono final.
 * El hueco del icono final se reserva aunque no haya: así las insignias quedan en la misma columna
 * en todas las páginas (Documentación e Información del sistema).
 * El contenedor (un <div> o un <a> si se puede pulsar) lleva `tarjeta fila` o `tarjeta-interactiva fila`.
 */
export function InfoRow({ icon: Icon, title, detail, badge, actionIcon: ActionIcon }: InfoRowProps) {
  return (
    <>
      <div className="w-9 h-9 rounded-md bg-contraste/5 flex items-center justify-center flex-shrink-0">
        <Icon className="w-4 h-4 text-texto-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-texto-200 truncate">{title}</div>
        <div className="flex items-center gap-2 text-[11px] text-texto-500 mt-0.5">{detail}</div>
      </div>
      {badge}
      <div className="w-4 h-4 flex-shrink-0" aria-hidden="true">
        {ActionIcon && <ActionIcon className="w-4 h-4 text-texto-500" />}
      </div>
    </>
  );
}
