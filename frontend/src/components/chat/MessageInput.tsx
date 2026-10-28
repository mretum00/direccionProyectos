import { useEffect, useRef, useState } from 'react';
import { Send, Square } from 'lucide-react';

const MAX_TEXTAREA_HEIGHT_PX = 120;

interface MessageInputProps {
  loading: boolean;
  /** Devuelve true si la consulta salió; si no, el texto se conserva. */
  onSend: (text: string) => boolean;
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

  // Ajusta el alto al contenido al escribir y también cuando cambia el ancho del cuadro:
  // medir con ancho 0 (al montarse) dejaría el alto fijado al máximo.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const fit = () => {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
    };
    fit();
    let width = el.clientWidth;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth !== width) {
        width = el.clientWidth;
        fit();
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [text]);

  // Al terminar la consulta, devuelve el foco para poder seguir escribiendo.
  useEffect(() => {
    if (!loading) textareaRef.current?.focus();
  }, [loading]);

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    if (onSend(trimmed)) setText('');
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
        <div className="flex items-end gap-3 bg-tarjeta border border-contraste/10 rounded-2xl pl-4 pr-2.5 py-2.5 shadow-sm shadow-black/5 focus-within:border-cyan-500/40 focus-within:ring-4 focus-within:ring-cyan-500/10 transition-all">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            readOnly={loading}
            className="flex-1 min-w-0 py-2 bg-transparent text-sm text-texto placeholder-texto-500 outline-none resize-none read-only:opacity-50"
          />
          {loading ? (
            <button
              type="button"
              onClick={onCancel}
              title="Cancelar consulta"
              aria-label="Cancelar consulta"
              className="flex items-center justify-center w-9 h-9 rounded-full bg-contraste/10 text-texto-200 hover:bg-contraste/20 transition-colors flex-shrink-0"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!text.trim()}
              aria-label="Enviar consulta"
              className="flex items-center justify-center w-9 h-9 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20 hover:from-cyan-400 hover:to-blue-500 disabled:from-contraste/5 disabled:to-contraste/5 disabled:text-texto-600 disabled:shadow-none transition-all flex-shrink-0"
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
