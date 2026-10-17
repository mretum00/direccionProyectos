import { Loader2 } from 'lucide-react';

/** Estado de espera real: el backend responde en una sola petición, sin progreso intermedio que mostrar. */
export function ThinkingIndicator() {
  return (
    <div role="status" aria-live="polite" className="rounded-xl bg-[#151518] border border-white/5 p-4">
      <div className="flex items-center gap-2">
        <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
        <span className="text-sm text-gray-300">Consultando la documentación técnica…</span>
      </div>
    </div>
  );
}
