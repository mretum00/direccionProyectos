import type { EvidenceStatus as EvidenceStatusType } from '@/types/chat';
import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react';

interface EvidenceStatusProps {
  status?: EvidenceStatusType;
  confidence?: number;
  documentsConsulted?: number;
}

export function EvidenceStatus({ status, confidence, documentsConsulted }: EvidenceStatusProps) {
  if (!status) return null;

  const config = {
    high: {
      label: 'Evidencia: ALTA',
      color: 'text-green-400 bg-green-500/10 border-green-500/20',
      icon: ShieldCheck,
    },
    medium: {
      label: 'Evidencia: MEDIA',
      color: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
      icon: ShieldAlert,
    },
    insufficient: {
      label: 'Evidencia insuficiente',
      color: 'text-red-400 bg-red-500/10 border-red-500/20',
      icon: ShieldX,
    },
  }[status];

  const { icon: Icon } = config;

  if (status === 'insufficient') {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Icon className="w-5 h-5 text-red-400" />
          <h4 className="text-sm font-semibold text-red-400">Evidencia insuficiente</h4>
        </div>
        <p className="text-sm text-red-300">
          No he encontrado evidencia suficiente en la documentación disponible para responder con seguridad.
        </p>
        {documentsConsulted !== undefined && (
          <p className="text-xs text-red-400/70 mt-2">
            Documentación consultada: {documentsConsulted} documentos
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${config.color}`}>
        <Icon className="w-3.5 h-3.5" />
        {config.label}
      </span>
      {confidence !== undefined && (
        <span className="text-xs text-gray-500">
          Confianza: {Math.round(confidence * 100)}%
        </span>
      )}
      {documentsConsulted !== undefined && (
        <span className="text-xs text-gray-500">
          · {documentsConsulted} documentos consultados
        </span>
      )}
    </div>
  );
}
