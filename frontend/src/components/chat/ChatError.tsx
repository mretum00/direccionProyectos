import { AlertCircle, RefreshCw } from 'lucide-react';

interface ChatErrorProps {
  message: string;
  onRetry: () => void;
}

export function ChatError({ message, onRetry }: ChatErrorProps) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 flex items-center gap-3">
      <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
      <div className="flex-1">
        <p className="text-sm text-red-300">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-red-500/15 text-red-400 text-xs font-medium hover:bg-red-500/25 transition-colors flex-shrink-0"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Reintentar
      </button>
    </div>
  );
}
