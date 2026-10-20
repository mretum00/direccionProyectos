/**
 * Convierte markdown en texto plano de una sola línea para vistas previas
 * (barra lateral, resultados de búsqueda). Omite los títulos (### ...) para que
 * la vista previa muestre el primer contenido real y no el nombre de la sección.
 */
export function toPlainPreview(markdown: string): string {
  const stripInline = (text: string) =>
    text
      .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1') // enlaces e imágenes
      .replace(/(\*\*|__|\*|_|`|~~)/g, '') // negrita, cursiva, código, tachado
      .replace(/^\s*(?:[-*+]|\d+\.)\s+/gm, '') // viñetas y listas numeradas
      .replace(/^\s*>\s?/gm, '') // citas
      .replace(/\s+/g, ' ')
      .trim();

  const withoutHeadings = stripInline(markdown.replace(/^\s{0,3}#{1,6}\s.*$/gm, ' '));
  if (withoutHeadings) return withoutHeadings;
  // Solo había títulos: se muestran sin las almohadillas.
  return stripInline(markdown.replace(/^\s{0,3}#{1,6}\s+/gm, ''));
}
