import { Activity, FileCheck, Gauge, Info, User } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { ENGINE_NAME, PROFILES, formatSelection } from '@/types/engine';
import type { Conversation } from '@/types/conversation';
import type { AnswerMeta, ChatMessage } from '@/types/chat';

const EVIDENCE_BADGES: Record<NonNullable<AnswerMeta['evidence_status']>, { label: string; color: string }> = {
  high: { label: 'Evidencia: ALTA', color: 'insignia-exito' },
  medium: { label: 'Evidencia: MEDIA', color: 'insignia-aviso' },
  insufficient: { label: 'Evidencia insuficiente', color: 'insignia-peligro' },
};

/** Respuesta más reciente del asistente con metadatos (recorre desde el final, sin copiar el array). */
function lastAnswer(conversation: Conversation | null): (ChatMessage & { response: AnswerMeta }) | undefined {
  const messages = conversation?.messages ?? [];
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.response && !message.response.needs_clarification) {
      return message as ChatMessage & { response: AnswerMeta };
    }
  }
  return undefined;
}

interface ContextPanelProps {
  conversation: Conversation | null;
}

/**
 * Dos bloques separados a propósito, porque la versión se puede cambiar a mitad del chat:
 * - "Próxima pregunta": la selección actual (lo que se usará al enviar).
 * - "Última respuesta": para qué versión se respondió y con qué evidencia.
 */
export function ContextPanel({ conversation }: ContextPanelProps) {
  const sel = useAppStore().engineSelection;

  const answer = lastAnswer(conversation);
  const response = answer?.response;
  const evidence = response?.evidence_status && EVIDENCE_BADGES[response.evidence_status];
  const hasSources = (response?.sources?.length ?? 0) > 0;
  const answeredFor = formatSelection(answer?.engine_version, answer?.profile);
  const selectionChanged =
    !!answer?.engine_version &&
    (answer.engine_version !== sel.engine_version || answer.profile !== sel.profile);

  const items = [
    { icon: Gauge, label: 'Motor', value: ENGINE_NAME },
    { icon: Activity, label: 'Versión', value: sel.engine_version || 'Sin seleccionar' },
    { icon: User, label: 'Tipo de usuario', value: PROFILES.find((p) => p.value === sel.profile)?.label ?? 'Sin seleccionar' },
  ];

  return (
    <div className="w-64 flex-shrink-0 border-l border-contraste/5 bg-panel/50 p-4 hidden xl:flex flex-col gap-4 overflow-y-auto">
      <h3 className="text-xs font-semibold text-texto-400 uppercase tracking-wider">Próxima pregunta</h3>

      <div className="space-y-3">
        {items.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-contraste/5 flex items-center justify-center flex-shrink-0">
              <Icon className="w-4 h-4 text-texto-400" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] text-texto-500 uppercase tracking-wide">{label}</div>
              <div className="text-xs text-texto-200 truncate">{value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="pt-3 border-t border-contraste/5 space-y-2">
        <div className="text-[11px] text-texto-500 uppercase tracking-wide">Última respuesta</div>
        {response ? (
          <>
            {answeredFor && (
              <div className="text-xs text-texto-200">
                Para <span className="font-medium text-marca-400">{answeredFor}</span>
              </div>
            )}
            {evidence && <div className={`${evidence.color} w-full px-3 py-2`}>{evidence.label}</div>}
            {response.documents_consulted !== undefined && (
              <div className="text-xs text-texto-400">Documentos consultados: {response.documents_consulted}</div>
            )}
            {hasSources && (
              <div className="flex items-center gap-1.5 text-xs text-exito-400">
                <FileCheck className="w-3.5 h-3.5" />
                <span>Consulta documentada ✓</span>
              </div>
            )}
            {selectionChanged && (
              <p className="flex items-start gap-1.5 text-[11px] leading-snug text-aviso-400">
                <Info className="mt-px h-3 w-3 flex-shrink-0" />
                Has cambiado la selección: la próxima pregunta se responderá para{' '}
                {formatSelection(sel.engine_version, sel.profile) || 'la nueva selección'}.
              </p>
            )}
          </>
        ) : (
          <div className="insignia-neutra w-full px-3 py-2 font-normal">Sin consulta aún</div>
        )}
      </div>
    </div>
  );
}
