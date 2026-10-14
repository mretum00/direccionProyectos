import type { AssistantResponse } from '@/types/chat';
import type { TechnicalDocument } from '@/types/document';
import type { Conversation } from '@/types/conversation';

export function uuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export const MOCK_DOCUMENTS: TechnicalDocument[] = [
  { id: 'doc-001', filename: 'Manual técnico HTM-240 V2.0', type: 'manual', engine: 'ThermoDrive HTM-240', engine_version: 'V2.0', pages: 312, uploaded_at: '2025-08-15T10:00:00Z', status: 'processed' },
  { id: 'doc-002', filename: 'Catálogo DTC HTM-240', type: 'dtc_catalog', engine: 'ThermoDrive HTM-240', engine_version: 'V2.0', pages: 48, uploaded_at: '2025-08-15T10:05:00Z', status: 'processed' },
  { id: 'doc-003', filename: 'Árboles de decisión HTM-240', type: 'decision_tree', engine: 'ThermoDrive HTM-240', engine_version: 'V2.0', pages: 36, uploaded_at: '2025-08-16T08:30:00Z', status: 'processed' },
  { id: 'doc-004', filename: 'Casos históricos HTM-240', type: 'historical_case', engine: 'ThermoDrive HTM-240', engine_version: 'V2.0', pages: 72, uploaded_at: '2025-08-17T12:00:00Z', status: 'processed' },
  { id: 'doc-005', filename: 'Glosario técnico HTM-240', type: 'glossary', engine: 'ThermoDrive HTM-240', engine_version: 'V2.0', pages: 28, uploaded_at: '2025-08-17T12:15:00Z', status: 'processed' },
  { id: 'doc-006', filename: 'Manual de seguridad HTM-240', type: 'safety_manual', engine: 'ThermoDrive HTM-240', engine_version: 'V2.0', pages: 54, uploaded_at: '2025-08-18T09:00:00Z', status: 'processed' },
  { id: 'doc-007', filename: 'Manual técnico HTM-240 V1.1', type: 'manual', engine: 'ThermoDrive HTM-240', engine_version: 'V1.1', pages: 286, uploaded_at: '2024-03-10T08:00:00Z', status: 'processed' },
  { id: 'doc-008', filename: 'Manual técnico HTM-240 V1.0', type: 'manual', engine: 'ThermoDrive HTM-240', engine_version: 'V1.0', pages: 264, uploaded_at: '2023-06-20T08:00:00Z', status: 'processed' },
];

const fullResponse = (): AssistantResponse => ({
  message: { id: uuid(), role: 'assistant', content: 'El sobrecalentamiento del motor ThermoDrive HTM-240 V2.0 junto con olor a quemado indica una posible avería en el circuito de refrigeración o en el sistema de combustión. Se ha consultado el manual técnico y el catálogo DTC para determinar las causas más probables.' },
  evidence_status: 'high',
  needs_clarification: false,
  confidence: 0.92,
  documents_consulted: 3,
  interpreted_query: {
    original: 'se enciende el testigo de temperatura y huele a quemado',
    technical_terms: ['sobrecalentamiento', 'sobrecarga térmica', 'deterioro por temperatura'],
  },
  detected_dtc: [{ code: 'P0217', description: 'Sobrecalentamiento del motor' }],
  sections: {
    diagnosis: 'Sobrecalentamiento del motor con posible deterioro de componentes por temperatura elevada. El olor a quemado sugiere contacto de fluidos con superficies calientes o deterioro de correas.',
    possible_causes: [
      'Nivel bajo de refrigerante en el circuito CIR-01',
      'Termostato bloqueado en posición cerrada',
      'Bomba de refrigerante con bajo rendimiento',
      'Fuga en el radiador o manguitos',
      'Correa de accesorios deteriorada',
    ],
    criticality: 'high',
    safety: [
      { level: 'warning', text: 'No abrir el tapón del radiador en caliente. Riesgo de quemaduras por proyección de líquido a presión.' },
      { level: 'warning', text: 'Dejar enfriar el motor al menos 30 minutos antes de inspeccionar.' },
    ],
    ppe: ['Guantes térmicos resistentes', 'Gafas de protección', 'Calzado de seguridad'],
    checks: [
      'Verificar nivel de refrigerante en el depósito de expansión',
      'Inspeccionar termostato: comprobar apertura a 87°C',
      'Comprobar funcionamiento de la bomba de refrigerante',
      'Revisar estado de manguitos y abrazaderas',
      'Verificar integridad del radiador y ausencia de fugas',
    ],
    decision_tree_id: 'DT-014',
    procedure: '1. Detener el vehículo y apagar el motor. 2. Esperar 30 minutos para enfriamiento. 3. Verificar nivel de refrigerante con motor frío. 4. Si el nivel es bajo, rellenar con refrigerante especificado y buscar el origen de la fuga. 5. Comprobar el termostato en banco de pruebas. 6. Si el termostato no abre, sustituir por uno nuevo. 7. Realizar una prueba de circulación con motor en marcha y verificar que la temperatura se estabiliza entre 85°C y 95°C.',
  },
  sources: [
    {
      id: 'src-001',
      document: 'Manual técnico HTM-240 V2.0',
      source_type: 'manual',
      section: 'Sección 4.3 - Sistema de refrigeración',
      page: 142,
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      system: 'CIR-01',
      excerpt: 'El sistema de refrigeración del HTM-240 V2.0 mantiene la temperatura de funcionamiento entre 85°C y 95°C. El termostato abre a 87°C ± 2°C. Un nivel bajo de refrigerante o un termostato bloqueado son las causas más frecuentes de sobrecalentamiento.',
    },
    {
      id: 'src-002',
      document: 'Catálogo DTC HTM-240',
      source_type: 'dtc_catalog',
      section: 'Códigos P02xx',
      page: 18,
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      system: 'CIR-01',
      excerpt: 'P0217: Sobrecalientamiento del motor. Activación cuando la temperatura del refrigerante supera los 110°C durante más de 10 segundos. Acción recomendada: verificar circuito de refrigeración y termostato.',
    },
    {
      id: 'src-003',
      document: 'Árboles de decisión HTM-240',
      source_type: 'decision_tree',
      section: 'Árbol DT-014',
      page: 22,
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      system: 'CIR-01',
      excerpt: 'DT-014: Sobrecalentamiento. Paso 1: ¿Nivel de refrigerante correcto? No → Repostar y buscar fuga. Sí → Paso 2: ¿Termostato abre correctamente? No → Sustituir termostato. Sí → Paso 3: Comprobar bomba de refrigerante.',
    },
  ],
});

const partialResponse = (): AssistantResponse => ({
  message: { id: uuid(), role: 'assistant', content: 'El código DTC P0217 corresponde a un sobrecalientamiento del motor. Este código se activa cuando la temperatura del refrigerante supera los 110°C durante más de 10 segundos. La causa más habitual es un fallo en el circuito de refrigeración.' },
  evidence_status: 'medium',
  documents_consulted: 2,
  sources: [
    {
      id: 'src-partial-1',
      document: 'Catálogo DTC HTM-240',
      source_type: 'dtc_catalog',
      section: 'Códigos P02xx',
      page: 18,
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      system: 'CIR-01',
      excerpt: 'P0217: Sobrecalientamiento del motor. Activación cuando la temperatura del refrigerante supera los 110°C durante más de 10 segundos.',
    },
  ],
});

const clarificationResponse = (): AssistantResponse => ({
  message: { id: uuid(), role: 'assistant', content: 'Para responder con precisión sobre el par de apriete necesito que indiques la versión del motor, ya que los valores difieren entre versiones.' },
  evidence_status: 'medium',
  needs_clarification: true,
  clarification: {
    message: 'Necesito información adicional para buscar la documentación correcta.',
    missing_fields: [
      { key: 'engine_version', label: 'Versión del motor', options: ['V1.0', 'V1.1', 'V2.0'] },
      { key: 'component', label: 'Componente específico (culata, tornillo de biela, etc.)' },
    ],
  },
});

const insufficientResponse = (): AssistantResponse => ({
  message: { id: uuid(), role: 'assistant', content: 'No he encontrado evidencia suficiente en la documentación disponible para responder con seguridad sobre este tema. La documentación consultada no incluye información específica sobre la consulta realizada.' },
  evidence_status: 'insufficient',
  documents_consulted: 4,
});

const highVoltageResponse = (): AssistantResponse => ({
  message: { id: uuid(), role: 'assistant', content: 'Para trabajar en el sistema de alta tensión CIR-02 del ThermoDrive HTM-240 V2.0 es obligatorio seguir el procedimiento de descarga y utilizar los EPIs especificados. El sistema opera a 400V DC y requiere desconexión certificada.' },
  evidence_status: 'high',
  confidence: 0.95,
  documents_consulted: 2,
  sections: {
    diagnosis: 'Trabajo en sistema de alta tensión CIR-02. Procedimiento de intervención con desconexión y verificación de ausencia de tensión.',
    criticality: 'critical',
    safety: [
      { level: 'critical', text: 'Riesgo de electrocución. El sistema CIR-02 opera a 400V DC. No intervenir sin haber desconectado y verificado la ausencia de tensión.' },
      { level: 'critical', text: 'Esperar al menos 15 minutos tras la desconexión para que se descarguen los condensadores.' },
    ],
    ppe: [
      'Guantes dieléctricos clase 2 (1000V)',
      'Calzado dieléctrico',
      'Gafas de protección facial integral',
      'Manta aislante',
      'Detector de tensión certificado',
    ],
    checks: [
      'Desconectar el sistema de alta tensión mediante el interruptor principal',
      'Verificar ausencia de tensión con detector certificado',
      'Aplicar bloqueo y etiquetado (LOTO)',
      'Esperar 15 minutos para descarga de condensadores',
    ],
    procedure: '1. Desconectar el interruptor principal de alta tensión. 2. Aplicar bloqueo y etiquetado. 3. Esperar 15 minutos. 4. Verificar ausencia de tensión con detector certificado en todos los polos. 5. Colocar manta aislante sobre zonas adyacentes. 6. Proceder con la intervención.',
  },
  sources: [
    {
      id: 'src-hv-1',
      document: 'Manual de seguridad HTM-240',
      source_type: 'safety_manual',
      section: 'Sección 2 - Alta tensión',
      page: 12,
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      system: 'CIR-02',
      excerpt: 'El sistema CIR-02 opera a 400V DC. Toda intervención requiere desconexión, verificación de ausencia de tensión y uso de EPIs dieléctricos. Tiempo de descarga de condensadores: 15 minutos mínimo.',
    },
  ],
});

const discardedResponse = (): AssistantResponse => ({
  message: { id: uuid(), role: 'assistant', content: 'El intervalo de mantenimiento para el ThermoDrive HTM-240 V2.0 establece cambios de aceite cada 500 horas de funcionamiento y revisión completa cada 2000 horas. Se ha descartado la documentación de la versión V1.0 por contener intervalos obsoletos.' },
  evidence_status: 'high',
  confidence: 0.89,
  documents_consulted: 3,
  sections: {
    diagnosis: 'Intervalos de mantenimiento aplicables a la versión V2.0.',
    possible_causes: [],
    criticality: 'low',
    checks: [
      'Cambio de aceite: cada 500 horas',
      'Filtro de aceite: sustituir en cada cambio de aceite',
      'Revisión completa: cada 2000 horas',
      'Inspección de correas: cada 1000 horas',
    ],
  },
  sources: [
    {
      id: 'src-maint-1',
      document: 'Manual técnico HTM-240 V2.0',
      source_type: 'manual',
      section: 'Sección 1 - Mantenimiento periódico',
      page: 24,
      engine: 'ThermoDrive HTM-240',
      engine_version: 'V2.0',
      system: 'CIR-01',
      excerpt: 'V2.0: Intervalo de cambio de aceite 500h. Revisión completa 2000h. Inspección de correas 1000h. Estos intervalos sustituyen a los de versiones anteriores.',
    },
  ],
  discarded_sources: [
    { document: 'Manual técnico HTM-240 V1.0', reason: 'obsolete_version', detail: 'Los intervalos de mantenimiento de la V1.0 (cambio de aceite cada 300h) han sido reemplazados por los de la V2.0.' },
  ],
});

const responseMap: { match: RegExp; build: () => AssistantResponse }[] = [
  { match: /alta.tensión|epi|circuit.*02|CIR-02/i, build: highVoltageResponse },
  { match: /P0217|código|codigo.*dtc|dtc/i, build: partialResponse },
  { match: /par.*apriete|apriete|qué.*par|que.*par/i, build: clarificationResponse },
  { match: /mantenimiento|intervalo|revisión|revision/i, build: discardedResponse },
  { match: /calienta|sobrecalent|quemado|temperatura|testigo/i, build: fullResponse },
];

export function mockChatResponse(message: string): AssistantResponse {
  for (const { match, build } of responseMap) {
    if (match.test(message)) return build();
  }
  return insufficientResponse();
}

export const MOCK_CONVERSATIONS: Conversation[] = [];
