import { Settings, Info, Database, Cpu, Shield } from 'lucide-react';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
const REMOTE_CONVERSATIONS = import.meta.env.VITE_REMOTE_CONVERSATIONS === 'true';
const ENABLE_UPLOAD = import.meta.env.VITE_ENABLE_DOCUMENT_UPLOAD === 'true';

export function SettingsPage() {
  const settings = [
    { icon: Cpu, label: 'Modo de IA', value: USE_MOCK ? 'Demostración (mock)' : 'Backend real', hint: USE_MOCK ? 'Los datos son simulados' : 'Conectado a la API real' },
    { icon: Database, label: 'Almacenamiento de conversaciones', value: REMOTE_CONVERSATIONS ? 'Backend remoto' : 'Local (localStorage)', hint: REMOTE_CONVERSATIONS ? 'Sincronizado con el servidor' : 'Guardado en el navegador' },
    { icon: Shield, label: 'Subida de documentos', value: ENABLE_UPLOAD ? 'Activada' : 'Desactivada', hint: ENABLE_UPLOAD ? 'Se pueden subir PDFs' : 'No disponible hasta que el backend lo soporte' },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center">
            <Settings className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Ajustes</h2>
            <p className="text-xs text-gray-500">Configuración de la aplicación</p>
          </div>
        </div>

        <div className="space-y-3">
          {settings.map(({ icon: Icon, label, value, hint }) => (
            <div key={label} className="flex items-center gap-3 p-4 rounded-xl bg-[#151518] border border-white/5">
              <div className="w-9 h-9 rounded-md bg-white/5 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-gray-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-200">{label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{hint}</div>
              </div>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-md flex-shrink-0 ${
                value.includes('Activada') || value.includes('Backend') || value.includes('remoto')
                  ? 'text-green-400 bg-green-500/10'
                  : 'text-gray-400 bg-white/5'
              }`}>
                {value}
              </span>
            </div>
          ))}

          <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-500/5 border border-blue-500/10">
            <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-400">
              Para cambiar la configuración, edita las variables de entorno en el archivo <code className="text-cyan-400">.env</code> y reinicia la aplicación.
              El equipo de backend debe implementar primero el endpoint <code className="text-cyan-400">POST /api/chat</code> para conectar la IA real.
            </p>
          </div>

          <div className="flex items-start gap-3 p-4 rounded-xl bg-white/5 border border-white/5">
            <Shield className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-500">
              Los roles Administrador y Supervisor están previstos para futuras versiones.
              La arquitectura está preparada para roles, pero no se implementa autenticación completa en esta versión.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
