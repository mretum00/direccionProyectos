import type { SafetyItem } from '@/types/chat';
import { ShieldAlert, HardHat } from 'lucide-react';

interface SafetyWarningProps {
  safety?: SafetyItem[];
  ppe?: string[];
}

export function SafetyWarning({ safety, ppe }: SafetyWarningProps) {
  if (!safety?.length && !ppe?.length) return null;

  const hasCritical = safety?.some((s) => s.level === 'critical');

  return (
    <div className={`rounded-xl border p-4 ${
      hasCritical
        ? 'bg-red-500/10 border-red-500/30'
        : 'bg-orange-500/10 border-orange-500/30'
    }`}>
      {safety && safety.length > 0 && (
        <div className="space-y-2 mb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className={`w-4 h-4 ${hasCritical ? 'text-red-400' : 'text-orange-400'}`} />
            <h4 className={`text-sm font-semibold ${hasCritical ? 'text-red-400' : 'text-orange-400'}`}>
              Advertencias de seguridad
            </h4>
          </div>
          {safety.map((item, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 text-xs ${
                item.level === 'critical' ? 'text-red-300' : 'text-orange-300'
              }`}
            >
              <span className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                item.level === 'critical' ? 'bg-red-400' : 'bg-orange-400'
              }`} />
              <span>{item.text}</span>
            </div>
          ))}
        </div>
      )}

      {ppe && ppe.length > 0 && (
        <div className={safety?.length ? 'pt-3 border-t border-white/10' : ''}>
          <div className="flex items-center gap-2 mb-2">
            <HardHat className={`w-4 h-4 ${hasCritical ? 'text-red-400' : 'text-orange-400'}`} />
            <h4 className={`text-sm font-semibold ${hasCritical ? 'text-red-400' : 'text-orange-400'}`}>
              EPIs requeridos
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {ppe.map((item, i) => (
              <span
                key={i}
                className={`px-2.5 py-1 rounded-md text-xs ${
                  hasCritical ? 'bg-red-500/10 text-red-300' : 'bg-orange-500/10 text-orange-300'
                }`}
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
