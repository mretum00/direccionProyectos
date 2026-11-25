import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { Toast, type ToastData } from '@/components/ui/Toast';
import { ToastContext } from './toastContext';

/** Como mucho se ven estos avisos a la vez: si llega otro, se va el más antiguo. */
const MAX_VISIBLE = 3;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<(ToastData & { id: number })[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((toast: ToastData) => {
    const id = nextId.current++;
    setToasts((prev) => {
      // El mismo aviso dos veces seguidas (p. ej. dos intentos fallidos) se reinicia, no se duplica.
      const others = prev.filter((t) => t.title !== toast.title || t.description !== toast.description);
      return [...others, { ...toast, id }].slice(-MAX_VISIBLE);
    });
  }, []);

  const clearErrors = useCallback(() => {
    setToasts((prev) => prev.filter((t) => t.tone !== 'peligro'));
  }, []);

  const api = useMemo(() => ({ show, clearErrors }), [show, clearErrors]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {/* En un portal: un `backdrop-blur` en un padre haría que `fixed` se posicionara respecto a él. */}
      {createPortal(
        <div className="pila-toasts">
          {toasts.map(({ id, ...toast }) => (
            <ToastItem key={id} id={id} toast={toast} onDismiss={dismiss} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

function ToastItem({ id, toast, onDismiss }: { id: number; toast: ToastData; onDismiss: (id: number) => void }) {
  const close = useCallback(() => onDismiss(id), [id, onDismiss]);
  return <Toast {...toast} onClose={close} />;
}