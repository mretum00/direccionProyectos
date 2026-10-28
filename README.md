# Instalación rápida

## Requisitos previos

- **Python 3** y **Node.js** (con npm) instalados.
- Un archivo `.env` en la raíz del proyecto con tu clave de Groq (ver paso 0).

## 0. Configurar el `.env` (una sola vez)

Desde la raíz del proyecto:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edita `.env` y añade tu clave:

```
GROQ_API_KEY=tu_clave_de_groq
VITE_API_URL=http://localhost:8000
```

> **Importante:** nunca subas el `.env` ni tu clave a Git. Pon la clave solo en `.env`, nunca en `.env.example`.

## 1. Backend (terminal 1)

Desde la raíz del proyecto:

```bash
python -m pip install -r requirements.txt
cd backend
python main.py
```

El backend queda en http://localhost:8000. Compruébalo en http://localhost:8000/api/health.

## 2. Frontend (terminal 2)

Abre una **nueva consola** y, desde la raíz del proyecto:

```bash
cd frontend
npm install
npm run dev
```

## 3. Usar la aplicación

Entra en **http://localhost:5173** y disfruta. 🚀

---

## Notas

- Si `thermodrive_rag.db` no existe, genérala antes de arrancar el backend:

  ```bash
  python backend/db/database_generator.py
  ```

- Si cambias el `.env`, reinicia el backend y el frontend.

---

# ARSOFT AI — Technical Vehicle Assistant

Asistente de documentación técnica para motores industriales, basado en arquitectura RAG (Retrieval-Augmented Generation). El frontend está completamente terminado y preparado para conectar con un backend Python/FastAPI real.

---

## Índice

1. [Qué es y para qué sirve](#1-qué-es-y-para-qué-sirve)
2. [Pantallas y funcionalidades](#2-pantallas-y-funcionalidades)
3. [Arquitectura del proyecto](#3-arquitectura-del-proyecto)
4. [Capas de la aplicación](#4-capas-de-la-aplicación)
5. [Contrato API con el backend](#5-contrato-api-con-el-backend)
6. [Modo mock vs. backend real](#6-modo-mock-vs-backend-real)
7. [Variables de entorno](#7-variables-de-entorno)
8. [Estructura de archivos](#8-estructura-de-archivos)
9. [Poner en marcha el proyecto](#9-poner-en-marcha-el-proyecto)
10. [Backend mock de referencia](#10-backend-mock-de-referencia)

---

## 1. Qué es y para qué sirve

ARSOFT AI es una interfaz de chat técnico que permite a mecánicos consultar la documentación de motores en lenguaje natural y recibir respuestas verificables, con las fuentes exactas de los manuales que respaldan cada respuesta.

El flujo es:

```
Mecánico → consulta en lenguaje natural
         → el backend busca en manuales técnicos (RAG + sqlite-vec)
         → el LLM genera una respuesta con evidencia
         → el frontend muestra la respuesta estructurada + fuentes
```

El frontend **no implementa IA ni búsqueda vectorial**. Toda la inteligencia vive en el backend; el frontend es la interfaz que envía la consulta y renderiza la respuesta estructurada.

---

## 2. Pantallas y funcionalidades

### Chat

- **Pantalla de bienvenida** con 4 sugerencias de consulta rápida (sobrecalentamiento, códigos DTC, EPIs, mantenimiento).
- **Caja de entrada de texto** con soporte de Shift+Enter para saltos de línea, contador de caracteres y envío por Enter.
- **Indicador de carga animado** ("Analizando documentación...") mientras el backend procesa.
- **Respuesta estructurada en tarjetas independientes:**
  - Diagnóstico
  - Criticidad (4 niveles: baja, media, alta, crítica — con color y etiqueta)
  - Alertas de seguridad (warning / crítico) con icono diferenciado
  - EPIs necesarios
  - Posibles causas
  - Comprobaciones numeradas (con referencia al árbol de decisión si aplica)
  - Procedimiento oficial
- **Interpretación de la consulta:** muestra los términos técnicos que el backend identificó.
- **Códigos DTC detectados** como chips con código y descripción.
- **Estado de evidencia:** ALTA / MEDIA / INSUFICIENTE con color indicativo.
- **Confianza numérica** (porcentaje) y número de documentos consultados.
- **Panel de evidencia** — para cada fuente usada se muestra:
  - Documento, tipo, sección, página, versión del motor, fragmento
  - Botón "Ver fuente" que abre un modal con todos los detalles
  - Enlace a PDF original si el backend lo devuelve
- **Documentos descartados** — aviso desplegable si el backend rechazó manuales por versión incompatible.
- **Versión y perfil obligatorios**: el selector de arriba a la derecha empieza vacío y no se puede enviar una consulta hasta elegir ambos; si falta alguno se muestra un aviso y se abre el selector.
- **Gestión de errores** con mensajes en lenguaje natural y botón "Reintentar" que reenvía el último mensaje.
- **Cancelar** una petición en curso.

### Barra lateral — Historial de conversaciones

- **Crear** una nueva conversación.
- **Listar** todas las conversaciones, agrupadas por fecha: Hoy, Ayer, Esta semana, Mes anterior, y por meses pasados.
- **Renombrar** una conversación directamente en la lista (doble clic o botón de edición).
- **Eliminar** con modal de confirmación.
- **Duplicar** una conversación existente.
- **Marcar como favorita** (estrella) para fijarla al inicio.
- **Buscador de conversaciones** en modal:
  - Búsqueda por título y contenido de mensajes
  - Filtro por motor / versión
  - Filtro por fecha (hoy, esta semana, este mes)
  - Resultados en tiempo real con fragmento de contexto
- **Sidebar adaptativo:** visible permanentemente en pantalla grande, drawer deslizante en móvil.

### Cabecera

- Logo ARSOFT.
- Navegación entre Chat y Documentación.
- **Selector de motor y versión:** desplegable compacto con selector de motor (lista) y versión (botones V1.0 / V1.1 / V2.0). Muestra aviso si no se ha seleccionado versión.
- **Distintivo DEMO** cuando la app corre en modo mock.

### Documentación

- Lista de documentos técnicos indexados con nombre, tipo, motor/versión, páginas, fecha y estado de procesamiento (Procesado / Pendiente / Fallido).
- Aviso informativo si el endpoint `GET /api/documents` todavía no está implementado en el backend (degrada con elegancia, sin romper la app).
- Soporte opcional de subida de PDFs (activable con variable de entorno).

---

## 3. Arquitectura del proyecto

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite + Tailwind)        │
│                                                         │
│  src/                                                   │
│  ├── App.tsx                 Raíz + contexto global     │
│  ├── store/appStore.ts       Estado global (Context)    │
│  ├── hooks/                                             │
│  │   ├── useChat.ts          Lógica de envío y errores  │
│  │   └── useConversations.ts CRUD de conversaciones     │
│  ├── services/               Capa de acceso a datos     │
│  │   ├── api.ts              Selecciona mock o real     │
│  │   ├── mockApi.ts          Implementación mock        │
│  │   ├── realApi.ts          Implementación real (HTTP) │
│  │   ├── conversationRepository.ts  Selecciona repo     │
│  │   ├── localConversationRepository.ts  localStorage   │
│  │   └── remoteConversationRepository.ts Backend HTTP   │
│  ├── types/                  Todos los tipos TypeScript │
│  │   ├── chat.ts             Mensajes, respuesta RAG    │
│  │   ├── contract.ts         Interfaces ApiClient       │
│  │   ├── conversation.ts     Modelo de conversación     │
│  │   ├── document.ts         Modelo de documento        │
│  │   └── engine.ts           Motor, versión, sistema    │
│  ├── components/             UI por dominio             │
│  │   ├── chat/               Ventana de chat            │
│  │   ├── conversations/      Sidebar e historial        │
│  │   ├── documents/          Lista de documentos        │
│  │   ├── engine/             Selector motor/versión     │
│  │   ├── sources/            Panel de evidencia         │
│  │   └── ui/                 Header, Logo, Modal        │
│  ├── pages/                  ChatPage, DocumentsPage    │
│  └── utils/dateUtils.ts      Agrupación por fecha       │
└─────────────────────────────────────────────────────────┘
                          │
              POST /api/chat  (obligatorio)
              GET  /api/documents (opcional)
                          │
┌─────────────────────────────────────────────────────────┐
│  Backend Python/FastAPI  (pendiente de implementar)     │
│                                                         │
│  SQLite + sqlite-vec → búsqueda vectorial de fragmentos │
│  Groq LLM            → generación con contexto RAG      │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Capas de la aplicación

### Estado global (`src/store/appStore.ts`)

Context API de React. Almacena:
- Lista de conversaciones y la conversación activa
- Selección de motor/versión/sistema/perfil/vehículo

### Hooks de lógica

| Hook | Responsabilidad |
|------|-----------------|
| `useChat` | Envío de mensajes, gestión de errores (red / servidor), retry, cancel, historial de 7 turnos |
| `useConversations` | Crear, renombrar, eliminar, duplicar, marcar favorita, persistir |

### Capa de servicios (intercambiable por variable de entorno)

| Servicio | Función |
|----------|---------|
| `api.ts` | Selecciona `mockApi` o `realApi` según `VITE_USE_MOCK` |
| `mockApi.ts` | Simula respuestas con delay realista (800–1500 ms) |
| `realApi.ts` | Hace `fetch` al backend real en `VITE_API_URL` |
| `conversationRepository.ts` | Selecciona `local` o `remote` según `VITE_REMOTE_CONVERSATIONS` |
| `localConversationRepository.ts` | Persiste en `localStorage` |
| `remoteConversationRepository.ts` | Persiste en el backend vía HTTP |

### Tipos TypeScript

Todos los tipos que el backend debe respetar están definidos en `src/types/`. Son la fuente de verdad compartida entre frontend y backend.

---

## 5. Contrato API con el backend

Ver el documento completo en [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

### Endpoint imprescindible

```
POST /api/chat
```

**Petición mínima:**
```json
{
  "conversation_id": "uuid",
  "message": "El motor se calienta en exceso",
  "engine": "ThermoDrive HTM-240",
  "engine_version": "V2.0",
  "profile": "mechanic",
  "history": []
}
```

**Respuesta mínima que acepta el frontend:**
```json
{
  "message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Respuesta del LLM"
  }
}
```

El frontend es tolerante a respuesta parcial: si no llegan `sections`, `sources` ni `evidence_status`, simplemente muestra el texto de `message.content`. Nada se rompe por campos opcionales ausentes.

**Respuesta completa** (cuando el backend está plenamente implementado):
```json
{
  "message": { "id": "...", "role": "assistant", "content": "..." },
  "evidence_status": "high",
  "confidence": 0.92,
  "documents_consulted": 3,
  "interpreted_query": { "original": "...", "technical_terms": ["..."] },
  "detected_dtc": [{ "code": "P0217", "description": "..." }],
  "sections": {
    "diagnosis": "...",
    "possible_causes": ["..."],
    "criticality": "high",
    "safety": [{ "level": "warning", "text": "..." }],
    "ppe": ["..."],
    "checks": ["..."],
    "decision_tree_id": "DT-001",
    "procedure": "..."
  },
  "sources": [
    {
      "id": "uuid",
      "document": "Manual técnico HTM-240",
      "source_type": "manual",
      "section": "Capítulo 4.3",
      "page": 87,
      "engine_version": "V2.0",
      "excerpt": "...",
      "url": "https://..."
    }
  ],
  "discarded_sources": [
    { "document": "Manual HTM-240 V1.0", "reason": "version_mismatch" }
  ]
}
```

### Endpoints opcionales

| Endpoint | Método | Uso |
|----------|--------|-----|
| `/api/health` | GET | Comprobar que el backend está vivo |
| `/api/documents` | GET | Listar documentos indexados |
| `/api/documents` | POST | Subir un PDF nuevo |
| `/api/sources/{id}` | GET | Fragmento / URL de una fuente |
| `/api/conversations` | GET/POST | Solo con `VITE_REMOTE_CONVERSATIONS=true` |
| `/api/conversations/{id}` | GET/PUT/DELETE | Ídem |

---

## 6. Modo mock vs. backend real

El frontend arranca en modo **mock** por defecto. No necesita ningún backend para funcionar.

| Variable | Valor | Efecto |
|----------|-------|--------|
| `VITE_USE_MOCK` | `true` (defecto) | Usa datos simulados, sin red |
| `VITE_USE_MOCK` | `false` | Hace peticiones reales al backend |

Para conectar el backend real:
1. Implementar `POST /api/chat` en Python/FastAPI
2. En `.env`, cambiar `VITE_USE_MOCK=false`
3. Comprobar que `VITE_API_URL` apunta al backend correcto
4. Reiniciar la app

---

## 7. Variables de entorno

Copiar `.env.example` a `.env`:

```bash
cp .env.example .env
```

| Variable | Defecto | Descripción |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | URL base del backend |
| `VITE_USE_MOCK` | `true` | `true` = mock, `false` = backend real |
| `VITE_REMOTE_CONVERSATIONS` | `false` | `true` = conversaciones en el backend |
| `VITE_ENABLE_DOCUMENT_UPLOAD` | `false` | Activar subida de PDFs |

---

## 8. Estructura de archivos

```
├── src/
│   ├── App.tsx
│   ├── index.css
│   ├── main.tsx
│   ├── hooks/
│   │   ├── useChat.ts
│   │   └── useConversations.ts
│   ├── pages/
│   │   ├── ChatPage.tsx
│   │   └── DocumentsPage.tsx
│   ├── services/
│   │   ├── api.ts
│   │   ├── mockApi.ts
│   │   ├── mockData.ts
│   │   ├── realApi.ts
│   │   ├── conversationRepository.ts
│   │   ├── localConversationRepository.ts
│   │   └── remoteConversationRepository.ts
│   ├── store/
│   │   └── appStore.ts
│   ├── types/
│   │   ├── chat.ts
│   │   ├── contract.ts
│   │   ├── conversation.ts
│   │   ├── document.ts
│   │   └── engine.ts
│   ├── utils/
│   │   └── dateUtils.ts
│   └── components/
│       ├── chat/
│       │   ├── ChatWindow.tsx
│       │   ├── ChatError.tsx
│       │   ├── CriticalityBadge.tsx
│       │   ├── EvidenceStatus.tsx
│       │   ├── Message.tsx
│       │   ├── MessageInput.tsx
│       │   ├── ResponseSections.tsx
│       │   ├── SafetyWarning.tsx
│       │   ├── ThinkingIndicator.tsx
│       │   └── WelcomeScreen.tsx
│       ├── conversations/
│       │   ├── ConfirmationModal.tsx
│       │   ├── ConversationItem.tsx
│       │   ├── ConversationSearch.tsx
│       │   └── ConversationSidebar.tsx
│       ├── documents/
│       │   └── DocumentList.tsx
│       ├── engine/
│       │   ├── ContextPanel.tsx
│       │   └── EngineSelector.tsx
│       ├── sources/
│       │   ├── DiscardedSources.tsx
│       │   ├── EvidencePanel.tsx
│       │   ├── SourceCard.tsx
│       │   └── SourceModal.tsx
│       └── ui/
│           ├── DemoBadge.tsx
│           ├── Header.tsx
│           ├── Logo.tsx
│           └── Modal.tsx
├── docs/
│   └── API_CONTRACT.md        Contrato completo frontend ↔ backend
├── backend-mock/
│   ├── main.py                FastAPI de referencia con todos los modelos Pydantic
│   └── requirements.txt
├── public/
│   └── assets/
│       └── Logo_Arsoft.png
├── .env.example
└── package.json
```

---

## 9. Poner en marcha el proyecto

### Requisitos

- Node.js 18+
- npm 9+

### Instalación y arranque

```bash
# Instalar dependencias
npm install

# Copiar variables de entorno
cp .env.example .env

# Arrancar en modo desarrollo (mock activado por defecto)
npm run dev
```

La app estará disponible en `http://localhost:5173`.

### Build de producción

```bash
npm run build
```

### TypeScript check

```bash
npm run typecheck
```

---

## 10. Backend mock de referencia

En `backend-mock/main.py` hay un servidor FastAPI con todos los modelos Pydantic que definen el contrato de la API. **No implementa lógica RAG** — es una guía de arranque para el equipo de backend.

```bash
cd backend-mock
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Una vez arrancado, cambiar `VITE_USE_MOCK=false` en `.env` y reiniciar la app. El único endpoint que realmente necesita estar implementado para que el chat funcione es `POST /api/chat`.

El esquema completo de RAG previsto:

```
POST /api/chat
    ↓
Embeddings de la consulta (sentence-transformers)
    ↓
sqlite-vec: búsqueda vectorial, filtrado por motor + versión
    ↓
Top-K fragmentos relevantes
    ↓
Groq LLM (llama-3.1-70b-versatile o similar)
con contexto: fragmentos + historial + instrucciones de perfil
    ↓
Respuesta estructurada JSON según el contrato
```

---

## Tecnologías utilizadas

| Capa | Tecnología |
|------|-----------|
| UI | React 18 + TypeScript 5 |
| Bundler | Vite 5 |
| Estilos | Tailwind CSS 3 |
| Iconos | Lucide React |
| Estado | React Context API |
| Persistencia local | localStorage |
| Backend mock | Python 3 + FastAPI + Pydantic v2 |

---

*ARSOFT — Build Your Virtual World*
