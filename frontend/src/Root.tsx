
import { useEffect } from 'react';
import App from './App.tsx';
import { useAuth } from './useAuth';
import { LoginPage } from './pages/LoginPage.tsx';
import { navigate, useRoute } from './router';

/**
 * Elige la vista según la URL y la sesión:
 * - Sin sesión, solo se puede estar en /login o /register.
 * - Con sesión, /login y /register llevan al asistente (/).
 */
function Root() {
  const route = useRoute();
  const { status, user, login, register } = useAuth();
  const isAuthPage = route === '/login' || route === '/register';

  useEffect(() => {
    if (status === 'anonymous' && !isAuthPage) {
      navigate('/login', { replace: true });
    }

    if (status === 'authenticated' && isAuthPage) {
      navigate('/', { replace: true });
    }
  }, [status, isAuthPage]);

  if (status === 'checking') {
    return <div className="min-h-screen bg-fondo" aria-busy="true" />;
  }

  if (status === 'authenticated' && user && !isAuthPage) {
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

export default Root;
