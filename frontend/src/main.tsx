import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import { AuthProvider } from './auth';
import { ToastProvider } from './toast';
import Root from './Root';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* Los toasts van por fuera de la sesión: siguen visibles al pasar del login a la app y al revés. */}
    <ToastProvider>
      <AuthProvider>
        <Root />
      </AuthProvider>
    </ToastProvider>
  </StrictMode>
);
