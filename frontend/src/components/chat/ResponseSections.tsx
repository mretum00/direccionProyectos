import type { ResponseSections, InterpretedQuery, DetectedDTC } from '@/types/chat';
import { CriticalityBadge } from './CriticalityBadge';
import { SafetyWarning } from './SafetyWarning';
import { Stethoscope, ListChecks, Wrench, ClipboardList, GitBranch, Languages, Tag } from 'lucide-react';

interface ResponseSectionsProps {
  sections?: ResponseSections;
  interpretedQuery?: InterpretedQuery;
  detectedDtc?: DetectedDTC[];
  content: string;
}

function SectionCard({ icon: Icon, title, children }: { icon: typeof Stethoscope; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-[#151518] border border-white/5 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-cyan-400" />
        <h4 className="text-sm font-semibold text-gray-200">{title}</h4>
      </div>
      {children}
    </div>
  );
}

export function ResponseSectionsView({ sections, interpretedQuery, detectedDtc, content }: ResponseSectionsProps) {
  const hasSections = sections && Object.values(sections).some((v) => v !== undefined && (Array.isArray(v) ? v.length > 0 : v));

  return (
    <div className="space-y-3">
      {/* Interpreted query */}
      {interpretedQuery && interpretedQuery.technical_terms?.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-gray-500 px-1">
          <Languages className="w-3.5 h-3.5" />
          <span>Interpretado como: </span>
          <span className="text-cyan-400">{interpretedQuery.technical_terms.join(', ')}</span>
        </div>
      )}

      {/* DTC chips */}
      {detectedDtc && detectedDtc.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap px-1">
          <Tag className="w-3.5 h-3.5 text-gray-500" />
          {detectedDtc.map((dtc) => (
            <span key={dtc.code} className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-cyan-500/10 border border-cyan-500/20 text-xs">
              <span className="font-mono font-semibold text-cyan-400">{dtc.code}</span>
              <span className="text-gray-400">{dtc.description}</span>
            </span>
          ))}
        </div>
      )}

      {/* If no structured sections, show content as text */}
      {!hasSections && (
        <div className="rounded-xl bg-[#151518] border border-white/5 p-4">
          <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{content}</p>
        </div>
      )}

      {/* Diagnosis */}
      {sections?.diagnosis && (
        <SectionCard icon={Stethoscope} title="Diagnóstico">
          <p className="text-sm text-gray-300 leading-relaxed">{sections.diagnosis}</p>
        </SectionCard>
      )}

      {/* Criticality */}
      {sections?.criticality && (
        <div className="px-1">
          <CriticalityBadge level={sections.criticality} />
        </div>
      )}

      {/* Safety */}
      <SafetyWarning safety={sections?.safety} ppe={sections?.ppe} />

      {/* Possible causes */}
      {sections?.possible_causes && sections.possible_causes.length > 0 && (
        <SectionCard icon={ListChecks} title="Posibles causas">
          <ul className="space-y-1.5">
            {sections.possible_causes.map((cause, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                <span className="mt-1.5 w-1 h-1 rounded-full bg-cyan-400 flex-shrink-0" />
                {cause}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {/* Checks */}
      {sections?.checks && sections.checks.length > 0 && (
        <SectionCard icon={ClipboardList} title={sections.decision_tree_id ? 'Comprobaciones (árbol de decisión)' : 'Comprobaciones'}>
          {sections.decision_tree_id && (
            <div className="flex items-center gap-1.5 mb-2 text-xs text-gray-500">
              <GitBranch className="w-3 h-3" />
              Árbol: <span className="font-mono text-cyan-400">{sections.decision_tree_id}</span>
            </div>
          )}
          <ol className="space-y-2">
            {sections.checks.map((check, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-gray-300">
                <span className="flex-shrink-0 w-5 h-5 rounded-md bg-cyan-500/10 text-cyan-400 text-xs font-mono font-semibold flex items-center justify-center">
                  {i + 1}
                </span>
                {check}
              </li>
            ))}
          </ol>
        </SectionCard>
      )}

      {/* Procedure */}
      {sections?.procedure && (
        <SectionCard icon={Wrench} title="Procedimiento">
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{sections.procedure}</p>
          <p className="text-xs text-gray-500 mt-2 italic">
            Siga siempre el procedimiento oficial. El asistente no inventa procedimientos.
          </p>
        </SectionCard>
      )}
    </div>
  );
}
