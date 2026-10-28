import { Settings, Info, Database, Cpu, Shield } from 'lucide-react';
import { config } from '@/config';

const SETTINGS = [
  {
    icon: Cpu,
    label: 'Backend',
    value: config.apiUrl || 'No configurado',
    hint: 'URL del servidor de IA (VITE_API_URL)',
    positive: !!config.apiUrl,
  },
  {
    icon: Database,
    label: 'Almacenamiento de conversaciones',
    value: config.remoteConversations ? 'Backend remoto' : 'Local (localStorage)',
    hint: config.remoteConversations ? 'Sincronizado con el servidor' : 'Guardado en el navegador',
    positive: config.remoteConversations,
  },
  {
    icon: Shield,
    label: 'Subida de documentos',
    value: config.enableDocumentUpload ? 'Activada' : 'Desactivada',
    hint: config.enableDocumentUpload ? 'Se pueden subir PDFs' : 'No disponible hasta que el backend lo soporte',
    positive: config.enableDocumentUpload,
  },
];

export function SettingsPage() {

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center">
            <Settings className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-texto">Ajustes</h2>
            <p className="text-xs text-texto-500">Configuración de la aplicación</p>
          </div>
        </div>

        <div className="space-y-3">
          {SETTINGS.map(({ icon: Icon, label, value, hint, positive }) => (
            <div key={label} className="flex items-center gap-3 p-4 rounded-xl bg-tarjeta border border-contraste/5">
              <div className="w-9 h-9 rounded-md bg-contraste/5 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-texto-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-texto-200">{label}</div>
                <div className="text-xs text-texto-500 mt-0.5">{hint}</div>
              </div>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-md flex-shrink-0 max-w-[50%] truncate ${
                positive ? 'text-green-400 bg-green-500/10' : 'text-texto-400 bg-contraste/5'
              }`}>
                {value}
              </span>
            </div>
          ))}

          <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-500/5 border border-blue-500/10">
            <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-texto-400">
              Para cambiar la configuración, edita las variables de entorno en el archivo <code className="text-cyan-400">.env</code> de la raíz del repositorio y reinicia la aplicación.
            </p>
          </div>

          <div className="flex items-start gap-3 p-4 rounded-xl bg-contraste/5 border border-contraste/5">
            <Shield className="w-4 h-4 text-texto-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-texto-500">
              Los roles Administrador y Supervisor están previstos para futuras versiones.
              La arquitectura está preparada para roles, pero no se implementa autenticación completa en esta versión.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
