import { useEffect, useRef } from 'react';
import { useAppStore } from '@/store/appStore';
import { useChat } from '@/hooks/useChat';
import { Message } from './Message';
import { MessageInput } from './MessageInput';
import { ThinkingIndicator } from './ThinkingIndicator';
import { WelcomeScreen } from './WelcomeScreen';
import { ChatError } from './ChatError';
import { ContextPanel } from '@/components/engine/ContextPanel';
import type { Conversation } from '@/types/conversation';

export function ChatWindow() {
  const store = useAppStore();
  const { loading, error, sendMessage, retry } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  const conversation: Conversation | null = store.activeConversationId
    ? store.conversations.find((c) => c.id === store.activeConversationId) ?? null
    : null;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation?.messages, loading]);

  const hasMessages = conversation && conversation.messages.length > 0;

  function handleClarificationSubmit(answers: Record<string, string>) {
    const text = Object.values(answers).join('; ');
    sendMessage(text, answers);
  }

  return (
    <div className="flex flex-1 min-w-0">
      <div className="flex-1 flex flex-col min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
            {!hasMessages && !loading && (
              <WelcomeScreen onSuggestion={(s) => sendMessage(s)} />
            )}

            {hasMessages &&
              conversation.messages.map((msg) => (
                <Message
                  key={msg.id}
                  message={msg}
                  onClarificationSubmit={handleClarificationSubmit}
                />
              ))}

            {loading && <ThinkingIndicator visible={loading} />}

            {error && (
              <ChatError
                message={error.message}
                onRetry={retry}
              />
            )}
          </div>
        </div>

        <MessageInput />
      </div>

      <ContextPanel conversation={conversation} />
    </div>
  );
}
