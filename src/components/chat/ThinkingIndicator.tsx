import { useState, useEffect } from 'react';
import { ChevronDown, Loader2, Search, FileText, Brain, MessageSquare, Check } from 'lucide-react';

interface ThinkingIndicatorProps {
  visible: boolean;
}

const STEPS = [
  { icon: MessageSquare, label: 'Consulta recibida' },
  { icon: Search, label: 'Buscando documentación' },
  { icon: FileText, label: 'Recuperando fragmentos' },
  { icon: Brain, label: 'Analizando evidencia' },
  { icon: FileText, label: 'Generando respuesta' },
];

const PHASES = ['Analizando documentación…', 'Buscando evidencia…', 'Generando respuesta…'];

export function ThinkingIndicator({ visible }: ThinkingIndicatorProps) {
  const [expanded, setExpanded] = useState(false);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!visible) {
      setPhase(0);
      return;
    }
    setPhase(0);
    const interval = setInterval(() => {
      setPhase((p) => (p < PHASES.length - 1 ? p + 1 : p));
    }, 1500);
    return () => clearInterval(interval);
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="rounded-xl bg-[#151518] border border-white/5 p-4">
      <div className="flex items-center gap-2">
        <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
        <span className="text-sm text-gray-300">{PHASES[phase]}</span>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
        >
          Ver proceso
          <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2 pl-1">
          {STEPS.map((step, i) => {
            const active = i === phase;
            const done = i < phase;
            return (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                  done ? 'bg-green-500/15' : active ? 'bg-cyan-500/15' : 'bg-white/5'
                }`}>
                  {done ? (
                    <Check className="w-3 h-3 text-green-400" />
                  ) : active ? (
                    <Loader2 className="w-3 h-3 text-cyan-400 animate-spin" />
                  ) : (
                    <step.icon className="w-3 h-3 text-gray-600" />
                  )}
                </div>
                <span className={done ? 'text-gray-400' : active ? 'text-cyan-300' : 'text-gray-600'}>
                  {step.label}
                </span>
              </div>
            );
          })}
          <p className="text-[10px] text-gray-600 italic pt-1">
            Progreso estimado. La API actual no envía eventos intermedios.
          </p>
        </div>
      )}
    </div>
  );
}
