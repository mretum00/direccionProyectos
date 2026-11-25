import { memo, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot, Settings2, CircleHelp, SearchX } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import type { AnswerMeta, ChatMessage, ClarificationKind } from '@/types/chat';
import { EvidencePanel } from '@/components/sources/EvidencePanel';
import { Callout, CalloutButton } from '@/components/ui/Callout';
import { ReasoningSteps } from './ReasoningSteps';
import { ClaimsCheck, SafetyAlerts, SufficiencyCheck } from './Checks';
import { parseAnswer, stripSourceReferences, type ParsedAnswer } from '@/utils/answer';

// Estilos del markdown definidos como variantes de Tailwind sobre el contenedor:
// evita crear un objeto `components` nuevo (y castear a any) en cada render.
const MARKDOWN_CLASSES = [
  '[&_:is(p,ul,ol)]:text-texto-300 [&_:is(p,ul,ol)]:leading-relaxed [&_:is(p,ul,ol)]:text-sm',
  '[&_p]:mb-3 [&_ul]:mb-3 [&_ol]:mb-3 [&>:last-child]:mb-0',
  '[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1',
  '[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1',
  '[&_strong]:font-semibold [&_strong]:text-texto',
  // Citas literales de la documentación: mismo estilo que en las comprobaciones automáticas.
  '[&_blockquote]:border-l-2 [&_blockquote]:border-contraste/20 [&_blockquote]:pl-3 [&_blockquote]:my-2 [&_blockquote_p]:text-xs [&_blockquote_p]:italic [&_blockquote_p]:text-texto-400',
  // Códigos y referencias (HTM-0142, CMP-02...) en monoespaciada para distinguirlos del texto.
  '[&_code]:font-mono [&_code]:text-[0.875em] [&_code]:text-marca-300 [&_code]:bg-contraste/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded',
].join(' ');

function Markdown({ children }: { children: string }) {
  return (
    <div className={MARKDOWN_CLASSES}>
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  );
}

const isSummary = (title: string) => title.toUpperCase() === 'RESUMEN';

/**
 * Respuesta con esquema: primero el resumen como texto de entrada (sin etiqueta) y debajo
 * cada sección (CAUSAS POSIBLES, CRITICIDAD, SEGURIDAD...) con su título encima.
 * Las respuestas directas, sin encabezados, se muestran como texto normal.
 */
function StructuredAnswer({ intro, sections }: ParsedAnswer) {
  if (sections.length === 0) return <Markdown>{intro}</Markdown>;
  return (
    <div className="space-y-6">
      {intro && <Markdown>{intro}</Markdown>}
      {sections.map(({ title, body }) =>
        isSummary(title) ? (
          <Markdown key={title}>{body}</Markdown>
        ) : (
          <section key={title} className="space-y-2">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-marca-400">{title}</h3>
            <Markdown>{body}</Markdown>
          </section>
        ),
      )}
    </div>
  );
}

// --- Aclaraciones ---------------------------------------------------------------------------

const CLARIFICATIONS: Record<ClarificationKind, { title: string; action?: string }> = {
  engine_version: { title: 'Elige la versión del motor', action: 'Abrir selector de motor' },
  version_mismatch: { title: 'La versión no coincide', action: 'Cambiar versión seleccionada' },
  version_comparison: { title: 'Necesito una sola versión', action: 'Elegir una versión' },
  technical: { title: 'Necesito una aclaración' },
};

/** El asistente necesita un dato antes de buscar. Si es la versión, el botón abre el selector. */
function Clarification({ content, kind = 'engine_version' }: { content: string; kind?: ClarificationKind }) {
  const { setEngineSelectorOpen } = useAppStore();
  const { title, action } = CLARIFICATIONS[kind];
  return (
    <Callout tone="info" icon={CircleHelp} title={title}>
      <Markdown>{content}</Markdown>
      {action && (
        <CalloutButton tone="info" icon={Settings2} onClick={() => setEngineSelectorOpen(true)}>
          {action}
        </CalloutButton>
      )}
    </Callout>
  );
}

// --- Estructura común de los mensajes del asistente ------------------------------------------

/** Avatar del asistente y columna de contenido: igual para todos sus mensajes. */
function AssistantRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-start animate-in">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="icono-marca w-8 h-8 rounded-full">
          <Bot className="w-4 h-4 text-sobre-marca" />
        </div>
        <div className="flex-1 min-w-0 space-y-4 pt-1">{children}</div>
      </div>
    </div>
  );
}

type AssistantKind = 'clarification' | 'no_evidence' | 'answer';

function kindOf(response?: AnswerMeta): AssistantKind {
  if (response?.needs_clarification) return 'clarification';
  if (response?.evidence_status === 'insufficient' && !response.sources?.length) return 'no_evidence';
  return 'answer';
}

/**
 * Mensaje del asistente. Sea cual sea el tipo, el orden es siempre el mismo:
 *   1. avisos de seguridad
 *   2. pasos seguidos (si ha llegado a buscar)
 *   3. contenido: aclaración, aviso de falta de evidencia o respuesta
 *   4. comprobaciones automáticas (cobertura y revisión de afirmaciones)
 *   5. fuentes
 */
function AssistantMessage({ message }: { message: ChatMessage }) {
  const response = message.response;
  const kind = kindOf(response);
  const sources = response?.sources ?? [];
  const steps = response?.steps ?? [];

  return (
    <AssistantRow>
      <SafetyAlerts alerts={response?.safety_alerts ?? []} />

      {steps.length > 0 && <ReasoningSteps steps={steps} />}

      {kind === 'clarification' && <Clarification content={message.content} kind={response?.clarification_kind} />}

      {kind === 'no_evidence' && (
        <Callout tone="warning" icon={SearchX} title="Sin evidencia suficiente">
          <Markdown>{message.content}</Markdown>
        </Callout>
      )}

      {kind === 'answer' && (
        <StructuredAnswer {...parseAnswer(sources.length > 0 ? stripSourceReferences(message.content) : message.content)} />
      )}

      {/* Sin evidencia, el propio aviso ya explica qué datos faltan: no se repite la cobertura. */}
      {kind === 'answer' && (
        <>
          <SufficiencyCheck sufficiency={response?.evidence_sufficiency} />
          <ClaimsCheck verification={response?.claim_verification} sources={sources} />
        </>
      )}

      {sources.length > 0 && <EvidencePanel sources={sources} />}
    </AssistantRow>
  );
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end animate-in">
      <div className="flex items-start gap-2.5 max-w-[80%]">
        <div className="rounded-2xl rounded-tr-sm bg-marca-500/15 border border-marca-500/20 px-4 py-2.5">
          <p className="text-sm leading-relaxed text-texto-100 whitespace-pre-wrap">{content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-marca-500/20 flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-marca-400" />
        </div>
      </div>
    </div>
  );
}

function MessageComponent({ message }: { message: ChatMessage }) {
  return message.role === 'user' ? <UserMessage content={message.content} /> : <AssistantMessage message={message} />;
}

// Los mensajes ya enviados no cambian: memo evita re-renderizar (y re-parsear
// el markdown) de todo el historial cada vez que cambia la lista de conversaciones.
export const Message = memo(MessageComponent);
