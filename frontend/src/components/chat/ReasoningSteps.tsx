import { Fragment, useState, type ReactNode } from 'react';
import {
  ArrowDown,
  Brain,
  ChevronDown,
  CircleCheck,
  CircleMinus,
  FileText,
  Languages,
  ListChecks,
  MessageSquareText,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import type { QueryStage, ReasoningStep, StepFragment } from '@/types/chat';
import { SOURCE_TYPES } from '@/utils/sourceTypes';

interface ReasoningStepsProps {
  steps: (ReasoningStep | string)[];
}

const KIND_ICONS: Record<ReasoningStep['kind'], LucideIcon> = {
  query: MessageSquareText,
  interpretation: Languages,
  search: Search,
  analysis: Brain,
  conclusion: ShieldCheck,
};

const EVIDENCE_STYLES = {
  high: { icon: 'bg-exito-500/15 text-exito-400 ring-exito-500/30', title: 'text-exito-400' },
  medium: { icon: 'bg-aviso-500/15 text-aviso-400 ring-aviso-500/30', title: 'text-aviso-400' },
  insufficient: { icon: 'bg-peligro-500/15 text-peligro-400 ring-peligro-500/30', title: 'text-peligro-400' },
} as const;

/** Respuestas guardadas antes de los pasos por fases: sus pasos eran solo texto. */
function normalize(steps: (ReasoningStep | string)[]): ReasoningStep[] {
  const legacy = steps.filter((s): s is string => typeof s === 'string');
  const structured = steps.filter((s): s is ReasoningStep => typeof s !== 'string');
  return legacy.length > 0
    ? [...structured, { kind: 'analysis', title: 'Pasos seguidos', points: legacy.map((text) => ({ text })) }]
    : structured;
}

// Códigos de documentos (HTM240-DIA-001) y técnicos (TES-01, CMP-02, HTM-0142) dentro del texto.
const CODES = /(HTM240-[A-Z]{3}-\d{3}|\b(?:CMP|TES|CIR)-\d{2}\b|\bHTM-(?:TOOL-)?\d{2,4}\b)/g;

/** Texto con los códigos en monoespaciada para distinguirlos de un vistazo. */
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split(CODES).map((part, i) =>
        i % 2 === 0 ? (
          <Fragment key={i}>{part}</Fragment>
        ) : (
          <code key={i} className="font-mono text-[0.9em] text-marca-300">
            {part}
          </code>
        ),
      )}
    </>
  );
}

/** Ficha del fragmento del que sale un paso: "HTM240-DIA-001 · pág. 1". */
function RefChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-px rounded bg-marca-500/10 text-marca-300 font-mono text-[10px] whitespace-nowrap">
      <FileText className="w-3 h-3" />
      {label}
    </span>
  );
}

/**
 * De la pregunta original a la consulta técnica generada: cada etapa en su recuadro, unidas por
 * flechas. La última (la que se busca) va destacada, con los códigos técnicos que ha añadido.
 */
function QueryTransformation({ stages }: { stages: QueryStage[] }) {
  return (
    <ol className="space-y-1">
      {stages.map((stage, i) => {
        const generated = i === stages.length - 1 && i > 0;
        return (
          <li key={i} className="space-y-1">
            {i > 0 && (
              <div className="flex items-center gap-1.5 pl-3 text-texto-600" aria-hidden>
                <ArrowDown className="w-3.5 h-3.5" />
              </div>
            )}
            <div
              className={`rounded-md border px-3 py-2 space-y-1.5 ${
                generated ? 'border-marca-500/30 bg-marca-500/5' : 'border-contraste/10 bg-contraste/5'
              }`}
            >
              <div
                className={`text-[10px] font-semibold uppercase tracking-wider ${
                  generated ? 'text-marca-400' : 'text-texto-500'
                }`}
              >
                {stage.label}
              </div>
              <p className={generated ? 'text-texto-200' : 'text-texto-300'}>
                <RichText text={stage.text} />
              </p>
              {stage.terms && stage.terms.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] text-texto-500">Términos añadidos:</span>
                  {stage.terms.map((term) => (
                    <span
                      key={term}
                      className="inline-flex items-center gap-0.5 px-1.5 py-px rounded bg-exito-500/10 font-mono text-[10px] text-exito-400"
                    >
                      <Plus className="w-2.5 h-2.5" />
                      {term}
                    </span>
                  ))}
                </div>
              )}
              {stage.note && <p className="text-[11px] text-texto-500">{stage.note}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function FragmentRow({ fragment }: { fragment: StepFragment }) {
  const type = SOURCE_TYPES[fragment.source_type] ?? SOURCE_TYPES.manual;
  const StatusIcon = fragment.used ? CircleCheck : CircleMinus;
  const location = [fragment.page !== undefined && `pág. ${fragment.page}`, fragment.section]
    .filter(Boolean)
    .join(' · ');

  return (
    <li
      className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px] ${
        fragment.used ? 'bg-exito-500/5' : 'opacity-55'
      }`}
      title={`${type.label} · ${fragment.used ? 'usado en la respuesta' : 'recuperado pero no usado'}`}
    >
      <StatusIcon className={`w-3.5 h-3.5 flex-shrink-0 ${fragment.used ? 'text-exito-400' : 'text-texto-500'}`} />
      <span className="font-mono text-texto-200 whitespace-nowrap">{fragment.document}</span>
      {location && <span className="text-texto-500 truncate">{location}</span>}
      <span className="flex-1" />
      <span className="hidden sm:block w-16 h-1.5 rounded-full bg-contraste/10 overflow-hidden flex-shrink-0">
        <span
          className={`block h-full rounded-full ${fragment.used ? 'bg-exito-400' : 'bg-texto-500'}`}
          style={{ width: `${Math.max(0, Math.min(1, fragment.score)) * 100}%` }}
        />
      </span>
      <span className="font-mono text-texto-400 w-8 text-right flex-shrink-0">{fragment.score.toFixed(2)}</span>
    </li>
  );
}

function StepBody({ step }: { step: ReasoningStep }) {
  const parts: ReactNode[] = [];

  if (step.detail) {
    parts.push(
      step.kind === 'interpretation' ? (
        <p key="detail" className="border-l-2 border-marca-500/30 pl-2.5 italic text-texto-400">
          <RichText text={step.detail} />
        </p>
      ) : (
        <p key="detail" className="text-texto-400">
          <RichText text={step.detail} />
        </p>
      ),
    );
  }

  if (step.stages?.length) {
    parts.push(<QueryTransformation key="stages" stages={step.stages} />);
  }

  if (step.terms?.length) {
    parts.push(
      <div key="terms" className="flex flex-wrap gap-1.5">
        {step.terms.map((term) => (
          <span key={term} className="px-1.5 py-0.5 rounded bg-contraste/5 border border-contraste/10 font-mono text-[11px] text-marca-300">
            {term}
          </span>
        ))}
      </div>,
    );
  }

  if (step.fragments?.length) {
    parts.push(
      <ul key="fragments" className="space-y-1">
        {step.fragments.map((fragment, i) => (
          <FragmentRow key={i} fragment={fragment} />
        ))}
      </ul>,
    );
  }

  if (step.points?.length) {
    parts.push(
      <ol key="points" className="space-y-2">
        {step.points.map((point, i) => (
          <li key={i} className="flex gap-2 text-texto-300">
            <span className="mt-px flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-marca-500/15 font-mono text-[10px] text-marca-300">
              {i + 1}
            </span>
            <div className="min-w-0 space-y-1">
              <p>
                <RichText text={point.text} />
              </p>
              {point.refs && point.refs.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {point.refs.map((ref) => (
                    <RefChip key={ref} label={ref} />
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>,
    );
  }

  return parts.length > 0 ? <div className="space-y-2 text-xs leading-relaxed">{parts}</div> : null;
}

function StepItem({ step, last }: { step: ReasoningStep; last: boolean }) {
  const evidence = step.kind === 'conclusion' && step.evidence ? EVIDENCE_STYLES[step.evidence] : null;
  const Icon = step.kind === 'conclusion' && step.evidence === 'insufficient' ? ShieldAlert : KIND_ICONS[step.kind];

  return (
    <li className="relative pl-10">
      {!last && <span className="absolute left-[13px] top-8 -bottom-4 w-px bg-contraste/10" aria-hidden />}
      <span
        className={`absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full ring-1 ${
          evidence?.icon ?? 'bg-marca-500/10 text-marca-400 ring-marca-500/20'
        }`}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="space-y-1.5 pt-1">
        <h4 className={`text-xs font-semibold ${evidence?.title ?? 'text-texto-200'}`}>{step.title}</h4>
        <StepBody step={step} />
      </div>
    </li>
  );
}

/**
 * "Pasos seguidos": cómo se ha llegado a la respuesta, como una línea temporal por fases
 * (consulta, interpretación, búsqueda, razonamiento y conclusión). Plegado de entrada, con un
 * resumen en la cabecera para no alargar la respuesta.
 */
export function ReasoningSteps({ steps }: ReasoningStepsProps) {
  const [open, setOpen] = useState(false);
  const phases = normalize(steps);

  const fragments = phases.find((s) => s.kind === 'search')?.fragments;
  const conclusion = phases.find((s) => s.kind === 'conclusion');
  const summary = [
    fragments && `${fragments.filter((f) => f.used).length} de ${fragments.length} fragmentos usados`,
    conclusion?.title,
  ].filter(Boolean);

  return (
    <div className="space-y-2.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="group flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-left"
      >
        <ListChecks className="w-3.5 h-3.5 text-marca-400" />
        <span className="text-marca-400 group-hover:text-marca-300 font-bold text-[11px] tracking-wider uppercase transition-colors">
          Pasos seguidos
        </span>
        {summary.length > 0 && <span className="text-[11px] text-texto-500">· {summary.join(' · ')}</span>}
        <ChevronDown className={`w-3.5 h-3.5 text-marca-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <ol className="space-y-4 rounded-lg border border-contraste/5 bg-elevado/40 p-4">
          {phases.map((step, i) => (
            <StepItem key={i} step={step} last={i === phases.length - 1} />
          ))}
        </ol>
      )}
    </div>
  );
}
