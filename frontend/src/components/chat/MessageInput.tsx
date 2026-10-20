import { useEffect, useRef, useState } from 'react';
import { Send, Square } from 'lucide-react';

const MAX_TEXTAREA_HEIGHT_PX = 120;

interface MessageInputProps {
  loading: boolean;
  onSend: (text: string) => void;
  onCancel: () => void;
  placeholder?: string;
}

export function MessageInput({
  loading,
  onSend,
  onCancel,
  placeholder = 'Escribe tu consulta técnica…',
}: MessageInputProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
  }, [text]);

  // Al terminar la consulta, devuelve el foco para poder seguir escribiendo.
  useEffect(() => {
    if (!loading) textareaRef.current?.focus();
  }, [loading]);

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setText('');
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="flex-shrink-0 border-t border-contraste/5 bg-panel/80 backdrop-blur-sm px-4 py-3">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-tarjeta border border-contraste/10 rounded-xl px-3 py-2 focus-within:border-cyan-500/30 transition-colors">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            readOnly={loading}
            className="flex-1 bg-transparent text-sm text-texto placeholder-texto-500 outline-none resize-none read-only:opacity-50"
          />
          {loading ? (
            <button
              type="button"
              onClick={onCancel}
              title="Cancelar consulta"
              aria-label="Cancelar consulta"
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-contraste/10 text-texto-200 hover:bg-contraste/20 transition-colors flex-shrink-0"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!text.trim()}
              aria-label="Enviar consulta"
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-500 text-white disabled:bg-contraste/5 disabled:text-texto-600 hover:bg-cyan-400 transition-colors flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-[10px] text-texto-600 text-center mt-1.5">
          Enter para enviar · Shift+Enter para salto de línea
        </p>
      </div>
    </div>
  );
}
