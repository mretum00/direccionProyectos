import type { Profile } from './chat';
export type { Profile };

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
  { label: 'Usuario', value: 'user' },
];

export interface EngineSelection {
  engine: string;
  engine_version: string;
  profile: Profile;
}
