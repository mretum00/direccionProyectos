import { Cpu } from 'lucide-react';

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/20">
        <Cpu className="w-5 h-5 text-white" />
      </div>
      <div className="leading-tight">
        <div className="text-sm font-bold tracking-wider text-texto">ARSOFT AI</div>
        <div className="text-[10px] text-texto-400 tracking-wide">Technical Vehicle Assistant</div>
      </div>
    </div>
  );
}
