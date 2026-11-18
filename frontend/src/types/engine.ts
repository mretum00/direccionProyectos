import type { Profile } from './chat';

/** Sistema sobre el que se consulta (hay uno solo). Las versiones las ofrece el backend: GET /api/versions. */
export const ENGINE_NAME = 'ThermoDrive HTM-240';

export const PROFILES: { label: string; value: Profile }[] = [
  { label: 'Mecánico', value: 'mechanic' },
  { label: 'Usuario', value: 'user' },
];

/** Versión y perfil empiezan vacíos: el usuario debe elegirlos antes de poder consultar. */
export interface EngineSelection {
  engine_version: string;
  profile: Profile | '';
}

/** "V2.0 · Mecánico": cómo se muestra una versión con su perfil en toda la app. */
export function formatSelection(engineVersion?: string, profile?: Profile | ''): string {
  const profileLabel = PROFILES.find((p) => p.value === profile)?.label;
  return [engineVersion, profileLabel].filter(Boolean).join(' · ');
}

/** Nombres de los datos que aún faltan por elegir (vacío si la selección está completa). */
export function missingSelection(selection: EngineSelection): string[] {
  return [
    !selection.engine_version && 'versión del motor',
    !selection.profile && 'tipo de usuario',
  ].filter((item): item is string => !!item);
}

export function isSelectionComplete(selection: EngineSelection): selection is EngineSelection & { profile: Profile } {
  return Boolean(selection.engine_version && selection.profile);
}
