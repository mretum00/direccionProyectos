import { User, Bot } from 'lucide-react';
import type { ChatMessage } from '@/types/chat';
import { ResponseSectionsView } from './ResponseSections';
import { EvidenceStatus } from './EvidenceStatus';
import { ClarificationPanel } from './ClarificationPanel';
import { EvidencePanel } from '@/components/sources/EvidencePanel';
import { DiscardedSources } from '@/components/sources/DiscardedSources';

interface MessageProps {
  message: ChatMessage;
  onClarificationSubmit: (answers: Record<string, string>) => void;
}

export function Message({ message, onClarificationSubmit }: MessageProps) {
  const isUser = message.role === 'user';
  const response = message.response;

  if (isUser) {
    return (
      <div className="flex justify-end animate-in fade-in duration-300">
        <div className="flex items-start gap-2.5 max-w-[80%]">
          <div className="rounded-2xl rounded-tr-sm bg-cyan-500/15 border border-cyan-500/20 px-4 py-2.5">
            <p className="text-sm text-gray-100 whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-cyan-400" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start animate-in fade-in duration-300">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1 min-w-0 space-y-3">
          {/* Evidence status (if not insufficient — that gets a special block) */}
          {response?.evidence_status && response.evidence_status !== 'insufficient' && (
            <EvidenceStatus
              status={response.evidence_status}
              confidence={response.confidence}
              documentsConsulted={response.documents_consulted}
            />
          )}

          {/* Insufficient evidence special block */}
          {response?.evidence_status === 'insufficient' && (
            <EvidenceStatus
              status={response.evidence_status}
              documentsConsulted={response.documents_consulted}
            />
          )}

          {/* Clarification panel */}
          {response?.needs_clarification && response.clarification && (
            <ClarificationPanel
              clarification={response.clarification}
              onSubmit={onClarificationSubmit}
            />
          )}

          {/* Response sections / content */}
          <ResponseSectionsView
            sections={response?.sections}
            interpretedQuery={response?.interpreted_query}
            detectedDtc={response?.detected_dtc}
            content={response?.message.content ?? message.content}
          />

          {/* Discarded sources */}
          {response?.discarded_sources && response.discarded_sources.length > 0 && (
            <DiscardedSources sources={response.discarded_sources} />
          )}

          {/* Evidence / sources */}
          {response?.sources && response.sources.length > 0 && (
            <EvidencePanel sources={response.sources} />
          )}
        </div>
      </div>
    </div>
  );
}
