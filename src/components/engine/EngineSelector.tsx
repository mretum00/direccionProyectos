import { useState, useRef, useEffect } from 'react';
import { Settings2, ChevronDown, AlertTriangle, Car } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { ENGINES, SYSTEMS, type EngineSystem } from '@/types/engine';
import type { Profile } from '@/types/chat';

export function EngineSelector() {
  const store = useAppStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const sel = store.engineSelection;
  const versionWarning = !sel.engine_version;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-white/5 hover:bg-white/10 border border-white/5 text-xs transition-colors"
      >
        <Settings2 className="w-3.5 h-3.5 text-cyan-400" />
        <span className="hidden md:inline text-gray-200">
          {sel.engine}
          {sel.engine_version && <span className="text-gray-400"> · {sel.engine_version}</span>}
        </span>
        {sel.system && <span className="hidden lg:inline text-cyan-400"> · {sel.system}</span>}
        <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-[#151518] border border-white/10 rounded-xl shadow-2xl z-50 p-4 space-y-4">
          {/* Engine */}
          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Motor</label>
            <select
              value={sel.engine}
              onChange={(e) => store.setEngineSelection({ ...sel, engine: e.target.value })}
              className="w-full bg-[#0a0a0b] border border-white/10 rounded-md px-3 py-2 text-sm text-white outline-none focus:border-cyan-500/50"
            >
              {ENGINES.map((eng) => (
                <option key={eng.name} value={eng.name}>{eng.name}</option>
              ))}
            </select>
          </div>

          {/* Version */}
          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Versión</label>
            <div className="flex gap-2">
              {ENGINES.find((e) => e.name === sel.engine)?.versions.map((v) => (
                <button
                  key={v.value}
                  onClick={() => store.setEngineSelection({ ...sel, engine_version: v.value })}
                  className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                    sel.engine_version === v.value
                      ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                      : 'bg-white/5 text-gray-300 border border-white/5 hover:bg-white/10'
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
            {versionWarning && (
              <p className="flex items-center gap-1.5 mt-2 text-[11px] text-amber-400">
                <AlertTriangle className="w-3 h-3" />
                Selecciona la versión para respuestas más precisas
              </p>
            )}
          </div>

          {/* System */}
          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Sistema</label>
            <select
              value={sel.system ?? ''}
              onChange={(e) => store.setEngineSelection({ ...sel, system: (e.target.value || null) as EngineSystem })}
              className="w-full bg-[#0a0a0b] border border-white/10 rounded-md px-3 py-2 text-sm text-white outline-none focus:border-cyan-500/50"
            >
              {SYSTEMS.map((s) => (
                <option key={s.label} value={s.value ?? ''}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Profile */}
          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Perfil de respuesta</label>
            <div className="flex gap-2">
              <button
                onClick={() => store.setEngineSelection({ ...sel, profile: 'mechanic' as Profile })}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                  sel.profile === 'mechanic'
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                    : 'bg-white/5 text-gray-300 border border-white/5 hover:bg-white/10'
                }`}
              >
                Mecánico
              </button>
              <button
                onClick={() => store.setEngineSelection({ ...sel, profile: 'user' as Profile })}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                  sel.profile === 'user'
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                    : 'bg-white/5 text-gray-300 border border-white/5 hover:bg-white/10'
                }`}
              >
                Usuario
              </button>
            </div>
          </div>

          {/* Vehicle info */}
          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">
              <span className="flex items-center gap-1"><Car className="w-3 h-3" /> Datos del vehículo (opcional)</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <input
                placeholder="Marca"
                value={sel.vehicle.brand}
                onChange={(e) => store.setEngineSelection({ ...sel, vehicle: { ...sel.vehicle, brand: e.target.value } })}
                className="bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
              />
              <input
                placeholder="Modelo"
                value={sel.vehicle.model}
                onChange={(e) => store.setEngineSelection({ ...sel, vehicle: { ...sel.vehicle, model: e.target.value } })}
                className="bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
              />
              <input
                type="number"
                placeholder="Año"
                value={sel.vehicle.year ?? ''}
                onChange={(e) => store.setEngineSelection({ ...sel, vehicle: { ...sel.vehicle, year: e.target.value ? parseInt(e.target.value) : null } })}
                className="bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
              />
              <input
                placeholder="VIN"
                value={sel.vehicle.vin}
                onChange={(e) => store.setEngineSelection({ ...sel, vehicle: { ...sel.vehicle, vin: e.target.value } })}
                className="bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
              />
            </div>
          </div>

          <button
            onClick={() => setOpen(false)}
            className="w-full py-2 rounded-md bg-cyan-500/10 text-cyan-400 text-sm font-medium hover:bg-cyan-500/20 transition-colors"
          >
            Aplicar
          </button>
        </div>
      )}
    </div>
  );
}
