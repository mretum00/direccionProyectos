import { useRef, useEffect } from 'react';
import { Settings2, ChevronDown, AlertTriangle } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { ToggleGroup } from '@/components/ui/ToggleGroup';
import { ENGINES, PROFILES, type EngineSelection } from '@/types/engine';

const SELECT_CLASS =
  'w-full bg-fondo border border-contraste/10 rounded-md px-3 py-2 text-sm text-texto outline-none focus:border-marca-500/50';

export function EngineSelector() {
  const { engineSelection: sel, setEngineSelection, engineSelectorOpen: open, setEngineSelectorOpen: setOpen } = useAppStore();
  const ref = useRef<HTMLDivElement>(null);

  // El listener global solo existe mientras el panel está abierto.
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, setOpen]);

  const update = (patch: Partial<EngineSelection>) => setEngineSelection({ ...sel, ...patch });

  const versions = ENGINES.find((e) => e.name === sel.engine)?.versions ?? [];
  const versionWarning = !sel.engine_version;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-contraste/5 hover:bg-contraste/10 border border-contraste/5 text-xs transition-colors"
      >
        <Settings2 className="w-3.5 h-3.5 text-marca-400" />
        <span className="hidden md:inline text-texto-200">
          {sel.engine}
          {sel.engine_version && <span className="text-texto-400"> · {sel.engine_version}</span>}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-texto-500" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-tarjeta border border-contraste/10 rounded-xl shadow-2xl z-50 p-4 space-y-4">
          <div>
            <label className="block text-[11px] font-medium text-texto-400 mb-1.5">Motor</label>
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
            <label className="block text-[11px] font-medium text-texto-400 mb-1.5">Versión</label>
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
            <label className="block text-[11px] font-medium text-texto-400 mb-1.5">Perfil de respuesta</label>
            <ToggleGroup options={PROFILES} value={sel.profile} onChange={(profile) => update({ profile })} />
          </div>

          <button
            onClick={() => setOpen(false)}
            className="w-full py-2 rounded-md bg-marca-500/10 text-marca-400 text-sm font-medium hover:bg-marca-500/20 transition-colors"
          >
            Aplicar
          </button>
        </div>
      )}
    </div>
  );
}
