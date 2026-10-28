// El logo es de la empresa y se muestra sin modificar: la tarjeta clara
// garantiza el contraste del texto azul marino sobre el tema oscuro.
export function Logo() {
  return (
    <div className="flex items-center min-w-0">
      <div className="rounded-lg bg-white px-2.5 py-1.5 ring-1 ring-contraste/10 shadow-sm shadow-black/10">
        <img
          src="/assets/arsoft-logo.webp"
          alt="ARSOFT"
          className="h-6 w-auto object-contain"
        />
      </div>
    </div>
  );
}
