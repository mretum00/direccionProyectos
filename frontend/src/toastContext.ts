
import { createContext } from 'react';
import type { ToastData } from '@/components/ui/Toast';

export interface ToastApi {
  show: (toast: ToastData) => void;
  clearErrors: () => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
