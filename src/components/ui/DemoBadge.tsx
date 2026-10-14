import { Database } from 'lucide-react';

export function DemoBadge() {
  return (
    <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px] font-medium">
      <Database className="w-3 h-3" />
      <span>Datos de demostración</span>
    </div>
  );
}
