import { useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, ChevronDown, CircleHelp, type LucideIcon } from 'lucide-react';
import type {
  ClaimCheckStatus,
  ClaimVerification,
  EvidenceSufficiency,
  RequestedEvidenceStatus,
  SafetyAlert,
  Source,
} from '@/types/chat';
import { Callout, StatusChip, type Tone } from '@/components/ui/Callout';

// --- Avisos de seguridad -------------------------------------------------------------------

/** Avisos deterministas del backend: siempre los primeros de la respuesta. */
export function SafetyAlerts({ alerts }: { alerts: SafetyAlert[] }) {
  if (alerts.length === 0) return null;
  return (
    <div className="space-y-2" aria-label="Avisos de seguridad">
      {alerts.map((alert) => {
        const critical = alert.severity === 'critical';
        return (
          <Callout
            key={alert.code}
            tone={critical ? 'danger' : 'warning'}
            icon={AlertTriangle}
            title={alert.title}
            role={critical ? 'alert' : 'note'}
          >
            <p className="text-sm leading-relaxed text-texto-200">{alert.message}</p>
          </Callout>
        );
      })}
    </div>
  );
}

// --- Panel común de comprobaciones automáticas ----------------------------------------------

interface CheckItem {
  text: string;
  label: string;
  tone: Tone;
  excerpt?: string | null;
  meta?: string;
}

interface CheckPanelProps {
  tone: Tone;
  icon: LucideIcon;
  title: string;
  chip: string;
  summary: string;
  items: CheckItem[];
  note: string;
}

/**
 * Comprobación automática (cobertura documental o revisión de afirmaciones). Muestra de
 * entrada el resultado y un resumen de una línea; el detalle de cada dato se despliega
 * bajo demanda, igual que los pasos seguidos, para no alargar la respuesta.
 */
function CheckPanel({ tone, icon, title, chip, summary, items, note }: CheckPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <Callout tone={tone} icon={icon} title={title} chip={<StatusChip tone={tone}>{chip}</StatusChip>}>
      <p className="text-xs text-texto-300 leading-relaxed">{summary}</p>
      {items.length > 0 && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex items-center gap-1 text-xs font-medium text-marca-400 hover:text-marca-300 transition-colors"
        >
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
          {open ? 'Ocultar detalle' : `Ver detalle (${items.length})`}
        </button>
      )}
      {open && (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={`${index}-${item.text}`} className="rounded-lg border border-contraste/5 bg-fondo/50 p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-texto-100">{item.text}</span>
                <StatusChip tone={item.tone}>{item.label}</StatusChip>
              </div>
              {item.excerpt && (
                <blockquote className="border-l-2 border-contraste/20 pl-3 text-xs text-texto-400 italic">
                  “{item.excerpt}”
                </blockquote>
              )}
              {item.meta && <p className="text-[11px] text-texto-500">{item.meta}</p>}
            </div>
          ))}
          <p className="text-[11px] text-texto-500 leading-relaxed">{note}</p>
        </div>
      )}
    </Callout>
  );
}

// Mismo estado, misma etiqueta y mismo color en las dos comprobaciones.
const ITEM_STATUS: Record<RequestedEvidenceStatus | ClaimCheckStatus, { label: string; tone: Tone }> = {
  supported: { label: 'Respaldado', tone: 'success' },
  not_found: { label: 'No localizado', tone: 'warning' },
  uncertain: { label: 'No concluyente', tone: 'warning' },
  unverified: { label: 'No verificado', tone: 'warning' },
  conflicting: { label: 'Contradictorio', tone: 'danger' },
};

// --- Cobertura documental (R07) -------------------------------------------------------------

export function SufficiencyCheck({ sufficiency }: { sufficiency?: EvidenceSufficiency }) {
  if (!sufficiency || sufficiency.status === 'not_run') return null;

  const items = sufficiency.requested_items;
  const supported = items.filter((item) => item.status === 'supported').length;
  const config: Record<Exclude<EvidenceSufficiency['status'], 'not_run'>, { tone: Tone; icon: LucideIcon; chip: string }> = {
    sufficient: { tone: 'success', icon: CheckCircle2, chip: 'Completa' },
    partial: { tone: 'warning', icon: AlertCircle, chip: 'Parcial' },
    insufficient: { tone: 'warning', icon: AlertCircle, chip: 'Sin datos' },
    unavailable: { tone: 'warning', icon: CircleHelp, chip: 'No disponible' },
  };
  const { tone, icon, chip } = config[sufficiency.status];

  return (
    <CheckPanel
      tone={tone}
      icon={icon}
      title="Cobertura documental"
      chip={chip}
      summary={
        sufficiency.status === 'unavailable'
          ? 'No se pudo comprobar si los fragmentos contienen los datos solicitados. Por precaución, no se ha generado una respuesta técnica.'
          : `${supported} de ${items.length} datos solicitados tienen una cita localizada en los fragmentos recuperados.`
      }
      items={items.map((item) => ({ text: item.item, ...ITEM_STATUS[item.status], excerpt: item.evidence_excerpt }))}
      note="La comprobación es automática y orientativa. Una cita literal no demuestra por sí sola que la interpretación sea correcta; contrasta siempre los datos técnicos con la documentación original."
    />
  );
}

// --- Revisión de afirmaciones ---------------------------------------------------------------

export function ClaimsCheck({ verification, sources }: { verification?: ClaimVerification; sources?: Source[] }) {
  if (!verification || verification.status === 'not_run' || verification.status === 'no_claims') return null;

  const unavailable = verification.status === 'unavailable';
  const restricted = verification.answer_restricted === true;
  const blocked = restricted && verification.claims_supported === 0;
  const reviewed = verification.status === 'reviewed';

  const tone: Tone = reviewed ? 'success' : 'warning';
  const icon = reviewed ? CheckCircle2 : unavailable ? CircleHelp : AlertCircle;
  const chip = reviewed
    ? 'Respaldada'
    : unavailable
      ? 'No disponible'
      : blocked
        ? 'Respuesta bloqueada'
        : restricted
          ? 'Respuesta limitada'
          : 'Requiere revisión';
  const summary = unavailable
    ? 'No se pudo completar la revisión automática.'
    : blocked
      ? 'No se muestra la respuesta generada porque ninguna afirmación obtuvo una cita literal validada.'
      : restricted
        ? 'La respuesta se ha limitado a las afirmaciones con una cita literal validada; las demás se han omitido.'
        : `${verification.claims_supported} de ${verification.claims_total} afirmaciones tienen un extracto localizado compatible.`;

  const documentsOf = (ids: string[] = []): string | undefined => {
    const names = ids
      .map((id) => sources?.find((source) => source.id === id)?.document)
      .filter((name): name is string => Boolean(name));
    return names.length > 0 ? `Fuentes: ${Array.from(new Set(names)).join(', ')}` : undefined;
  };

  return (
    <CheckPanel
      tone={tone}
      icon={icon}
      title="Revisión de afirmaciones"
      chip={chip}
      summary={summary}
      items={verification.claims.map((claim) => ({
        text: claim.claim,
        ...ITEM_STATUS[claim.status],
        excerpt: claim.evidence_excerpt,
        meta: documentsOf(claim.source_ids),
      }))}
      note="Revisión automática y orientativa de hasta 12 afirmaciones; puede no detectarlas todas. En procedimientos críticos, contrasta siempre la documentación y solicita revisión cualificada."
    />
  );
}
