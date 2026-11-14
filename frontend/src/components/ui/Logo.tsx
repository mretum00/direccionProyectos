export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <img src="/logo-arsoft.png" alt="ARSOFT" className="h-9 w-auto flex-shrink-0" />
      <div className="h-7 w-px bg-contraste/10" aria-hidden="true" />
      <div className="leading-tight">
        <div className="text-sm font-bold tracking-wider text-marca-400">AI</div>
        <div className="text-[11px] text-texto-400 tracking-wide">Technical Vehicle Assistant</div>
      </div>
    </div>
  );
}
