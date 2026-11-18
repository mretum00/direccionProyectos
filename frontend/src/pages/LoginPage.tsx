import { useState, type FormEvent } from 'react';
import { Eye, EyeOff, LockKeyhole, UserPlus } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';

/** Longitudes mínimas al crear una cuenta. */
const MIN_USERNAME_LENGTH = 3;
const MIN_PASSWORD_LENGTH = 8;

type Mode = 'login' | 'register';

interface LoginPageProps {
  onLogin?: (username: string, password: string) => Promise<void>;
  onRegister?: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ onLogin, onRegister }: LoginPageProps) {
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const isRegister = mode === 'register';
  const submitAction = isRegister ? onRegister : onLogin;

  function changeMode(nextMode: Mode) {
    setMode(nextMode);
    setPassword('');
    setConfirmPassword('');
    setShowPassword(false);
    setShowConfirmPassword(false);
    setError('');
    setSuccess('');
  }

  /** Devuelve el mensaje de error del formulario, o una cadena vacía si es válido. */
  function validate(cleanUsername: string): string {
    if (!cleanUsername || !password.trim()) {
      return 'Introduce tu usuario y contraseña.';
    }

    if (isRegister) {
      if (cleanUsername.length < MIN_USERNAME_LENGTH) {
        return `El usuario debe tener al menos ${MIN_USERNAME_LENGTH} caracteres.`;
      }
      if (password.length < MIN_PASSWORD_LENGTH) {
        return `La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`;
      }
      if (password !== confirmPassword) {
        return 'Las contraseñas no coinciden.';
      }
    }

    return '';
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!submitAction || loading) return;

    const cleanUsername = username.trim();
    const validationError = validate(cleanUsername);

    if (validationError) {
      setError(validationError);
      setSuccess('');
      return;
    }

    setError('');
    setSuccess('');
    setLoading(true);

    try {
      await submitAction(cleanUsername, password);

      if (isRegister) {
        // Cuenta creada: se vuelve al inicio de sesión con el usuario ya escrito.
        changeMode('login');
        setSuccess('Cuenta creada correctamente. Ya puedes iniciar sesión.');
      } else {
        setPassword('');
      }
    } catch {
      setError(
        isRegister
          ? 'No se ha podido crear la cuenta. Es posible que el usuario ya exista; prueba con otro.'
          : 'No se ha podido iniciar sesión. Comprueba tus datos e inténtalo de nuevo.',
      );
    } finally {
      setLoading(false);
    }
  }

  const TitleIcon = isRegister ? UserPlus : LockKeyhole;

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
            <TitleIcon
              aria-hidden="true"
              className="h-6 w-6 text-cyan-400"
            />
          </div>

          <h1 id="login-title" className="text-2xl font-bold">
            {isRegister ? 'Crear cuenta' : 'Acceso al asistente'}
          </h1>

          <p className="mt-2 text-sm text-texto-400">
            {isRegister
              ? 'Regístrate para acceder al asistente y guardar tu historial de conversaciones.'
              : 'Introduce tus credenciales para acceder al diagnóstico técnico documentado.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-5">
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
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                required
                disabled={loading}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-describedby={isRegister ? 'password-hint' : undefined}
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

            {isRegister && (
              <p id="password-hint" className="mt-2 text-xs text-texto-500">
                Mínimo {MIN_PASSWORD_LENGTH} caracteres.
              </p>
            )}
          </div>

          {isRegister && (
            <div>
              <label
                htmlFor="confirm-password"
                className="mb-2 block text-sm font-medium text-texto-200"
              >
                Repetir contraseña
              </label>

              <div className="relative">
                <input
                  id="confirm-password"
                  name="confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  disabled={loading}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  className="w-full rounded-lg border border-contraste/10 bg-fondo px-3 py-3 pr-12 text-sm text-texto-100 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20 disabled:opacity-60"
                />

                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((current) => !current)}
                  disabled={loading}
                  aria-label={
                    showConfirmPassword
                      ? 'Ocultar contraseña'
                      : 'Mostrar contraseña'
                  }
                  aria-controls="confirm-password"
                  className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-lg text-texto-400 hover:text-cyan-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
                >
                  {showConfirmPassword ? (
                    <EyeOff aria-hidden="true" className="h-5 w-5" />
                  ) : (
                    <Eye aria-hidden="true" className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>
          )}

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300"
            >
              {error}
            </p>
          )}

          {success && (
            <p
              role="status"
              className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-300"
            >
              {success}
            </p>
          )}

          {!submitAction && (
            <p
              id="login-availability"
              className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300"
            >
              {isRegister
                ? 'El registro de usuarios todavía no está disponible.'
                : 'El inicio de sesión todavía no está disponible.'}
            </p>
          )}

          <button
            type="submit"
            disabled={!submitAction || loading}
            aria-describedby={!submitAction ? 'login-availability' : undefined}
            className="w-full rounded-lg bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRegister
              ? loading ? 'Creando cuenta…' : 'Crear cuenta'
              : loading ? 'Comprobando acceso…' : 'Iniciar sesión'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-texto-400">
          {isRegister ? '¿Ya tienes cuenta?' : '¿No tienes cuenta?'}{' '}
          <button
            type="button"
            onClick={() => changeMode(isRegister ? 'login' : 'register')}
            disabled={loading}
            className="font-semibold text-cyan-400 hover:text-cyan-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRegister ? 'Inicia sesión' : 'Regístrate'}
          </button>
        </p>

        <p className="mt-4 text-center text-xs text-texto-500">
          Asistente de documentación técnica ARSOFT
        </p>
      </section>
    </main>
  );
}
