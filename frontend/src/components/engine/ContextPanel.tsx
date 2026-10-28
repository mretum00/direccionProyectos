import { Activity, FileCheck, Gauge, ShieldCheck } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import type { Conversation } from '@/types/conversation';
import type { AssistantResponse } from '@/types/chat';

interface ContextPanelProps {
  conversation: Conversation | null;
}

export function ContextPanel({ conversation }: ContextPanelProps) {
  const store = useAppStore();
  const sel = store.engineSelection;

  const lastAssistant = conversation
    ? [...conversation.messages].reverse().find((m) => m.response)
    : undefined;
  const response: AssistantResponse | undefined = lastAssistant?.response;
  const hasSources = (response?.sources?.length ?? 0) > 0;

  const items = [
    { icon: Gauge, label: 'Motor', value: sel.engine },
    { icon: Activity, label: 'Versión', value: sel.engine_version || 'Sin seleccionar' },
    { icon: ShieldCheck, label: 'Sistema', value: sel.system || 'Auto' },
    { icon: FileCheck, label: 'Documentos consultados', value: response?.documents_consulted?.toString() ?? '—' },
  ];

  return (
    <div className="w-64 flex-shrink-0 border-l border-contraste/5 bg-panel/50 p-4 hidden xl:flex flex-col gap-4 overflow-y-auto">
      <h3 className="text-xs font-semibold text-texto-400 uppercase tracking-wider">Contexto</h3>

      <div className="space-y-3">
        {items.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-contraste/5 flex items-center justify-center flex-shrink-0">
              <Icon className="w-4 h-4 text-texto-400" />
            </div>
            <div className="min-w-0">
              <div className="text-[10px] text-texto-500 uppercase tracking-wide">{label}</div>
              <div className="text-xs text-texto-200 truncate">{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Evidence status */}
      <div className="pt-3 border-t border-contraste/5">
        <div className="text-[10px] text-texto-500 uppercase tracking-wide mb-2">Estado</div>
        {response?.evidence_status ? (
          <div className={`px-3 py-2 rounded-md text-xs font-medium ${
            response.evidence_status === 'high'
              ? 'bg-green-500/10 text-green-400'
              : response.evidence_status === 'medium'
              ? 'bg-amber-500/10 text-amber-400'
              : 'bg-red-500/10 text-red-400'
          }`}>
            {response.evidence_status === 'high' && 'Evidencia: ALTA'}
            {response.evidence_status === 'medium' && 'Evidencia: MEDIA'}
            {response.evidence_status === 'insufficient' && 'Evidencia insuficiente'}
          </div>
        ) : (
          <div className="px-3 py-2 rounded-md text-xs text-texto-500 bg-contraste/5">
            Sin consulta aún
          </div>
        )}
      </div>

      {hasSources && (
        <div className="pt-3 border-t border-contraste/5">
          <div className="flex items-center gap-1.5 text-xs text-green-400">
            <FileCheck className="w-3.5 h-3.5" />
            <span>Consulta documentada ✓</span>
          </div>
        </div>
      )}
    </div>
  );
}
