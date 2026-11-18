import { useEffect } from 'react';
import { AlertCircle, AlertTriangle, Check, Info, X, type LucideIcon } from 'lucide-react';

export type ToastTone = 'exito' | 'info' | 'aviso' | 'peligro';

// Nombres de clase completos (Tailwind solo genera las clases que encuentra escritas tal cual).
const TONES: Record<ToastTone, { icon: LucideIcon; box: string; color: string; duration: number }> = {
  exito: { icon: Check, box: 'bg-exito-500/10', color: 'text-exito-400', duration: 3500 },
  info: { icon: Info, box: 'bg-marca-500/10', color: 'text-marca-400', duration: 3500 },
  aviso: { icon: AlertTriangle, box: 'bg-aviso-500/10', color: 'text-aviso-400', duration: 5000 },
  // Los errores se quedan más tiempo: hay que poder leerlos.
  peligro: { icon: AlertCircle, box: 'bg-peligro-500/10', color: 'text-peligro-400', duration: 6000 },
};

export interface ToastData {
  tone: ToastTone;
  title: string;
  /** Obligatoria: todos los avisos llevan una frase bajo el título, para que se vean iguales. */
  description: string;
  /** Milisegundos hasta que se cierra solo. Por defecto depende del tono. */
  duration?: number;
}

interface ToastProps extends ToastData {
  onClose: () => void;
}

/** Un aviso de la pila de toasts (src/toast.tsx). No se usa suelto: se lanza con `useToast().show(...)`. */
export function Toast({ tone, title, description, duration, onClose }: ToastProps) {
  const { icon: Icon, box, color, duration: toneDuration } = TONES[tone];
  const isError = tone === 'peligro';

  useEffect(() => {
    const timer = setTimeout(onClose, duration ?? toneDuration);
    return () => clearTimeout(timer);
  }, [onClose, duration, toneDuration]);

  return (
    <div role={isError ? 'alert' : 'status'} aria-live={isError ? 'assertive' : 'polite'} className="toast animate-toast-in">
      <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md ${box}`}>
        <Icon aria-hidden="true" className={`h-4 w-4 ${color}`} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-texto">{title}</p>
        <p className="mt-0.5 text-xs text-texto-400">{description}</p>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Cerrar aviso"
        className="-m-1 rounded p-1 text-texto-500 hover:bg-contraste/5 hover:text-texto-200"
      >
        <X aria-hidden="true" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
