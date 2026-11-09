import { useState, type FormEvent } from 'react';
import { Eye, EyeOff, LockKeyhole } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';

interface LoginPageProps {
  onLogin?: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!onLogin || loading) return;

    const cleanUsername = username.trim();

    if (!cleanUsername || !password.trim()) {
      setError('Introduce tu usuario y contraseña.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await onLogin(cleanUsername, password);
      setPassword('');
    } catch {
      setError(
        'No se ha podido iniciar sesión. Comprueba tus datos e inténtalo de nuevo.',
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-fondo text-texto-100 flex items-center justify-center px-4 py-10">
      <section
        aria-labelledby="login-title"
        className="w-full max-w-md rounded-2xl border border-contraste/10 bg-tarjeta p-6 shadow-xl sm:p-8"
      >
        <div className="mb-8 flex items-center justify-between">
          <Logo />
          <span className="text-xs text-texto-400">
            ThermoDrive HTM-240
          </span>
        </div>

        <div className="mb-6">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-500/10">
            <LockKeyhole
              aria-hidden="true"
              className="h-6 w-6 text-cyan-400"
            />
          </div>

          <h1 id="login-title" className="text-2xl font-bold">
            Acceso al asistente
          </h1>

          <p className="mt-2 text-sm text-texto-400">
            Introduce tus credenciales para acceder al diagnóstico
            técnico documentado.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label
              htmlFor="username"
              className="mb-2 block text-sm font-medium text-texto-200"
            >
              Usuario
            </label>

            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              disabled={loading}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-lg border border-contraste/10 bg-fondo px-3 py-3 text-sm text-texto-100 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20 disabled:opacity-60"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-2 block text-sm font-medium text-texto-200"
            >
              Contraseña
            </label>

            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                disabled={loading}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-contraste/10 bg-fondo px-3 py-3 pr-12 text-sm text-texto-100 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20 disabled:opacity-60"
              />

              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                disabled={loading}
                aria-label={
                  showPassword
                    ? 'Ocultar contraseña'
                    : 'Mostrar contraseña'
                }
                aria-controls="password"
                className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-lg text-texto-400 hover:text-cyan-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
              >
                {showPassword ? (
                  <EyeOff aria-hidden="true" className="h-5 w-5" />
                ) : (
                  <Eye aria-hidden="true" className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300"
            >
              {error}
            </p>
          )}

          {!onLogin && (
            <p
              id="login-availability"
              className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300"
            >
              El inicio de sesión todavía no está disponible.
            </p>
          )}

          <button
            type="submit"
            disabled={!onLogin || loading}
            aria-describedby={!onLogin ? 'login-availability' : undefined}
            className="w-full rounded-lg bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Comprobando acceso…' : 'Iniciar sesión'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-texto-500">
          Asistente de documentación técnica ARSOFT
        </p>
      </section>
    </main>
  );
}