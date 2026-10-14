# direccionProyectos

Asistente técnico ARSOFT AI (ThermoDrive). El repositorio está separado en frontend (React/Vite) y backend (Python/FastAPI).

- Grupo 2: primero subir vuestro código a la rama de backend. Antes de subirlo a la rama principal.
- Grupo 3: primero subir vuestro código a la rama de frontend. Antes de subirlo a la rama principal.

El contrato entre ambos lados está en [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

## Estructura

```
frontend/                 Interfaz React + Vite
  src/controllers/        Capa de llamadas HTTP al backend (aún no usada por la UI)
  src/services/           Aquí corre la app hoy (mock o realApi)
backend/                  API FastAPI
  main.py                 Arranque, CORS y registro de rutas
  controllers/            Endpoints HTTP
  models/schemas.py       Modelos Pydantic del contrato
  db/                     Script de generación de la BD
docs/                     Contrato API
```

## Cómo encender el programa

Hacen falta **dos terminales**: una para el frontend y otra para el backend. Para ver la interfaz **no es obligatorio** el backend: por defecto el front usa datos mock.

Requisitos: Node.js (npm) y Python 3.

### 1. Frontend (interfaz)

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

En Linux/macOS usa `cp .env.example .env` en lugar de `copy`.

La app queda en **http://localhost:5173**.

Variables de `.env` (copiadas de `.env.example`):

| Variable | Valor por defecto | Qué hace |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL del backend |
| `VITE_USE_MOCK` | `true` | `true`: chat y documentos simulados en el cliente. `false`: llama a `realApi` (fetch al backend) |
| `VITE_REMOTE_CONVERSATIONS` | `false` | `false`: conversaciones en `localStorage`. `true`: las pediría al backend |
| `VITE_ENABLE_DOCUMENT_UPLOAD` | `false` | Activa la subida de PDF |

Con `VITE_USE_MOCK=true` (el valor actual) **la UI no usa ni los controladores del front ni el backend**. El chat funciona con `src/services/mockApi.ts`.

### 2. Backend (API)

En otra terminal:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

El API queda en **http://localhost:8000**.

- Salud: http://localhost:8000/api/health
- Docs automáticas de FastAPI: http://localhost:8000/docs

CORS permite el origen del Vite (`http://localhost:5173`).

### Encender frontend y backend juntos

1. Arranca el backend (paso 2).
2. Arranca el frontend (paso 1).
3. Abre http://localhost:5173.

Si quieres que la UI hable con FastAPI en lugar del mock:

1. En `frontend/.env` pon `VITE_USE_MOCK=false`.
2. Reinicia `npm run dev`.

Eso usa `frontend/src/services/realApi.ts`, **no** `frontend/src/controllers`. Los controladores del front todavía no están conectados a la UI. Además, casi todos los endpoints del back responden 501 (no implementado), así que el chat real aún no funciona.

---

## Qué hacen los controladores ahora mismo

Hay dos capas con el mismo contrato. **Ninguna implementa RAG, LLM ni base de datos.**

### Backend (`backend/controllers/`)

`backend/main.py` registra estas rutas. Reciben la petición HTTP y, salvo health, no hacen nada más.

| Archivo | Método y ruta | Qué hace ahora |
|---|---|---|
| `health_controller.py` | `GET /api/health` | Devuelve `{ "status": "ok", "version": "1.0.0" }`. No comprueba BD ni servicios. |
| `chat_controller.py` | `POST /api/chat` | Acepta el body (`ChatRequest`) y responde **501 Not implemented yet**. No busca fragmentos ni llama al LLM. |
| `documents_controller.py` | `GET /api/documents` | **501**. No lista documentos. |
| `documents_controller.py` | `POST /api/documents` | Recibe el archivo y responde **501**. No guarda ni indexa. |
| `sources_controller.py` | `GET /api/sources/{id}` | **501**. No devuelve el fragmento. |
| `conversations_controller.py` | `GET/POST /api/conversations`, `GET/DELETE /api/conversations/{id}`, `PUT /api/conversations` | **501**. No persisten conversaciones. |

### Frontend (`frontend/src/controllers/`)

Son esqueletos TypeScript. **La UI no los importa.** El chat sigue yendo a `src/services/api.ts` → mock o `realApi`.

| Archivo | Métodos | Qué hacen ahora |
|---|---|---|
| `httpClient.ts` | `request()` | Cliente `fetch` hacia `VITE_API_URL`. Listo para usarse; los demás controladores **aún no lo llaman**. |
| `healthController.ts` | `check()` | Lanza error: `no implementado`. |
| `chatController.ts` | `send()` | Lanza error. No hace `POST /api/chat`. |
| `documentsController.ts` | `list()`, `upload()` | Lanzan error. |
| `sourcesController.ts` | `get()` | Lanza error. |
| `conversationsController.ts` | `list()`, `get()`, `create()`, `update()`, `remove()` | Lanzan error. |

Cuando se implementen, el flujo previsto es:

```
UI → frontend/src/controllers → HTTP /api/... → backend/controllers → (luego) BD / RAG / LLM
```
