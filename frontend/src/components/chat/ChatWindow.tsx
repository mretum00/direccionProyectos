import { useEffect, useMemo, useRef, useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { useChat } from '@/hooks/useChat';
import { Message } from './Message';
import { MessageInput } from './MessageInput';
import { ThinkingIndicator } from './ThinkingIndicator';
import { WelcomeScreen } from './WelcomeScreen';
import { ChatError } from './ChatError';
import { isSelectionComplete } from '@/types/engine';
import { ContextPanel } from '@/components/engine/ContextPanel';

export function ChatWindow() {
  const { conversations, activeConversationId, engineSelection, engineSelectorOpen, setEngineSelectorOpen } = useAppStore();
  // Única instancia de useChat: comparte loading/error con el input y el indicador.
  const { loading, error, sendMessage, retry, cancel } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  const conversation = useMemo(
    () => (activeConversationId ? conversations.find((c) => c.id === activeConversationId) ?? null : null),
    [conversations, activeConversationId],
  );
  const messages = conversation?.messages;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading, error]);

  const ready = isSelectionComplete(engineSelection);
  // Pregunta que el usuario quiso enviar sin tener configurada la consulta: se envía sola al configurarla.
  const pending = useRef<{ text: string; fromInput: boolean } | null>(null);
  // Al cambiarla se vacía el campo de texto (cuando la pregunta pendiente salió de él).
  const [inputKey, setInputKey] = useState(0);

  useEffect(() => {
    if (ready && pending.current) {
      const { text, fromInput } = pending.current;
      pending.current = null;
      void sendMessage(text);
      if (fromInput) setInputKey((k) => k + 1);
    } else if (!ready && !engineSelectorOpen) {
      pending.current = null; // el selector se cerró sin configurar: se descarta
    }
  }, [ready, engineSelectorOpen, sendMessage]);

  /**
   * Sin versión y tipo de usuario no se envía: se abre el selector explicando por qué y la pregunta
   * queda en espera (el texto del campo no se borra hasta que se envíe de verdad).
   */
  function submit(text: string, fromInput: boolean): boolean {
    if (!ready) {
      pending.current = { text, fromInput };
      setEngineSelectorOpen(true, true);
      return false;
    }
    void sendMessage(text);
    return true;
  }

  const hasMessages = !!messages && messages.length > 0;

  return (
    <div className="flex flex-1 min-w-0 h-full overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
            {!hasMessages && !loading && <WelcomeScreen onSuggestion={(text) => submit(text, false)} />}

            {messages?.map((msg) => (
              <Message key={msg.id} message={msg} />
            ))}

            {loading && <ThinkingIndicator />}

            {error && <ChatError message={error} onRetry={retry} />}
          </div>
        </div>
        <MessageInput key={inputKey} ready={ready} loading={loading} onSend={(text) => submit(text, true)} onCancel={cancel} />
      </div>
      <ContextPanel conversation={conversation} />
    </div>
  );
}
