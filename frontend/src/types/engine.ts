import type { EngineSystem, Profile } from './chat';
export type { EngineSystem, Profile };

export interface EngineVersion {
  label: string;
  value: string;
}

export interface EngineOption {
  name: string;
  versions: EngineVersion[];
}

export const ENGINES: EngineOption[] = [
  {
    name: 'ThermoDrive HTM-240',
    versions: [
      { label: 'V1.0', value: 'V1.0' },
      { label: 'V1.1', value: 'V1.1' },
      { label: 'V2.0', value: 'V2.0' },
    ],
  },
];

export const PROFILES: { label: string; value: Profile }[] = [
  { label: 'Mecánico', value: 'mechanic' },
  { label: 'Conductor', value: 'user' },
];

export interface VehicleInfo {
  brand: string;
  model: string;
  year: number | null;
  vin: string;
}

export interface EngineSelection {
  engine: string;
  engine_version: string;
  system: EngineSystem;
  /** Vacío hasta que el usuario lo elige, igual que la versión. */
  profile: Profile | '';
  vehicle: VehicleInfo;
}

/** Selección con lo obligatorio ya elegido (versión y perfil): la única que permite enviar. */
export type CompleteSelection = EngineSelection & { engine_version: string; profile: Profile };

export function isComplete(selection: EngineSelection): selection is CompleteSelection {
  return !!selection.engine_version && !!selection.profile;
}
