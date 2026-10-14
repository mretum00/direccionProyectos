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

export const SYSTEMS: { label: string; value: EngineSystem }[] = [
  { label: 'Auto', value: null },
  { label: 'CIR-01 Combustión', value: 'CIR-01' },
  { label: 'CIR-02 Alta tensión', value: 'CIR-02' },
  { label: 'CIR-03 Electrónica', value: 'CIR-03' },
];

export const PROFILES: { label: string; value: Profile }[] = [
  { label: 'Mecánico', value: 'mechanic' },
  { label: 'Usuario', value: 'user' },
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
  profile: Profile;
  vehicle: VehicleInfo;
}
