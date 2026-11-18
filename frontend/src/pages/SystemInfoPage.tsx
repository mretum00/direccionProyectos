import { Cpu, Info, Layers } from 'lucide-react';
import { config } from '@/config';
import { useAppStore } from '@/store/appStore';
import { ENGINE_NAME } from '@/types/engine';
import { InfoRow, PageLayout } from '@/components/ui/PageLayout';

/** Información de solo lectura sobre la instalación (no hay nada que configurar aquí). */
export function SystemInfoPage() {
  const { versions } = useAppStore();

  const rows = [
    {
      icon: Cpu,
      title: 'Backend',
      detail: 'URL del servidor de IA (VITE_API_URL en el .env)',
      value: config.apiUrl || 'No configurado',
      ok: !!config.apiUrl,
    },
    {
      icon: Layers,
      title: 'Versiones disponibles',
      detail: `Versiones de ${ENGINE_NAME} que cubre la documentación (las indica el backend)`,
      value: versions.length > 0 ? versions.join(' · ') : 'Sin conexión',
      ok: versions.length > 0,
    },
  ];

  return (
    <PageLayout icon={Info} title="Información del sistema" subtitle="Estado de la instalación">
      <div className="grid grid-cols-1 gap-2">
        {rows.map(({ icon, title, detail, value, ok }) => (
          <div key={title} className="tarjeta fila">
            <InfoRow
              icon={icon}
              title={title}
              detail={detail}
              badge={
                <span className={`${ok ? 'insignia-exito' : 'insignia-neutra'} flex-shrink-0 max-w-[50%] truncate`}>
                  {value}
                </span>
              }
            />
          </div>
        ))}
      </div>

      <div className="alerta-info mt-4 rounded-lg p-3 text-xs">
        <Info className="w-4 h-4 flex-shrink-0 mt-px" />
        <p className="text-texto-400">
          La URL del backend sale de <code className="text-marca-400">VITE_API_URL</code>, en el archivo{' '}
          <code className="text-marca-400">.env</code> de la raíz del repositorio: para cambiarla, edítalo y reinicia
          el frontend. Las versiones están definidas en el backend (<code className="text-marca-400">ENGINE_VERSIONS</code>{' '}
          en <code className="text-marca-400">backend/config.py</code>).
        </p>
      </div>
    </PageLayout>
  );
}
