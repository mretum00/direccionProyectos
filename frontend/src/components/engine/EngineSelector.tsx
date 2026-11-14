import { useRef, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Settings2, ChevronDown, AlertTriangle, Check, Info, User, Wrench, type LucideIcon } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { ToggleGroup } from '@/components/ui/ToggleGroup';
import type { Profile } from '@/types/chat';
import { ENGINE_NAME, PROFILES, isSelectionComplete, missingSelection, type EngineSelection } from '@/types/engine';

const APPLIED_NOTICE_MS = 2500;

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-xs font-semibold text-texto-200">{children}</p>;
}

const PROFILE_DETAILS: Record<Profile, { icon: LucideIcon; description: string }> = {
  mechanic: { icon: Wrench, description: 'Lenguaje técnico: códigos, componentes y procedimientos.' },
  user: { icon: User, description: 'Lenguaje sencillo: qué hacer y cuándo acudir al taller.' },
};

/** Opción de perfil: tarjeta con icono y una frase que explica qué cambia en las respuestas. */
function ProfileOption({ profile, label, selected, onSelect }: {
  profile: Profile;
  label: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const { icon: Icon, description } = PROFILE_DETAILS[profile];
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
        selected
          ? 'border-marca-500/40 bg-marca-500/10'
          : 'border-contraste/5 bg-contraste/5 hover:bg-contraste/10'
      }`}
    >
      <div
        className={`mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md ${
          selected ? 'bg-marca-500/20 text-marca-300' : 'bg-contraste/5 text-texto-400'
        }`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-medium ${selected ? 'text-texto' : 'text-texto-200'}`}>{label}</p>
        <p className="text-[11px] leading-snug text-texto-400">{description}</p>
      </div>
      {selected && <Check className="mt-1 h-4 w-4 flex-shrink-0 text-marca-400" />}
    </button>
  );
}

interface SelectorPanelProps {
  versions: string[];
  initial: EngineSelection;
  /** Se abrió al intentar consultar sin configurar: se explica por qué y qué pasará después. */
  prompted: boolean;
  onApply: (selection: EngineSelection) => void;
  onCancel: () => void;
}

/**
 * Edita una copia de la selección: no se aplica hasta pulsar "Aplicar". Como solo
 * está montado con el panel abierto, cada vez que se abre parte de la selección actual
 * y, si se cierra sin aplicar, los cambios se descartan.
 */
function SelectorPanel({ versions, initial, prompted, onApply, onCancel }: SelectorPanelProps) {
  const [draft, setDraft] = useState(initial);
  const update = (patch: Partial<EngineSelection>) => setDraft((prev) => ({ ...prev, ...patch }));
  const missing = missingSelection(draft);

  return (
    <div className="absolute right-0 top-full mt-2 w-[22rem] max-w-[calc(100vw-2rem)] bg-tarjeta border border-contraste/10 rounded-xl shadow-2xl z-50 overflow-hidden animate-in">
      <div className="px-5 pt-4 pb-3">
        <h3 className="text-sm font-semibold text-texto">Configura tu consulta</h3>
        <p className="mt-0.5 text-xs text-texto-400">Adaptamos las respuestas a tu motor y a tu forma de trabajar.</p>
      </div>

      {prompted && (
        <div className="mx-5 mb-1 flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5">
          <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" />
          <p className="text-xs leading-relaxed text-texto-200">
            Antes de responderte necesito saber{' '}
            <strong className="font-semibold text-amber-300">{missing.map((m) => `tu ${m}`).join(' y ')}</strong>.
            Elígelo y enviaré tu pregunta automáticamente.
          </p>
        </div>
      )}

      <div className="space-y-4 px-5 py-4">
        <div>
          <FieldLabel>Versión del motor</FieldLabel>
          <ToggleGroup
            options={versions.map((v) => ({ label: v, value: v }))}
            value={draft.engine_version}
            onChange={(engine_version) => update({ engine_version })}
          />
          {versions.length === 0 && (
            <p className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-400">
              <AlertTriangle className="h-3 w-3" />
              No se han podido cargar las versiones: comprueba que el backend está en marcha
            </p>
          )}
        </div>

        <div>
          <FieldLabel>Tipo de usuario</FieldLabel>
          <div role="radiogroup" aria-label="Tipo de usuario" className="space-y-2">
            {PROFILES.map(({ value, label }) => (
              <ProfileOption
                key={value}
                profile={value}
                label={label}
                selected={draft.profile === value}
                onSelect={() => update({ profile: value })}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-2 border-t border-contraste/5 bg-fondo/40 px-5 py-3">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 rounded-md text-xs text-texto-400 hover:text-texto hover:bg-contraste/5 transition-colors"
        >
          Cancelar
        </button>
        <button
          onClick={() => onApply(draft)}
          disabled={missing.length > 0}
          className="px-4 py-1.5 rounded-md bg-marca-500 text-white text-xs font-medium hover:bg-marca-400 transition-colors disabled:bg-contraste/5 disabled:text-texto-600 disabled:cursor-not-allowed"
        >
          Aplicar
        </button>
      </div>
    </div>
  );
}

export function EngineSelector() {
  const { versions, engineSelection: sel, setEngineSelection, engineSelectorOpen: open, engineSelectorPrompted: prompted, setEngineSelectorOpen: setOpen } = useAppStore();
  const [applied, setApplied] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const complete = isSelectionComplete(sel);
  const profileLabel = PROFILES.find((p) => p.value === sel.profile)?.label;

  // El listener global solo existe mientras el panel está abierto.
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, setOpen]);

  // El aviso "Cambios aplicados" desaparece solo.
  useEffect(() => {
    if (!applied) return;
    const timer = setTimeout(() => setApplied(false), APPLIED_NOTICE_MS);
    return () => clearTimeout(timer);
  }, [applied]);

  function handleApply(selection: EngineSelection) {
    setEngineSelection(selection);
    setOpen(false);
    setApplied(true);
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        aria-label={complete ? `Consulta: ${sel.engine_version}, ${profileLabel}` : 'Configurar consulta: elige versión y tipo de usuario'}
        className={`relative flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs transition-colors ${
          complete
            ? 'bg-contraste/5 hover:bg-contraste/10 border-contraste/5'
            : 'bg-marca-500/10 hover:bg-marca-500/15 border-marca-500/30'
        }`}
      >
        <Settings2 className="w-3.5 h-3.5 text-marca-400" />
        {complete ? (
          <span className="hidden md:inline text-texto-200">
            {sel.engine_version}
            <span className="text-texto-400"> · {profileLabel}</span>
          </span>
        ) : (
          <span className="hidden md:inline font-medium text-marca-300">Configurar consulta</span>
        )}
        <ChevronDown className="w-3.5 h-3.5 text-texto-500" />
        {!complete && (
          <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full rounded-full bg-marca-400 opacity-60 motion-safe:animate-ping" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-marca-400" />
          </span>
        )}
      </button>

      {open && <SelectorPanel versions={versions} initial={sel} prompted={prompted} onApply={handleApply} onCancel={() => setOpen(false)} />}

      {applied && <AppliedToast selection={sel} />}
    </div>
  );
}

/** Aviso flotante (abajo a la derecha) que confirma que la selección se ha aplicado y cuál es. */
function AppliedToast({ selection }: { selection: EngineSelection }) {
  const profileLabel = PROFILES.find((p) => p.value === selection.profile)?.label;
  const summary = [ENGINE_NAME, selection.engine_version, profileLabel].filter(Boolean).join(' · ');

  // En un portal: el backdrop-blur de la cabecera haría que `fixed` se posicionara respecto a ella.
  return createPortal(
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 right-6 z-[70] flex w-80 items-start gap-3 rounded-lg border border-contraste/10 bg-elevado p-4 shadow-2xl animate-toast-in"
    >
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-green-500/10">
        <Check className="h-4 w-4 text-green-400" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-texto">Cambios aplicados</p>
        <p className="mt-0.5 truncate text-xs text-texto-400">{summary}</p>
      </div>
    </div>,
    document.body,
  );
}
