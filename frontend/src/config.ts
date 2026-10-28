/**
 * Configuración del frontend. Única puerta de entrada a `import.meta.env`:
 * el resto del código importa `config` y nunca lee variables de entorno ni
 * hardcodea URLs. Las variables se definen en el `.env` de la raíz del repo.
 */

const env = import.meta.env;

function flag(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === 'true';
}

export const config = {
  /** URL base del backend FastAPI (sin barra final). */
  apiUrl: (env.VITE_API_URL ?? '').trim().replace(/\/+$/, ''),
  /** true: conversaciones en el backend. false: localStorage del navegador. */
  remoteConversations: flag(env.VITE_REMOTE_CONVERSATIONS),
  /** Activa el botón de subida de PDF en la pantalla de documentación. */
  enableDocumentUpload: flag(env.VITE_ENABLE_DOCUMENT_UPLOAD),
  /** Motor preseleccionado (debe existir en ENGINES). Vacío = primero de la lista. */
  defaultEngine: (env.VITE_DEFAULT_ENGINE ?? '').trim(),
  /** Versión preseleccionada (debe existir para ese motor). Vacío = sin seleccionar. */
  defaultEngineVersion: (env.VITE_DEFAULT_ENGINE_VERSION ?? '').trim(),
  /** El contrato de la API fija en 6 los mensajes previos que viajan en `history`. */
  chatHistoryLimit: 6,
} as const;

if (!config.apiUrl) {
  console.warn('VITE_API_URL no está definida: define la URL del backend en el .env de la raíz del repositorio.');
}
