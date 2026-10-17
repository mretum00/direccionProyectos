import { useEffect, useMemo, useRef } from 'react';
import { useAppStore } from '@/store/appStore';
import { useChat } from '@/hooks/useChat';
import { Message } from './Message';
import { MessageInput } from './MessageInput';
import { ThinkingIndicator } from './ThinkingIndicator';
import { WelcomeScreen } from './WelcomeScreen';
import { ChatError } from './ChatError';
import { ContextPanel } from '@/components/engine/ContextPanel';

export function ChatWindow() {
  const { conversations, activeConversationId } = useAppStore();
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

  const hasMessages = !!messages && messages.length > 0;

  return (
    <div className="flex flex-1 min-w-0 h-full overflow-hidden">
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
            {!hasMessages && !loading && <WelcomeScreen onSuggestion={sendMessage} />}

            {messages?.map((msg) => (
              <Message key={msg.id} message={msg} />
            ))}

            {loading && <ThinkingIndicator />}

            {error && <ChatError message={error.message} onRetry={retry} />}
          </div>
        </div>
        <MessageInput loading={loading} onSend={sendMessage} onCancel={cancel} />
      </div>
      <ContextPanel conversation={conversation} />
    </div>
  );
}
