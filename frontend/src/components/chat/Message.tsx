import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot } from 'lucide-react';
import type { ChatMessage } from '@/types/chat';
import { EvidencePanel } from '@/components/sources/EvidencePanel';

// Estilos del markdown definidos como variantes de Tailwind sobre el contenedor:
// evita crear un objeto `components` nuevo (y castear a any) en cada render.
const MARKDOWN_CLASSES = [
  '[&_h3]:text-cyan-400 [&_h3]:font-bold [&_h3]:text-xs [&_h3]:tracking-wider [&_h3]:uppercase [&_h3]:mt-6 [&_h3]:mb-2',
  '[&_p]:text-texto-300 [&_p]:leading-relaxed [&_p]:mb-3 [&_p]:text-sm md:[&_p]:text-base',
  '[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-4 [&_ul]:text-texto-300 [&_ul]:space-y-1 [&_ul]:text-sm md:[&_ul]:text-base',
  '[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-4 [&_ol]:text-texto-300 [&_ol]:space-y-1 [&_ol]:text-sm md:[&_ol]:text-base',
  '[&_strong]:font-semibold [&_strong]:text-texto',
].join(' ');

// Sección "### FUENTE" escrita por el LLM (o guardada en conversaciones antiguas):
// se oculta porque las fuentes se muestran como fichas debajo de la respuesta.
const SECCION_FUENTE = /\n#{1,6}\s*FUENTES?\b[\s\S]*$/i;

interface MessageProps {
  message: ChatMessage;
}

function MessageComponent({ message }: MessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end animate-in fade-in duration-300">
        <div className="flex items-start gap-2.5 max-w-[80%]">
          <div className="rounded-2xl rounded-tr-sm bg-cyan-500/15 border border-cyan-500/20 px-4 py-2.5">
            <p className="text-sm text-texto-100 whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-cyan-400" />
          </div>
        </div>
      </div>
    );
  }

  const sources = message.response?.sources;
  const hasSources = !!sources && sources.length > 0;
  const content = hasSources ? message.content.replace(SECCION_FUENTE, '') : message.content;

  return (
    <div className="flex justify-start animate-in fade-in duration-300">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>

        <div className="flex-1 min-w-0 space-y-3 pt-1">
          <div className={`max-w-none ${MARKDOWN_CLASSES}`}>
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>

          {hasSources && <EvidencePanel sources={sources} />}
        </div>
      </div>
    </div>
  );
}

// Los mensajes ya enviados no cambian: memo evita re-renderizar (y re-parsear
// el markdown) de todo el historial cada vez que cambia la lista de conversaciones.
export const Message = memo(MessageComponent);
