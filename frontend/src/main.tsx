import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { LoginPage } from './pages/LoginPage.tsx';
import './index.css';

const params = new URLSearchParams(window.location.search);
const previewLogin = params.get('pantalla') === 'acceso';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {previewLogin ? <LoginPage /> : <App />}
  </StrictMode>,
);