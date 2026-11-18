import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import App from './App.tsx';
import { LoginPage } from './pages/LoginPage.tsx';
import { useRoute } from './router.tsx';
import './index.css';

/** Elige la vista según la URL: /login, /register o el asistente (/). */
function Root() {
  const route = useRoute();
  if (route === '/login') return <LoginPage mode="login" />;
  if (route === '/register') return <LoginPage mode="register" />;
  return <App />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>
);
