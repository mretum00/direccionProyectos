import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot, AlertTriangle, Settings2 } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import type { ChatMessage } from '@/types/chat';
import { EvidencePanel } from '@/components/sources/EvidencePanel';
import { missingSelection } from '@/types/engine';
import { parseAnswer, stripSourceReferences, type ParsedAnswer } from '@/utils/answer';

// Estilos del markdown definidos como variantes de Tailwind sobre el contenedor:
// evita crear un objeto `components` nuevo (y castear a any) en cada render.
const MARKDOWN_CLASSES = [
  '[&_:is(p,ul,ol)]:text-texto-300 [&_:is(p,ul,ol)]:leading-relaxed [&_:is(p,ul,ol)]:text-sm',
  '[&_p]:mb-3 [&_ul]:mb-3 [&_ol]:mb-3 [&>:last-child]:mb-0',
  '[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1',
  '[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1',
  '[&_strong]:font-semibold [&_strong]:text-texto',
  // Códigos y referencias (HTM-0142, CMP-02...) en monoespaciada para distinguirlos del texto.
  '[&_code]:font-mono [&_code]:text-[0.875em] [&_code]:text-marca-300 [&_code]:bg-contraste/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded',
].join(' ');

const isSummary = (title: string) => title.toUpperCase() === 'RESUMEN';

/**
 * Respuesta con esquema: primero el resumen como texto de entrada (sin etiqueta, con la misma
 * tipografía que el resto) y debajo cada sección (CAUSAS POSIBLES, CRITICIDAD, SEGURIDAD...)
 * con su título encima del contenido. Sin recuadros ni columnas: se lee de arriba abajo.
 * Las respuestas directas, sin encabezados, se muestran como texto normal.
 */
function StructuredAnswer({ intro, sections }: ParsedAnswer) {
  return (
    <div className="space-y-6">
      {intro && (
        <div className={MARKDOWN_CLASSES}>
          <ReactMarkdown>{intro}</ReactMarkdown>
        </div>
      )}
      {sections.map(({ title, body }) =>
        isSummary(title) ? (
          <div key={title} className={MARKDOWN_CLASSES}>
            <ReactMarkdown>{body}</ReactMarkdown>
          </div>
        ) : (
          <section key={title} className="space-y-2">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-marca-400">{title}</h3>
            <div className={MARKDOWN_CLASSES}>
              <ReactMarkdown>{body}</ReactMarkdown>
            </div>
          </section>
        ),
      )}
    </div>
  );
}

interface MessageProps {
  message: ChatMessage;
}

/** Aviso destacado en ámbar cuando falta un dato (versión o tipo de usuario) para poder responder. */
function ClarificationMessage() {
  const { engineSelection, setEngineSelectorOpen } = useAppStore();
  // Si ya no falta nada (aviso antiguo), se menciona todo lo necesario.
  const missing = missingSelection(engineSelection);
  const needed = missing.length > 0 ? missing : missingSelection({ engine_version: '', profile: '' });

  return (
    <div className="flex justify-start animate-in">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-marca-500 to-marca-600 flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>

        <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm bg-amber-500/10 border border-amber-500/30 px-4 py-3 space-y-3">
          <div className="flex items-center gap-2 text-amber-400 text-[11px] font-semibold uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4" />
            Falta configurar tu consulta
          </div>
          <p className="text-sm text-texto-300 leading-relaxed">
            Para responderte necesito saber tu{' '}
            {needed.map((item, i) => (
              <span key={item}>
                {i > 0 && ' y tu '}
                <strong className="font-semibold text-amber-400">{item}</strong>
              </span>
            ))}
            . Elígelo en el selector y responderé a tu pregunta automáticamente.
          </p>
          <button
            type="button"
            onClick={() => setEngineSelectorOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-500/20 text-amber-300 text-xs font-medium hover:bg-amber-500/30 transition-colors"
          >
            <Settings2 className="w-3.5 h-3.5" />
            Abrir selector de motor
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageComponent({ message }: MessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end animate-in">
        <div className="flex items-start gap-2.5 max-w-[80%]">
          <div className="rounded-2xl rounded-tr-sm bg-marca-500/15 border border-marca-500/20 px-4 py-2.5">
            <p className="text-sm leading-relaxed text-texto-100 whitespace-pre-wrap">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-marca-500/20 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-marca-400" />
          </div>
        </div>
      </div>
    );
  }

  if (message.response?.needs_clarification) {
    return <ClarificationMessage />;
  }

  const sources = message.response?.sources;
  const hasSources = !!sources && sources.length > 0;
  const answer = parseAnswer(hasSources ? stripSourceReferences(message.content) : message.content);

  return (
    <div className="flex justify-start animate-in">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-marca-500 to-marca-600 flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>

        <div className="flex-1 min-w-0 space-y-3 pt-1">
          {answer.sections.length > 0 ? (
            <StructuredAnswer {...answer} />
          ) : (
            <div className={MARKDOWN_CLASSES}>
              <ReactMarkdown>{answer.intro}</ReactMarkdown>
            </div>
          )}

          {hasSources && <EvidencePanel sources={sources} />}
        </div>
      </div>
    </div>
  );
}

// Los mensajes ya enviados no cambian: memo evita re-renderizar (y re-parsear
// el markdown) de todo el historial cada vez que cambia la lista de conversaciones.
export const Message = memo(MessageComponent);
