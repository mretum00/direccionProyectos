/** Aviso permanente: HTM-240 es documentación ficticia utilizada con fines educativos. */
export function SafetyNotice() {
  return (
    <aside
      role="note"
      aria-label="Aviso de uso educativo y seguridad"
      className="border-b border-amber-500/25 bg-amber-500/10 px-4 py-2 text-xs leading-relaxed text-amber-100/90"
    >
      <strong className="font-semibold">Aviso de uso educativo:</strong>{' '}
      ThermoDrive utiliza el sistema ficticio HTM-240 y documentación creada para este proyecto.
      No sustituye los manuales oficiales del fabricante ni la evaluación de un profesional.
      Para intervenciones reales, sigue siempre la documentación y los procedimientos de seguridad oficiales.
    </aside>
  );
}
