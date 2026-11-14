# API Contract — ARSOFT AI Technical Vehicle Assistant

**Versión:** 1.0.0  
**Fuente de verdad** entre el frontend (React/TypeScript) y el backend (Python/FastAPI).

---

## 1. Endpoints

| Endpoint | Método | Obligatorio | Uso |
|----------|--------|-------------|-----|
| `/api/chat` | POST | Sí (imprescindible) | Consulta RAG |
| `/api/versions` | GET | Sí | Versiones del sistema que admite el backend (las ofrece el selector) |
| `/api/documents` | GET | No | Listar documentación e indexación |
| `/api/documents` | POST | No (tras flag) | Subir PDF |
| `/api/conversations` | GET/PUT | No | Solo si `VITE_REMOTE_CONVERSATIONS=true` |
| `/api/conversations/{id}` | DELETE | No | Solo si `VITE_REMOTE_CONVERSATIONS=true` |

> Si un endpoint opcional no existe o devuelve 404/501, la interfaz degrada con elegancia (estado informativo), sin romperse.

> La búsqueda de conversaciones se hace en el cliente sobre las conversaciones guardadas. **No existe** `/api/search` para conversaciones.

---

## 2. POST /api/chat

### Petición

```json
{
  "message": "Se enciende el testigo de temperatura y huele a quemado",
  "engine_version": "V2.0",
  "profile": "mechanic",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

- `engine_version`: versión del motor seleccionada. Es obligatoria: el frontend no envía la consulta sin ella y, si llega vacía o desconocida, el backend responde con `needs_clarification = true`.
- `profile`: **obligatorio**. `"mechanic"` (lenguaje técnico) o `"user"` (lenguaje sencillo). Si falta o no es válido, el backend responde 422. El frontend no lo preselecciona: el usuario debe elegirlo.
- `history`: últimos 6 mensajes, solo `role` (`"user"` o `"assistant"`) y `content` (el backend es sin estado). Los avisos locales de «falta versión o tipo de usuario» no se incluyen.

### Respuesta

```json
{
  "message": {
    "id": "uuid",
    "content": "texto completo de la respuesta"
  },
  "evidence_status": "high | medium | insufficient",
  "needs_clarification": false,
  "documents_consulted": 3,
  "sources": [
    {
      "id": "uuid",
      "document": "Manual técnico HTM-240",
      "source_type": "manual | dtc_catalog | decision_tree | historical_case | safety_manual | glossary",
      "section": "",
      "page": 0,
      "engine_version": "V2.0",
      "excerpt": ""
    }
  ]
}
```

### Reglas de robustez (OBLIGATORIAS)

- Solo `message.content` es obligatorio. Todo lo demás es opcional.
- Se muestra `message.content` junto con las fuentes (`sources`), si las hay.
- Nunca inventar datos que el backend no envíe.
- `evidence_status`: `high` → «Evidencia: ALTA», `medium` → «Evidencia: MEDIA», `insufficient` → aviso destacado. Si no llega, no se muestra.
- `needs_clarification = true` → aviso destacado con un botón que abre el selector de motor (el usuario debe elegir versión y perfil). El frontend no envía la consulta mientras falte alguno de los dos: abre el selector explicando qué falta, deja la pregunta en espera y la envía sola al completar la configuración (si se cierra el selector sin configurar, se descarta); el backend solo responde así si recibe una versión que no reconoce.
- Al guardar un mensaje del asistente, la respuesta se guarda **sin** `message` (el texto ya va en el `content` del mensaje) para no duplicarlo.
- Errores de red: «No se ha podido conectar con el servidor». Errores HTTP: «No se ha podido procesar la consulta», con botón Reintentar.

---

## 2b. GET /api/versions

```json
{ "versions": ["V1.0", "V1.1", "V2.0"] }
```

Es la **única** lista de versiones: está en `backend/config.py` (`ENGINE_VERSIONS`) y la usan el generador de la BD, el pipeline RAG y este endpoint. El frontend la pide al arrancar y no tiene copia propia. El sistema es uno solo (ThermoDrive HTM-240), por eso no hay campo `engine` en ninguna petición ni modelo.

---

## 3. GET /api/documents

```json
{
  "documents": [
    {
      "id": "uuid",
      "filename": "Manual técnico HTM-240 V2.0",
      "type": "manual | dtc_catalog | decision_tree | historical_case | safety_manual | glossary",
      "engine_version": "V2.0",
      "pages": 312,
      "uploaded_at": "2025-08-15T10:00:00Z",
      "status": "processed | pending | failed"
    }
  ]
}
```

---

## 4. POST /api/documents

Subida multipart de un PDF. Devuelve el documento creado con estado `pending`.

---

## 5. Conversaciones (solo si VITE_REMOTE_CONVERSATIONS=true)

### Modelo

```json
{
  "id": "uuid",
  "title": "...",
  "created_at": "...",
  "updated_at": "...",
  "favorite": false,
  "engine_version": "V2.0",
  "profile": "mechanic",
  "messages": [
    {
      "id": "",
      "role": "user|assistant",
      "content": "",
      "created_at": "",
      "response": {}
    }
  ]
}
```

- `profile` es `"mechanic"`, `"user"` o `""` (solo en una conversación vacía, creada antes de elegir el tipo de usuario).
- `GET /api/conversations` — listar. Respuesta: `{ "conversations": [...] }`
- `PUT /api/conversations` — crear o reemplazar (body = conversación completa). Responde `204 No Content`.
- `DELETE /api/conversations/{id}` — eliminar. Responde `204 No Content` (404 si no existe).

---

## 6. Tipos TypeScript

Ver `frontend/src/types/chat.ts`, `frontend/src/types/conversation.ts`, `frontend/src/types/document.ts` y `frontend/src/types/engine.ts`. Las llamadas al backend están en `frontend/src/services/api.ts`.

---

## 7. Modelos Pydantic equivalentes

Ver `backend/models/schemas.py` para los modelos completos en Python. Los endpoints están en `backend/routers/`.

---

## 8. CORS

El backend debe incluir `CORSMiddleware` permitiendo el origen del frontend en desarrollo (por defecto `http://localhost:5173`).

---

## 9. Dónde encajan RAG, LLM y base de datos

```
Usuario → Frontend → POST /api/chat → Backend (FastAPI)
                                        ├── SQLite + numpy: búsqueda vectorial (similitud coseno) de fragmentos
                                        ├── Recupera fragmentos relevantes (por motor/versión)
                                        ├── Construye contexto para el LLM
                                        ├── LLM (Groq): genera respuesta con evidencia
                                        └── Devuelve respuesta estructurada + fuentes
```

El frontend **no** implementa IA, embeddings ni búsqueda vectorial. Solo envía la consulta y renderiza la respuesta estructurada.

---

## 10. Configuración

La aplicación no tiene modo mock: el frontend siempre habla con el backend.

1. Copiar `.env.example` a `.env` en la raíz del repositorio.
2. Definir `VITE_API_URL` (frontend) y `GROQ_API_KEY` (backend). La lista completa de variables está en el `README.md`.
3. Arrancar el backend y después el frontend.

### Comportamiento esperado de `/api/chat` respecto a la versión

Especificación que debe cumplir `backend/services/rag_pipeline.py`:

- `engine_version` se compara (sin distinguir mayúsculas ni espacios) con las versiones presentes en la base de datos.
- Solo se recuperan fragmentos cuyo `applicable_versions` incluye esa versión.
- Si `engine_version` está vacía o no existe, la respuesta lleva `needs_clarification: true` y un mensaje que pide elegir la versión; no se consulta al LLM.
- Si la versión existe pero no hay fragmentos aplicables, se devuelve `evidence_status: "insufficient"` y `sources: []`.
- Los campos opcionales sin valor se omiten de la respuesta (no se envían como `null`).
