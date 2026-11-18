import { AlertTriangle } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';

interface ConfirmationModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmationModal({ open, title, message, confirmLabel = 'Confirmar', onConfirm, onCancel }: ConfirmationModalProps) {
  return (
    <Modal open={open} onClose={onCancel} title={title} maxWidth="max-w-sm">
      <div className="space-y-4">
        <div className="flex gap-3">
          <div className="w-10 h-10 rounded-full bg-peligro-500/10 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-peligro-400" />
          </div>
          <p className="text-sm text-texto-300 pt-1.5">{message}</p>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="btn-secundario px-4 py-2 rounded-md text-sm"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            className="btn-peligro px-4 py-2 rounded-md text-sm"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
