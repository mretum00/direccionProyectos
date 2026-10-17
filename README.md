# direccionProyectos

Asistente técnico ARSOFT AI (ThermoDrive). El repositorio está separado en frontend (React/Vite) y backend (Python/FastAPI).

- Grupo 2: primero subir vuestro código a la rama de backend. Antes de subirlo a la rama principal.
- Grupo 3: primero subir vuestro código a la rama de frontend. Antes de subirlo a la rama principal.

El contrato entre ambos lados está en [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

## Estructura

```
.env.example              Plantilla de variables de entorno (se versiona)
.env                      Variables reales, compartidas por front y back (NO se versiona)
requirements.txt          Dependencias de Python del backend
thermodrive_rag.db        Base de datos vectorial (la genera backend/db/database_generator.py)
frontend/                 Interfaz React + Vite
  src/config.ts           Única lectura de variables VITE_* del frontend
  src/controllers/        Capa HTTP hacia el backend (fetch, errores, validación mínima)
  src/services/           Fachada `api` para la UI y repositorios de conversaciones
  src/hooks/useChat.ts    Envío de la pregunta (+ motor/versión) y estado de la consulta
backend/                  API FastAPI
  config.py               Única lectura de variables de entorno del backend
  main.py                 Arranque, CORS y registro de rutas
  controllers/            Endpoints HTTP
  services/rag_pipeline.py  Pipeline RAG a completar por el equipo (ver "Reparto del pipeline RAG")
  models/schemas.py       Modelos Pydantic del contrato
  db/                     Generador de la BD vectorial y persistencia de conversaciones
docs/                     Contrato API
```

## Requisitos

- **Node.js** (con npm) para el frontend.
- **Python 3** para el backend.
- Las dependencias de Python están en [`requirements.txt`](requirements.txt), **en la raíz del repositorio**.
- Un archivo **`.env` en la raíz del repositorio** (ver siguiente sección).
- Una clave de Groq (`GROQ_API_KEY`) para que el backend pueda generar respuestas.

## Variables de entorno (`.env` en la raíz)

El `.env` vive en la **raíz del repo**, no dentro de `frontend/` ni de `backend/`. Lo leen los dos lados:

- **Frontend (Vite):** `frontend/vite.config.ts` apunta a la carpeta padre con `envDir`. Solo las variables con prefijo `VITE_` llegan al navegador, así que **nunca pongas secretos con ese prefijo**. El código las lee únicamente en `frontend/src/config.ts`.
- **Backend (FastAPI):** `backend/config.py` carga `../.env` de forma explícita (no depende del directorio desde el que se lance). Es el único módulo que lee variables de entorno.

Crea el tuyo copiando la plantilla, desde la raíz del repo:

```bash
copy .env.example .env
```

En Linux/macOS usa `cp .env.example .env` en lugar de `copy`. `.env` está en `.gitignore`; `.env.example` sí se sube al repositorio.

### Frontend

| Variable | Obligatoria | Qué hace |
|---|---|---|
| `VITE_API_URL` | Sí | URL del backend, p. ej. `http://localhost:8000` |
| `VITE_REMOTE_CONVERSATIONS` | No (`false`) | `false`: conversaciones en `localStorage`. `true`: se guardan en el backend |
| `VITE_ENABLE_DOCUMENT_UPLOAD` | No (`false`) | Activa el botón de subida de PDF |
| `VITE_DEFAULT_ENGINE` | No | Motor preseleccionado (debe existir en `ENGINES`) |
| `VITE_DEFAULT_ENGINE_VERSION` | No | Versión preseleccionada (`V1.0`, `V1.1`, `V2.0`). Vacía: el usuario la elige |

### Backend

| Variable | Obligatoria | Por defecto | Qué hace |
|---|---|---|---|
| `GROQ_API_KEY` | **Sí** | — | Clave de Groq (secreto) |
| `API_HOST` | No | `127.0.0.1` | Interfaz en la que escucha `python main.py` |
| `API_PORT` | No | `8000` | Puerto del backend |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Orígenes del frontend permitidos (separados por comas) |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DB_NAME` | No | `thermodrive_rag.db` | BD vectorial (relativa a la raíz del repo, o absoluta) |
| `CONVERSATIONS_DB_NAME` | No | `conversations.db` | BD de conversaciones (solo con `VITE_REMOTE_CONVERSATIONS=true`) |
| `MANUALS_DIR` | No | `manual_htm240` | Carpeta de manuales a indexar (relativa a `backend/db/`, o absoluta) |
| `EMBEDDING_MODEL` | No | `paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings. **Mismo** al generar la BD y al responder |
| `LLM_MODEL` | No | `openai/gpt-oss-20b` | Modelo de Groq |
| `LLM_TEMPERATURE` | No | `0.1` | Temperatura del LLM |
| `RAG_TOP_K` | No | `5` | Fragmentos que se pasan al LLM |
| `RAG_DICTIONARY_TOP_K` / `RAG_DICTIONARY_MIN_SCORE` | No | `3` / `0.3` | Términos del glosario usados para reescribir la consulta |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | No | `800` / `200` | Tamaño y solape de fragmentos al indexar |
| `SOURCE_EXCERPT_CHARS` | No | `200` | Longitud del extracto mostrado en cada fuente |

Después de cambiar el `.env` hay que **reiniciar** `npm run dev` y el backend.

## Cómo encender el programa

Hacen falta **dos terminales**: una para el backend y otra para el frontend. La aplicación no tiene modo demostración: el chat siempre consulta al backend (y devolverá un error 501 hasta que el pipeline RAG esté implementado).

### 0. Preparación (una sola vez, desde la raíz del repo)

```bash
copy .env.example .env
```

Edita `.env` y pon tu `GROQ_API_KEY`.

### 1. Backend (API)

Desde la raíz del repo, instala las dependencias:

```bash
pip install -r requirements.txt
```

Si todavía no existe `thermodrive_rag.db`, genérala (una sola vez, o cuando cambien los manuales):

```bash
python backend/db/database_generator.py
```

Arranca el servidor (usa `API_HOST` y `API_PORT` del `.env`):

```bash
cd backend
python main.py
```

También puedes usar `uvicorn main:app --reload --port 8000` para recarga automática.

- Salud: `http://localhost:<API_PORT>/api/health`
- Docs automáticas de FastAPI: `http://localhost:<API_PORT>/docs`

### 2. Frontend (interfaz)

```bash
cd frontend
npm install
npm run dev
```

La app queda en **http://localhost:5173**. Abre el selector de motor (cabecera), elige la **versión** y haz tu consulta.

---

## Cómo viaja una consulta

```
Selector de versión + pregunta
  -> useChat.sendMessage()           (frontend/src/hooks/useChat.ts)
  -> chatController.send()           POST /api/chat  { message, engine_version, profile, history, ... }
  -> chat_controller.chat()          valida ChatRequest (mensaje no vacío, campos recortados)
  -> rag_pipeline.armar_respuesta()  (backend/services/rag_pipeline.py, por implementar)
  -> { message, sources[], documents_consulted }  -> Message + EvidencePanel
```

## Reparto del pipeline RAG

`backend/services/rag_pipeline.py` contiene una función por tarea, cada una con un comentario que explica qué debe hacer, qué recibe y qué devuelve. Mientras estén vacías, `POST /api/chat` responde **501**.

| Persona | Funciones |
|---|---|
| **A (integrador)** | `validar_consulta`, `armar_respuesta`, `pedir_aclaracion` |
| **B (prompts)** | `traducir_consulta`, `construir_prompt` |
| **C (búsqueda vectorial)** | `buscar_fragmentos`, `cargar_indice` |
| **D (LLM y salida)** | `generar_respuesta`, `construir_fuentes`, `respuesta_sin_evidencia` |

Dependencias: C y D pueden empezar ya; B necesita a C (glosario) y a D (LLM) para `traducir_consulta` y puede usar versiones falsas mientras tanto; A deja `armar_respuesta` para el final. El comportamiento esperado respecto a la versión del motor está en la sección 12 de [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

## Qué hacen los endpoints ahora mismo

| Método y ruta | Estado |
|---|---|
| `GET /api/health` | Implementado: comprueba que la BD vectorial existe y si hay clave de Groq |
| `POST /api/chat` | **501** hasta que el equipo complete `backend/services/rag_pipeline.py` |
| `GET/POST /api/conversations`, `GET/DELETE /api/conversations/{id}`, `PUT /api/conversations` | Implementado: persisten en SQLite (`CONVERSATIONS_DB_NAME`) |
| `GET /api/documents`, `POST /api/documents` | **501** (pendiente). La pantalla de Documentación lo indica |
| `GET /api/sources/{id}` | **501** (pendiente) |

> `armar_respuesta` recibe solo mensaje, versión y perfil. `history`, `system` y `vehicle` llegan al backend pero el pipeline todavía no los usa.
