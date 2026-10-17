import { useState, useRef, useEffect } from 'react';
import { Settings2, ChevronDown, AlertTriangle, Car } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { ToggleGroup } from '@/components/ui/ToggleGroup';
import { ENGINES, PROFILES, SYSTEMS, type EngineSelection, type EngineSystem, type VehicleInfo } from '@/types/engine';

const INPUT_CLASS =
  'bg-[#0a0a0b] border border-white/10 rounded-md px-2.5 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50';
const SELECT_CLASS =
  'w-full bg-[#0a0a0b] border border-white/10 rounded-md px-3 py-2 text-sm text-white outline-none focus:border-cyan-500/50';

const VEHICLE_TEXT_FIELDS: { key: 'brand' | 'model' | 'vin'; placeholder: string }[] = [
  { key: 'brand', placeholder: 'Marca' },
  { key: 'model', placeholder: 'Modelo' },
  { key: 'vin', placeholder: 'VIN' },
];

export function EngineSelector() {
  const { engineSelection: sel, setEngineSelection } = useAppStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // El listener global solo existe mientras el panel está abierto.
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const update = (patch: Partial<EngineSelection>) => setEngineSelection({ ...sel, ...patch });
  const updateVehicle = (patch: Partial<VehicleInfo>) => update({ vehicle: { ...sel.vehicle, ...patch } });

  const versions = ENGINES.find((e) => e.name === sel.engine)?.versions ?? [];
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
          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Motor</label>
            <select
              value={sel.engine}
              onChange={(e) => {
                const engine = ENGINES.find((x) => x.name === e.target.value);
                const keepVersion = engine?.versions.some((v) => v.value === sel.engine_version);
                update({ engine: e.target.value, engine_version: keepVersion ? sel.engine_version : '' });
              }}
              className={SELECT_CLASS}
            >
              {ENGINES.map((eng) => (
                <option key={eng.name} value={eng.name}>{eng.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Versión</label>
            <ToggleGroup
              options={versions}
              value={sel.engine_version}
              onChange={(engine_version) => update({ engine_version })}
            />
            {versionWarning && (
              <p className="flex items-center gap-1.5 mt-2 text-[11px] text-amber-400">
                <AlertTriangle className="w-3 h-3" />
                Selecciona la versión para obtener respuestas
              </p>
            )}
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Sistema</label>
            <select
              value={sel.system ?? ''}
              onChange={(e) => update({ system: (e.target.value || null) as EngineSystem })}
              className={SELECT_CLASS}
            >
              {SYSTEMS.map((s) => (
                <option key={s.label} value={s.value ?? ''}>{s.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Perfil de respuesta</label>
            <ToggleGroup options={PROFILES} value={sel.profile} onChange={(profile) => update({ profile })} />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-400 mb-1.5">
              <span className="flex items-center gap-1"><Car className="w-3 h-3" /> Datos del vehículo (opcional)</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              {VEHICLE_TEXT_FIELDS.slice(0, 2).map(({ key, placeholder }) => (
                <input
                  key={key}
                  placeholder={placeholder}
                  value={sel.vehicle[key]}
                  onChange={(e) => updateVehicle({ [key]: e.target.value })}
                  className={INPUT_CLASS}
                />
              ))}
              <input
                type="number"
                placeholder="Año"
                value={sel.vehicle.year ?? ''}
                onChange={(e) => updateVehicle({ year: e.target.value ? parseInt(e.target.value, 10) : null })}
                className={INPUT_CLASS}
              />
              <input
                placeholder={VEHICLE_TEXT_FIELDS[2].placeholder}
                value={sel.vehicle.vin}
                onChange={(e) => updateVehicle({ vin: e.target.value })}
                className={INPUT_CLASS}
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
