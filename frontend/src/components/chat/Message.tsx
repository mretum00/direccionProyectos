import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot, AlertTriangle, Settings2, CheckCircle2, AlertCircle, CircleHelp } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import type { ChatMessage, SafetyAlert, ClaimVerification, ClaimCheck, EvidenceSufficiency, RequestedEvidenceStatus, Source, ClarificationKind } from '@/types/chat';
import { EvidencePanel } from '@/components/sources/EvidencePanel';
import { ReasoningSteps } from './ReasoningSteps';
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

/**
 * Aviso destacado en ámbar cuando el backend no ha podido responder porque falta la versión o no
 * la reconoce. El texto es el del backend (explica qué falta); el botón abre el selector.
 */
function ClarificationMessage({
  content,
  kind = 'engine_version',
}: {
  content: string;
  kind?: ClarificationKind;
}) {
  const { setEngineSelectorOpen } = useAppStore();
  const needsEngineSelector =
    kind === 'engine_version' || kind === 'version_mismatch' || kind === 'version_comparison';
  const clarificationTitle =
    kind === 'engine_version'
      ? 'Falta configurar tu consulta'
      : kind === 'version_mismatch'
        ? 'La versión no coincide'
        : kind === 'version_comparison'
          ? 'Necesito una sola versión'
          : 'Necesito una aclaración';
  const selectorLabel =
    kind === 'version_mismatch'
      ? 'Cambiar versión seleccionada'
      : kind === 'version_comparison'
        ? 'Elegir una versión'
        : 'Abrir selector de motor';

  return (
    <div className="flex justify-start animate-in">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="icono-marca w-8 h-8 rounded-full">
          <Bot className="w-4 h-4 text-sobre-marca" />
        </div>

        <div className="flex-1 min-w-0 rounded-2xl rounded-tl-sm bg-aviso-500/10 border border-aviso-500/30 px-4 py-3 space-y-3">
          <div className="flex items-center gap-2 text-aviso-400 text-[11px] font-semibold uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4" />
            {clarificationTitle}
          </div>
          <p className="text-sm text-texto-300 leading-relaxed">{content}</p>
          {needsEngineSelector && (
            <button
              type="button"
              onClick={() => setEngineSelectorOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-aviso-500/20 text-aviso-300 text-xs font-medium hover:bg-aviso-500/30 transition-colors"
            >
              <Settings2 className="w-3.5 h-3.5" />
              {selectorLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SafetyAlertsPanel({ alerts }: { alerts: SafetyAlert[] }) {
  if (alerts.length === 0) return null;

  return (
    <div className="space-y-2" aria-label="Avisos de seguridad">
      {alerts.map((alert) => {
        const critical = alert.severity === 'critical';
        return (
          <aside
            key={alert.code}
            role={critical ? 'alert' : 'note'}
            aria-live={critical ? 'assertive' : 'polite'}
            className={
              critical
                ? 'rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-100'
                : 'rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-amber-100'
            }
          >
            <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wide">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {alert.title}
            </div>
            <p className="text-sm leading-relaxed">{alert.message}</p>
          </aside>
        );
      })}
    </div>
  );
}

function EvidenceSufficiencyPanel({ sufficiency }: { sufficiency?: EvidenceSufficiency }) {
  if (!sufficiency || sufficiency.status === 'not_run') return null;

  const unavailable = sufficiency.status === 'unavailable';
  const sufficient = sufficiency.status === 'sufficient';
  const labels: Record<RequestedEvidenceStatus, string> = {
    supported: 'Respaldado',
    not_found: 'No localizado',
    uncertain: 'No concluyente',
    conflicting: 'Información contradictoria',
  };
  const classes: Record<RequestedEvidenceStatus, string> = {
    supported: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
    not_found: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
    uncertain: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
    conflicting: 'text-red-300 bg-red-500/10 border-red-500/20',
  };
  const heading = unavailable
    ? 'Comprobación de cobertura no disponible'
    : sufficient
      ? 'Cobertura documental completa'
      : sufficiency.status === 'partial'
        ? 'Cobertura documental parcial'
        : 'Información no documentada';
  const summary = unavailable
    ? 'No se pudo comprobar si los extractos contienen los datos solicitados. Por precaución, no se ha generado una respuesta técnica.'
    : `${sufficiency.requested_items.filter((item) => item.status === 'supported').length} de ${sufficiency.requested_items.length} datos solicitados tienen una cita localizada en los fragmentos recuperados.`;

  return (
    <aside
      className={`rounded-xl border px-4 py-3 space-y-3 ${
        sufficient
          ? 'border-emerald-500/25 bg-emerald-500/5'
          : 'border-amber-500/30 bg-amber-500/5'
      }`}
      aria-label="Comprobación de suficiencia documental"
    >
      <div className="flex items-center gap-2">
        {sufficient ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-300 shrink-0" />
        ) : (
          <AlertCircle className="h-4 w-4 text-amber-300 shrink-0" />
        )}
        <h3 className="text-xs font-bold uppercase tracking-wide text-texto-100">{heading}</h3>
      </div>
      <p className="text-xs text-texto-300 leading-relaxed">{summary}</p>
      {sufficiency.requested_items.length > 0 && (
        <div className="space-y-2">
          {sufficiency.requested_items.map((item, index) => (
            <div key={`${index}-${item.item}`} className="rounded-lg border border-contraste/40 bg-fondo/50 p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-texto-100">{item.item}</span>
                <span className={`text-[10px] px-2 py-1 rounded-full border ${classes[item.status]}`}>
                  {labels[item.status]}
                </span>
              </div>
              {item.evidence_excerpt && (
                <blockquote className="border-l-2 border-emerald-500/40 pl-3 text-xs text-texto-300">
                  “{item.evidence_excerpt}”
                </blockquote>
              )}
            </div>
          ))}
        </div>
      )}
      <p className="text-[11px] text-texto-400 leading-relaxed">
        La comprobación es automática y orientativa. La existencia de una cita literal no demuestra por sí sola que la interpretación sea correcta; contrasta siempre los datos técnicos con la documentación original.
      </p>
    </aside>
  );
}

function ClaimVerificationPanel({
  verification,
  sources,
}: {
  verification?: ClaimVerification;
  sources?: Source[];
}) {
  if (!verification || verification.status === 'not_run' || verification.status === 'no_claims') {
    return null;
  }

  const reviewed = verification.status === 'reviewed';
  const unavailable = verification.status === 'unavailable';
  const summary = unavailable
    ? 'No se pudo completar la revisión automática.'
    : `${verification.claims_supported} de ${verification.claims_total} afirmaciones tienen un extracto localizado que el revisor considera compatible.`;

  const statusLabels: Record<ClaimCheck['status'], string> = {
    supported: 'Respaldo localizado',
    conflicting: 'Posible contradicción',
    not_found: 'Sin respaldo localizado',
    uncertain: 'Resultado no concluyente',
    unverified: 'No verificada',
  };

  const statusClasses: Record<ClaimCheck['status'], string> = {
    supported: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
    conflicting: 'text-red-300 bg-red-500/10 border-red-500/20',
    not_found: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
    uncertain: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
    unverified: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
  };

  return (
    <aside
      className={`rounded-xl border px-4 py-3 space-y-3 ${
        reviewed
          ? 'border-emerald-500/25 bg-emerald-500/5'
          : 'border-amber-500/30 bg-amber-500/5'
      }`}
      aria-label="Revisión automática de afirmaciones"
    >
      <div className="flex items-center gap-2">
        {reviewed ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-300 shrink-0" />
        ) : unavailable ? (
          <CircleHelp className="h-4 w-4 text-amber-300 shrink-0" />
        ) : (
          <AlertCircle className="h-4 w-4 text-amber-300 shrink-0" />
        )}
        <h3 className="text-xs font-bold uppercase tracking-wide text-texto-100">
          Revisión automática de afirmaciones
        </h3>
        <span className={`ml-auto text-[10px] px-2 py-1 rounded-full border ${reviewed ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20' : 'text-amber-300 bg-amber-500/10 border-amber-500/20'}`}>
          {reviewed ? 'Respaldo localizado' : unavailable ? 'No disponible' : 'Requiere revisión'}
        </span>
      </div>

      <p className="text-xs text-texto-300 leading-relaxed">{summary}</p>

      {verification.claims.length > 0 && (
        <div className="space-y-2">
          {verification.claims.map((claim, index) => {
            const documents = (claim.source_ids ?? [])
              .map((id) => sources?.find((source) => source.id === id)?.document)
              .filter((name): name is string => Boolean(name));
            return (
              <div key={`${index}-${claim.claim}`} className="rounded-lg border border-contraste/40 bg-fondo/50 p-3 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-texto-100">{claim.claim}</span>
                  <span className={`text-[10px] px-2 py-1 rounded-full border ${statusClasses[claim.status]}`}>
                    {statusLabels[claim.status]}
                  </span>
                </div>
                {claim.evidence_excerpt && (
                  <blockquote className="border-l-2 border-emerald-500/40 pl-3 text-xs text-texto-300">
                    “{claim.evidence_excerpt}”
                  </blockquote>
                )}
                {documents.length > 0 && (
                  <p className="text-[11px] text-texto-400">Fuentes: {Array.from(new Set(documents)).join(', ')}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p className="text-[11px] text-texto-400 leading-relaxed">
        Esta revisión automática es orientativa y analiza hasta 12 afirmaciones identificadas; puede no detectar todas. Localizar un extracto coincidente no demuestra por sí solo que toda la afirmación sea correcta. En procedimientos críticos, contrasta siempre la documentación y solicita revisión cualificada.
      </p>
    </aside>
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

  const safetyAlerts = message.response?.safety_alerts ?? [];

  if (message.response?.needs_clarification) {
    return (
      <div className="space-y-3">
        <SafetyAlertsPanel alerts={safetyAlerts} />
        <ClarificationMessage
          content={message.content}
          kind={message.response?.clarification_kind}
        />
      </div>
    );
  }

  const sources = message.response?.sources;
  const hasSources = !!sources && sources.length > 0;
  const answer = parseAnswer(hasSources ? stripSourceReferences(message.content) : message.content);

  return (
    <div className="flex justify-start animate-in">
      <div className="flex items-start gap-2.5 max-w-[88%] w-full">
        <div className="icono-marca w-8 h-8 rounded-full">
          <Bot className="w-4 h-4 text-sobre-marca" />
        </div>

        <div className="flex-1 min-w-0 space-y-3 pt-1">
          <SafetyAlertsPanel alerts={safetyAlerts} />
          {message.response?.steps && message.response.steps.length > 0 && (
            <div className="pb-3 border-b border-contraste/5">
              <ReasoningSteps steps={message.response.steps} />
            </div>
          )}
          {answer.sections.length > 0 ? (
            <StructuredAnswer {...answer} />
          ) : (
            <div className={MARKDOWN_CLASSES}>
              <ReactMarkdown>{answer.intro}</ReactMarkdown>
            </div>
          )}

          <EvidenceSufficiencyPanel sufficiency={message.response?.evidence_sufficiency} />
          <ClaimVerificationPanel
            verification={message.response?.claim_verification}
            sources={sources}
          />
          {hasSources && <EvidencePanel sources={sources} />}
        </div>
      </div>
    </div>
  );
}

// Los mensajes ya enviados no cambian: memo evita re-renderizar (y re-parsear
// el markdown) de todo el historial cada vez que cambia la lista de conversaciones.
export const Message = memo(MessageComponent);
