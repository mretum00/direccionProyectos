import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

/**
 * Tonos comunes a todos los avisos del chat. Siempre significan lo mismo:
 * - info:    el asistente necesita algo del usuario (aclaraciones).
 * - success: comprobación superada.
 * - warning: respuesta limitada o sin evidencia suficiente.
 * - danger:  riesgo para la seguridad o información contradictoria.
 */
export type Tone = 'info' | 'success' | 'warning' | 'danger';

const TONES: Record<Tone, { box: string; icon: string; title: string; chip: string; button: string }> = {
  info: {
    box: 'border-marca-500/30 bg-marca-500/5',
    icon: 'text-marca-400',
    title: 'text-marca-300',
    chip: 'text-marca-300 bg-marca-500/10 border-marca-500/20',
    button: 'bg-marca-500/15 text-marca-300 hover:bg-marca-500/25',
  },
  success: {
    box: 'border-exito-500/25 bg-exito-500/5',
    icon: 'text-exito-400',
    title: 'text-exito-300',
    chip: 'text-exito-300 bg-exito-500/10 border-exito-500/20',
    button: 'bg-exito-500/15 text-exito-300 hover:bg-exito-500/25',
  },
  warning: {
    box: 'border-aviso-500/30 bg-aviso-500/5',
    icon: 'text-aviso-400',
    title: 'text-aviso-300',
    chip: 'text-aviso-300 bg-aviso-500/10 border-aviso-500/20',
    button: 'bg-aviso-500/15 text-aviso-300 hover:bg-aviso-500/25',
  },
  danger: {
    box: 'border-peligro-500/40 bg-peligro-500/10',
    icon: 'text-peligro-400',
    title: 'text-peligro-300',
    chip: 'text-peligro-300 bg-peligro-500/10 border-peligro-500/20',
    button: 'bg-peligro-500/15 text-peligro-300 hover:bg-peligro-500/25',
  },
};

/** Etiqueta pequeña de estado ("Respaldado", "No localizado"...). */
export function StatusChip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border whitespace-nowrap ${TONES[tone].chip}`}>
      {children}
    </span>
  );
}

/** Botón de acción dentro de un aviso, con el color de su tono. */
export function CalloutButton({
  tone,
  icon: Icon,
  onClick,
  children,
}: {
  tone: Tone;
  icon?: LucideIcon;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${TONES[tone].button}`}
    >
      {Icon && <Icon className="w-3.5 h-3.5" />}
      {children}
    </button>
  );
}

interface CalloutProps {
  tone: Tone;
  icon: LucideIcon;
  title: string;
  /** Etiqueta de estado a la derecha del título. */
  chip?: ReactNode;
  children?: ReactNode;
  role?: 'alert' | 'note' | 'status';
  'aria-label'?: string;
}

/**
 * Recuadro de aviso del chat: icono y título en mayúsculas en la cabecera y el
 * contenido debajo. Todos los avisos (seguridad, aclaraciones, sin evidencia y
 * comprobaciones automáticas) lo usan para que se vean iguales.
 */
export function Callout({ tone, icon: Icon, title, chip, children, role = 'note', ...rest }: CalloutProps) {
  const styles = TONES[tone];
  return (
    <aside
      role={role}
      aria-live={role === 'alert' ? 'assertive' : undefined}
      aria-label={rest['aria-label'] ?? title}
      className={`rounded-xl border px-4 py-3 space-y-2.5 ${styles.box}`}
    >
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 shrink-0 ${styles.icon}`} />
        <h3 className={`text-[11px] font-bold uppercase tracking-wider ${styles.title}`}>{title}</h3>
        {chip && <span className="ml-auto">{chip}</span>}
      </div>
      {children}
    </aside>
  );
}
