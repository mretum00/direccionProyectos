import { AlertCircle, RefreshCw } from 'lucide-react';

interface ChatErrorProps {
  message: string;
  onRetry: () => void;
}

export function ChatError({ message, onRetry }: ChatErrorProps) {
  return (
    <div className="alerta-peligro items-center">
      <AlertCircle className="w-5 h-5 text-peligro-400 flex-shrink-0" />
      <div className="flex-1">
        <p>{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-peligro-500/15 text-peligro-400 text-xs font-medium hover:bg-peligro-500/25 transition-colors flex-shrink-0"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Reintentar
      </button>
    </div>
  );
}
