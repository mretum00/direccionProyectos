import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Eye, EyeOff, Info, Loader2, LockKeyhole, UserPlus } from 'lucide-react';
import { Logo } from '@/components/ui/Logo';
import type { ToastData } from '@/components/ui/Toast';
import { navigate } from '@/router';
import { ApiError } from '@/services/api';
import { useToast } from '@/toast';

/** Mismas reglas que el backend (models/schemas.py): así el error se ve antes de enviar. */
const USERNAME_PATTERN = /^\S{3,50}$/;
const USERNAME_RULES = 'Entre 3 y 50 caracteres, sin espacios.';
const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;

type Mode = 'login' | 'register';
type Field = 'username' | 'password' | 'confirm';
type FieldErrors = Partial<Record<Field, string>>;

/**
 * Traduce el error de la API. Si es de un campo concreto (el usuario ya existe) va debajo de ese
 * campo; el resto (credenciales incorrectas, sin conexión...) se muestra como toast.
 */
function apiError(error: unknown, isRegister: boolean): { field: Field; message: string } | { toast: ToastData } {
  if (error instanceof ApiError) {
    if (isRegister && error.status === 409) return { field: 'username', message: 'Ese usuario ya existe. Prueba con otro.' };
    // 422: el backend dice qué campo ha rechazado (las mismas reglas que se comprueban antes de enviar).
    if (error.status === 422 && error.fields.includes('password')) {
      return { field: 'password', message: passwordRules(isRegister) };
    }
    if (isRegister && error.status === 422 && error.fields.includes('username')) {
      return { field: 'username', message: USERNAME_RULES };
    }
    if (!isRegister && error.status === 401) {
      return {
        toast: { tone: 'peligro', title: 'No se ha podido iniciar sesión', description: 'Usuario o contraseña incorrectos.' },
      };
    }
  }
  if (error instanceof TypeError) {
    return {
      toast: {
        tone: 'peligro',
        title: 'Sin conexión con el servidor',
        description: 'Comprueba que el backend está en marcha e inténtalo de nuevo.',
      },
    };
  }
  return {
    toast: {
      tone: 'peligro',
      title: isRegister ? 'No se ha podido crear la cuenta' : 'No se ha podido iniciar sesión',
      description: 'Ha ocurrido un error en el servidor. Inténtalo de nuevo en unos segundos.',
    },
  };
}

function passwordRules(isRegister: boolean): string {
  return isRegister
    ? `La contraseña debe tener entre ${MIN_PASSWORD_LENGTH} y ${MAX_PASSWORD_LENGTH} caracteres.`
    : `La contraseña no puede tener más de ${MAX_PASSWORD_LENGTH} caracteres.`;
}

/** Texto bajo un campo: el error (en rojo) o, si no hay, la pista de ayuda. */
function FieldMessage({ id, error, hint }: { id: string; error?: string; hint?: ReactNode }) {
  if (error) {
    return (
      <p id={id} className="mt-2 flex items-start gap-1.5 text-xs text-peligro-400">
        <AlertCircle aria-hidden="true" className="mt-px h-3.5 w-3.5 flex-shrink-0" />
        {error}
      </p>
    );
  }
  if (!hint) return null;
  return (
    <p id={id} className="mt-2 text-xs text-texto-500">
      {hint}
    </p>
  );
}

function CapsLockWarning() {
  return (
    <p className="mt-2 flex items-center gap-1.5 text-xs text-aviso-400">
      <Info aria-hidden="true" className="h-3.5 w-3.5" />
      Bloq Mayús está activado.
    </p>
  );
}

const LABEL_CLASS = 'mb-2 block text-sm font-medium text-texto-200';
const TOGGLE_CLASS =
  'absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-lg text-texto-400 hover:text-marca-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-marca-400';

interface LoginPageProps {
  /** Lo decide la ruta: /login o /register. */
  mode: Mode;
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
}

export function LoginPage({ mode, onLogin, onRegister }: LoginPageProps) {
  const toast = useToast();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const inputs = {
    username: useRef<HTMLInputElement>(null),
    password: useRef<HTMLInputElement>(null),
    confirm: useRef<HTMLInputElement>(null),
  };

  const isRegister = mode === 'register';
  const submitAction = isRegister ? onRegister : onLogin;
  const cleanUsername = username.trim().toLowerCase();
  const passwordsMatch = confirmPassword.length > 0 && confirmPassword === password;

  // Al cambiar entre login y registro, el cursor va al primer campo vacío.
  useEffect(() => {
    (username ? inputs.password : inputs.username).current?.focus();
    // Solo al cambiar de modo, no en cada tecla.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  function changeMode(nextMode: Mode) {
    navigate(nextMode === 'register' ? '/register' : '/login');
    setPassword('');
    setConfirmPassword('');
    setShowPassword(false);
    setShowConfirmPassword(false);
    setFieldErrors({});
  }

  /** Al escribir en un campo se borra su error. */
  function edit(field: Field, value: string) {
    ({ username: setUsername, password: setPassword, confirm: setConfirmPassword })[field](value);
    if (fieldErrors[field]) setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  function trackCapsLock(event: KeyboardEvent<HTMLInputElement>) {
    setCapsLock(event.getModifierState('CapsLock'));
  }

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!cleanUsername) errors.username = 'Introduce tu usuario.';
    else if (isRegister && !USERNAME_PATTERN.test(cleanUsername)) errors.username = USERNAME_RULES;

    if (!password) errors.password = 'Introduce tu contraseña.';
    else if (password.length > MAX_PASSWORD_LENGTH || (isRegister && password.length < MIN_PASSWORD_LENGTH)) {
      errors.password = passwordRules(isRegister);
    }

    if (isRegister && !errors.password) {
      if (!confirmPassword) errors.confirm = 'Repite la contraseña.';
      else if (confirmPassword !== password) errors.confirm = 'Las contraseñas no coinciden.';
    }
    return errors;
  }

  // Campo al que llevar el cursor. Se aplica cuando termina el envío: mientras carga, los campos
  // están desactivados y no aceptan el foco.
  const pendingFocus = useRef<Field | null>(null);
  useEffect(() => {
    if (loading || !pendingFocus.current) return;
    inputs[pendingFocus.current].current?.focus();
    pendingFocus.current = null;
  });

  function showErrors(errors: FieldErrors) {
    setFieldErrors(errors);
    pendingFocus.current = (['username', 'password', 'confirm'] as Field[]).find((f) => errors[f]) ?? null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;

    const errors = validate();
    if (Object.keys(errors).length > 0) {
      showErrors(errors);
      return;
    }

    setFieldErrors({});
    setLoading(true);
    try {
      await submitAction(cleanUsername, password);
      if (isRegister) {
        // Cuenta creada: se vuelve al inicio de sesión con el usuario ya escrito.
        changeMode('login');
        toast.show({
          tone: 'exito',
          title: 'Cuenta creada',
          description: `Ya puedes entrar como "${cleanUsername}": introduce tu contraseña.`,
        });
      } else {
        setPassword('');
        navigate('/');
      }
    } catch (e) {
      const result = apiError(e, isRegister);
      if ('field' in result) {
        showErrors({ [result.field]: result.message });
      } else {
        toast.show(result.toast);
        // Credenciales incorrectas: se vacía la contraseña para volver a escribirla.
        if (!isRegister && e instanceof ApiError && e.status === 401) {
          setPassword('');
          pendingFocus.current = 'password';
        }
      }
    } finally {
      setLoading(false);
    }
  }

  const TitleIcon = isRegister ? UserPlus : LockKeyhole;
  const fieldClass = (field: Field, extra = '') =>
    `campo px-3 py-3 ${extra} ${fieldErrors[field] ? 'campo-error' : ''}`.trim();

  return (
    <main className="min-h-screen bg-fondo text-texto-100 flex items-center justify-center px-4 py-10">
      <section
        aria-labelledby="login-title"
        className="panel-flotante w-full max-w-md rounded-2xl p-6 sm:p-8"
      >
        <div className="mb-8 flex items-center justify-between gap-3">
          <Logo />
          <span className="whitespace-nowrap text-xs text-texto-400">
            ThermoDrive HTM-240
          </span>
        </div>

        <div className="mb-6">
          {/* Icono junto al título, igual que en las cabeceras del resto de páginas. */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-marca-500/10">
              <TitleIcon aria-hidden="true" className="h-5 w-5 text-marca-400" />
            </div>
            <h1 id="login-title" className="text-2xl font-bold leading-tight">
              {isRegister ? 'Crear cuenta' : 'Acceso al asistente'}
            </h1>
          </div>

          <p className="mt-3 text-sm text-texto-400">
            {isRegister
              ? 'Regístrate para acceder al asistente y guardar tu historial de conversaciones.'
              : 'Introduce tus credenciales para acceder al diagnóstico técnico documentado.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate aria-busy={loading} className="space-y-5">
          <div>
            <label htmlFor="username" className={LABEL_CLASS}>
              Usuario
            </label>

            <input
              ref={inputs.username}
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              maxLength={50}
              disabled={loading}
              value={username}
              onChange={(event) => edit('username', event.target.value)}
              aria-invalid={!!fieldErrors.username}
              aria-describedby="username-message"
              className={fieldClass('username')}
            />
            <FieldMessage
              id="username-message"
              error={fieldErrors.username}
              hint={isRegister ? USERNAME_RULES : undefined}
            />
          </div>

          <div>
            <label htmlFor="password" className={LABEL_CLASS}>
              Contraseña
            </label>

            <div className="relative">
              <input
                ref={inputs.password}
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                required
                maxLength={MAX_PASSWORD_LENGTH}
                disabled={loading}
                value={password}
                onChange={(event) => edit('password', event.target.value)}
                onKeyUp={trackCapsLock}
                onBlur={() => setCapsLock(false)}
                aria-invalid={!!fieldErrors.password}
                aria-describedby="password-message"
                className={fieldClass('password', 'pr-12')}
              />

              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                disabled={loading}
                aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                aria-controls="password"
                className={TOGGLE_CLASS}
              >
                {showPassword ? (
                  <EyeOff aria-hidden="true" className="h-5 w-5" />
                ) : (
                  <Eye aria-hidden="true" className="h-5 w-5" />
                )}
              </button>
            </div>

            <FieldMessage
              id="password-message"
              error={fieldErrors.password}
              hint={isRegister ? `Entre ${MIN_PASSWORD_LENGTH} y ${MAX_PASSWORD_LENGTH} caracteres.` : undefined}
            />
            {capsLock && <CapsLockWarning />}
          </div>

          {isRegister && (
            <div>
              <label htmlFor="confirm-password" className={LABEL_CLASS}>
                Repetir contraseña
              </label>

              <div className="relative">
                <input
                  ref={inputs.confirm}
                  id="confirm-password"
                  name="confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  maxLength={MAX_PASSWORD_LENGTH}
                  disabled={loading}
                  value={confirmPassword}
                  onChange={(event) => edit('confirm', event.target.value)}
                  onKeyUp={trackCapsLock}
                  onBlur={() => setCapsLock(false)}
                  aria-invalid={!!fieldErrors.confirm}
                  aria-describedby="confirm-message"
                  className={fieldClass('confirm', 'pr-12')}
                />

                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((current) => !current)}
                  disabled={loading}
                  aria-label={showConfirmPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  aria-controls="confirm-password"
                  className={TOGGLE_CLASS}
                >
                  {showConfirmPassword ? (
                    <EyeOff aria-hidden="true" className="h-5 w-5" />
                  ) : (
                    <Eye aria-hidden="true" className="h-5 w-5" />
                  )}
                </button>
              </div>

              {/* Mientras se escribe: confirma en verde que coinciden (el error solo sale al enviar). */}
              {!fieldErrors.confirm && passwordsMatch ? (
                <p id="confirm-message" className="mt-2 flex items-center gap-1.5 text-xs text-exito-400">
                  <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
                  Las contraseñas coinciden.
                </p>
              ) : (
                <FieldMessage id="confirm-message" error={fieldErrors.confirm} />
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primario w-full px-4 py-3 text-sm font-semibold"
          >
            {loading && <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />}
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
            className="font-semibold text-marca-400 hover:text-marca-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-marca-400 disabled:cursor-not-allowed disabled:opacity-50"
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
