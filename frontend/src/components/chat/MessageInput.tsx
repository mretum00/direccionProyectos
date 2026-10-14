import { useRef, useState, useEffect } from 'react';
import { Send, Paperclip, Loader2 } from 'lucide-react';
import { useChat } from '@/hooks/useChat';

const ENABLE_UPLOAD = import.meta.env.VITE_ENABLE_DOCUMENT_UPLOAD === 'true';

interface MessageInputProps {
  onClarificationSubmit?: (answers: Record<string, string>) => void;
  placeholder?: string;
}

export function MessageInput({ onClarificationSubmit, placeholder = 'Escribe tu consulta técnica…' }: MessageInputProps) {
  const { sendMessage, loading } = useChat();
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  function handleSubmit() {
    if (!text.trim() || loading) return;
    if (onClarificationSubmit) {
      onClarificationSubmit({ text: text.trim() });
    } else {
      sendMessage(text.trim());
    }
    setText('');
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="flex-shrink-0 border-t border-white/5 bg-[#0d0d0f]/80 backdrop-blur-sm px-4 py-3">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-[#151518] border border-white/10 rounded-xl px-3 py-2 focus-within:border-cyan-500/30 transition-colors">
          {ENABLE_UPLOAD && (
            <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded-md hover:bg-white/5">
              <Paperclip className="w-4 h-4" />
            </button>
          )}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={loading}
            className="flex-1 bg-transparent text-sm text-white placeholder-gray-500 outline-none resize-none disabled:opacity-50"
          />
          <button
            onClick={handleSubmit}
            disabled={!text.trim() || loading}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-500 text-white disabled:bg-white/5 disabled:text-gray-600 hover:bg-cyan-400 transition-colors flex-shrink-0"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[10px] text-gray-600 text-center mt-1.5">
          Enter para enviar · Shift+Enter para salto de línea
        </p>
      </div>
    </div>
  );
}
