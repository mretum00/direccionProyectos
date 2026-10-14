import type { Criticality } from '@/types/chat';
import { AlertOctagon, AlertTriangle, Info, ShieldCheck } from 'lucide-react';

interface CriticalityBadgeProps {
  level: Criticality;
}

const config: Record<Criticality, { label: string; color: string; icon: typeof Info }> = {
  low: { label: 'Baja', color: 'text-green-400 bg-green-500/10 border-green-500/20', icon: ShieldCheck },
  medium: { label: 'Media', color: 'text-amber-400 bg-amber-500/10 border-amber-500/20', icon: Info },
  high: { label: 'Alta', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20', icon: AlertTriangle },
  critical: { label: 'Crítica', color: 'text-red-400 bg-red-500/10 border-red-500/20', icon: AlertOctagon },
};

export function CriticalityBadge({ level }: CriticalityBadgeProps) {
  const { label, color, icon: Icon } = config[level];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${color}`}>
      <Icon className="w-3.5 h-3.5" />
      Criticidad: {label}
    </span>
  );
}
