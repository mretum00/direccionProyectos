import { useState, useRef, useEffect } from 'react';
import { Settings2, ChevronDown, AlertTriangle } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { ToggleGroup } from '@/components/ui/ToggleGroup';
import { ENGINES, PROFILES, type EngineSelection } from '@/types/engine';

const SELECT_CLASS =
  'w-full bg-fondo border border-contraste/10 rounded-md px-3 py-2 text-sm text-texto outline-none focus:border-cyan-500/50';

/**
 * Motor, versión y perfil con los que se envía la consulta. La versión y el perfil
 * hay que elegirlos siempre; el panel se abre solo si se intenta enviar sin ellos.
 */
export function EngineSelector() {
  const { engineSelection: sel, setEngineSelection, selectionRequest } = useAppStore();
  const [open, setOpen] = useState(false);
  // Resalta el botón tras un intento de envío incompleto, hasta que se complete la selección.
  const [flagged, setFlagged] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Un intento de envío incompleto abre el panel para que se elija ahí mismo.
  useEffect(() => {
    if (selectionRequest > 0) {
      setOpen(true);
      setFlagged(true);
    }
  }, [selectionRequest]);

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

  const versions = ENGINES.find((e) => e.name === sel.engine)?.versions ?? [];
  const versionMissing = !sel.engine_version;
  const profileMissing = !sel.profile;
  const incomplete = versionMissing || profileMissing;
  const highlight = incomplete && flagged;

  // Al completar la selección se quita el resaltado: en un chat nuevo empieza limpio.
  useEffect(() => {
    if (!incomplete) setFlagged(false);
  }, [incomplete]);
  const missingLabel =
    versionMissing && profileMissing ? 'Elegir versión y perfil' : versionMissing ? 'Elegir versión' : 'Elegir perfil';
  const profileLabel = PROFILES.find((p) => p.value === sel.profile)?.label;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Motor, versión y perfil de la consulta"
        className={`flex items-center gap-2 h-8 pl-2.5 pr-2 rounded-full border text-xs transition-all ${
          incomplete
            ? `border-dashed border-amber-500/50 bg-amber-500/10 hover:bg-amber-500/15 ${highlight ? 'ring-2 ring-amber-500/30' : ''}`
            : 'border-contraste/10 bg-contraste/[0.03] hover:bg-contraste/[0.07]'
        }`}
      >
        {incomplete ? (
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
        ) : (
          <Settings2 className="w-3.5 h-3.5 text-texto-400 flex-shrink-0" />
        )}
        <span className="hidden lg:inline text-texto-200 font-medium truncate">{sel.engine}</span>
        {incomplete ? (
          <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 font-semibold whitespace-nowrap">
            {missingLabel}
          </span>
        ) : (
          <>
            <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 font-semibold">
              {sel.engine_version}
            </span>
            <span className="hidden sm:inline text-texto-300 font-medium">{profileLabel}</span>
          </>
        )}
        <ChevronDown className={`w-3.5 h-3.5 text-texto-500 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 max-w-[calc(100vw-2rem)] bg-tarjeta border border-contraste/10 rounded-xl shadow-2xl z-50 p-4 space-y-4">
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
            {versionMissing && (
              <p className="flex items-center gap-1.5 mt-2 text-[11px] text-amber-400">
                <AlertTriangle className="w-3 h-3" />
                Selecciona la versión para obtener respuestas
              </p>
            )}
          </div>

          <div>
            <label className="block text-[11px] font-medium text-texto-400 mb-1.5">Perfil de respuesta</label>
            <ToggleGroup options={PROFILES} value={sel.profile} onChange={(profile) => update({ profile })} />
            {profileMissing ? (
              <p className="flex items-center gap-1.5 mt-2 text-[11px] text-amber-400">
                <AlertTriangle className="w-3 h-3" />
                Selecciona el perfil para obtener respuestas
              </p>
            ) : (
              <p className="mt-2 text-[11px] text-texto-500">
                {sel.profile === 'user' ? 'Lenguaje sencillo, pensado para el conductor.' : 'Lenguaje técnico, pensado para el taller.'}
              </p>
            )}
          </div>

          <button
            type="button"
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
