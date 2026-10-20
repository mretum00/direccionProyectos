interface ToggleOption<T extends string> {
  label: string;
  value: T;
}

interface ToggleGroupProps<T extends string> {
  options: readonly ToggleOption<T>[];
  value: T | '';
  onChange: (value: T) => void;
}

/** Grupo de botones excluyentes (versión del motor, perfil...). */
export function ToggleGroup<T extends string>({ options, value, onChange }: ToggleGroupProps<T>) {
  return (
    <div className="flex gap-2" role="group">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
              selected
                ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                : 'bg-contraste/5 text-texto-300 border border-contraste/5 hover:bg-contraste/10'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
