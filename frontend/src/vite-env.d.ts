/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_ENABLE_DOCUMENT_UPLOAD?: string;
  readonly VITE_DEFAULT_ENGINE_VERSION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
