import { StrictMode, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import App from './App.tsx';
import { AuthProvider, useAuth } from './auth.tsx';
import { ToastProvider } from './toast.tsx';
import { LoginPage } from './pages/LoginPage.tsx';
import { navigate, useRoute } from './router.tsx';
import './index.css';

/**
 * Elige la vista según la URL y la sesión:
 * - sin sesión, solo se puede estar en /login o /register;
 * - con sesión, /login y /register llevan al asistente (/).
 */
function Root() {
  const route = useRoute();
  const { status, user, login, register } = useAuth();
  const isAuthPage = route === '/login' || route === '/register';

  useEffect(() => {
    if (status === 'anonymous' && !isAuthPage) navigate('/login', { replace: true });
    if (status === 'authenticated' && isAuthPage) navigate('/', { replace: true });
  }, [status, isAuthPage]);

  if (status === 'checking') {
    return <div className="min-h-screen bg-fondo" aria-busy="true" />;
  }
  if (status === 'authenticated' && user && !isAuthPage) {
    // `key`: al cambiar de usuario se descarta todo el estado del anterior (chats, selección...).
    return <App key={user.id} />;
  }
  return (
    <LoginPage
      mode={route === '/register' ? 'register' : 'login'}
      onLogin={login}
      onRegister={register}
    />
  );
}

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
