// Referencias a las fuentes escritas por el LLM (o guardadas en conversaciones antiguas): se
// ocultan porque las fuentes se muestran como fichas debajo de la respuesta. El modelo las
// escribe de dos formas:
//  - como sección:  "### FUENTE" + el resto de la respuesta
//  - como línea:    "Fuente: ..." / "**Fuente**: ..." / "**Fuentes:** ..." (hasta el final del párrafo)
const SECCION_FUENTE = /\n#{1,6}\s*FUENTES?\b[\s\S]*$/i;
const LINEA_FUENTE = /\n+\*{0,2}FUENTES?(?:\s*:\s*\*{0,2}|\*{0,2}\s*:)[^\n]*(?:\n(?!\n)[^\n]*)*/gi;

export function stripSourceReferences(content: string): string {
  return content.replace(SECCION_FUENTE, '').replace(LINEA_FUENTE, '').trimEnd();
}

interface AnswerSection {
  title: string;
  body: string;
}

export interface ParsedAnswer {
  /** Texto previo al primer encabezado (o toda la respuesta si no hay encabezados). */
  intro: string;
  /** Una sección por encabezado Markdown (CAUSAS POSIBLES, COMPROBACIONES...), en orden. */
  sections: AnswerSection[];
}

const HEADING_LINE = /^#{1,4}[ \t]+(.+?)[ \t]*#*[ \t]*$/;

/** Divide la respuesta del modelo en introducción + secciones por encabezado Markdown. */
export function parseAnswer(content: string): ParsedAnswer {
  const intro: string[] = [];
  const sections: { title: string; lines: string[] }[] = [];
  let inCodeBlock = false;

  for (const line of content.split('\n')) {
    if (line.trim().startsWith('```')) inCodeBlock = !inCodeBlock;
    const heading = inCodeBlock ? null : HEADING_LINE.exec(line);
    if (heading) {
      sections.push({ title: heading[1].replace(/[*_`]/g, '').trim(), lines: [] });
    } else {
      (sections.length > 0 ? sections[sections.length - 1].lines : intro).push(line);
    }
  }

  return {
    intro: intro.join('\n').trim(),
    sections: sections
      .map(({ title, lines }) => ({ title, body: lines.join('\n').trim() }))
      .filter((section) => section.body),
  };
}
