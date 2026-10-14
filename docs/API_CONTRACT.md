# API Contract — ARSOFT AI Technical Vehicle Assistant

**Versión:** 1.0.0  
**Fuente de verdad** entre el frontend (React/TypeScript) y el backend (Python/FastAPI).

---

## 1. Endpoints

| Endpoint | Método | Obligatorio | Uso |
|----------|--------|-------------|-----|
| `/api/health` | GET | Sí | Comprobar conexión |
| `/api/chat` | POST | Sí (imprescindible) | Consulta RAG |
| `/api/documents` | GET | No | Listar documentación e indexación |
| `/api/documents` | POST | No (tras flag) | Subir PDF |
| `/api/sources/{id}` | GET | No | Fragmento o PDF/página de una fuente |
| `/api/conversations` | POST/GET | No | Solo si `VITE_REMOTE_CONVERSATIONS=true` |
| `/api/conversations/{id}` | GET/PATCH/DELETE | No | Solo si `VITE_REMOTE_CONVERSATIONS=true` |

> Si un endpoint opcional no existe o devuelve 404/501, la interfaz degrada con elegancia (estado informativo), sin romperse.

> La búsqueda de conversaciones se hace en el cliente sobre las conversaciones guardadas. **No existe** `/api/search` para conversaciones.

---

## 2. POST /api/chat

### Petición

```json
{
  "conversation_id": "uuid",
  "message": "Se enciende el testigo de temperatura y huele a quemado",
  "engine": "ThermoDrive HTM-240",
  "engine_version": "V2.0",
  "system": "CIR-01",
  "profile": "mechanic",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "vehicle": {
    "brand": "",
    "model": "",
    "year": null,
    "vin": ""
  }
}
```

- `engine` y `engine_version`: motor y versión seleccionados. Pueden ir vacíos.
- `system`: opcional (`CIR-01`, `CIR-02`, `CIR-03`) o ausente.
- `profile`: `"mechanic"` (lenguaje técnico) o `"user"` (lenguaje sencillo).
- `history`: últimos 6 mensajes (el backend es sin estado).
- `vehicle`: datos informativos opcionales.

### Respuesta

```json
{
  "message": {
    "id": "uuid",
    "role": "assistant",
    "content": "texto completo de la respuesta"
  },
  "evidence_status": "high | medium | insufficient",
  "needs_clarification": false,
  "confidence": 0.92,
  "documents_consulted": 3,
  "interpreted_query": {
    "original": "huele a quemado",
    "technical_terms": ["sobrecalentamiento", "..."]
  },
  "detected_dtc": [
    { "code": "P0217", "description": "..." }
  ],
  "sections": {
    "diagnosis": "",
    "possible_causes": [],
    "criticality": "low | medium | high | critical",
    "safety": [
      { "level": "warning | critical", "text": "" }
    ],
    "ppe": [],
    "checks": [],
    "decision_tree_id": "",
    "procedure": ""
  },
  "clarification": {
    "message": "",
    "missing_fields": [
      { "key": "engine_version", "label": "Versión del motor", "options": ["V1.0", "V1.1", "V2.0"] }
    ]
  },
  "sources": [
    {
      "id": "uuid",
      "document": "Manual técnico HTM-240",
      "source_type": "manual | dtc_catalog | decision_tree | historical_case | safety_manual | glossary",
      "section": "",
      "page": 0,
      "engine": "ThermoDrive HTM-240",
      "engine_version": "V2.0",
      "system": "CIR-01",
      "excerpt": "",
      "url": ""
    }
  ],
  "discarded_sources": [
    { "document": "", "reason": "obsolete_version | version_mismatch", "detail": "" }
  ]
}
```

### Reglas de robustez (OBLIGATORIAS)

- Solo `message.content` es obligatorio. Todo lo demás es opcional.
- Si no llega `sections`, se muestra `message.content` junto con las fuentes.
- Nunca inventar datos que el backend no envíe.
- `evidence_status`: `high` → «Evidencia: ALTA», `medium` → «Evidencia: MEDIA», `insufficient` → aviso destacado. Si no llega, no se muestra.
- `needs_clarification = true` → tarjeta de aclaración con `clarification.missing_fields`.
- `discarded_sources` → aviso desplegable.
- Errores de red: «No se ha podido conectar con el servidor». Errores HTTP: «No se ha podido procesar la consulta», con botón Reintentar.

---

## 3. GET /api/health

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## 4. GET /api/documents

```json
{
  "documents": [
    {
      "id": "uuid",
      "filename": "Manual técnico HTM-240 V2.0",
      "type": "manual | dtc_catalog | decision_tree | historical_case | safety_manual | glossary",
      "engine": "ThermoDrive HTM-240",
      "engine_version": "V2.0",
      "pages": 312,
      "uploaded_at": "2025-08-15T10:00:00Z",
      "status": "processed | pending | failed"
    }
  ]
}
```

---

## 5. POST /api/documents

Subida multipart de un PDF. Devuelve el documento creado con estado `pending`.

---

## 6. GET /api/sources/{id}

```json
{
  "excerpt": "Fragmento recuperado...",
  "url": "https://..."
}
```

---

## 7. Conversaciones (solo si VITE_REMOTE_CONVERSATIONS=true)

### Modelo

```json
{
  "id": "uuid",
  "title": "...",
  "created_at": "...",
  "updated_at": "...",
  "favorite": false,
  "engine": "ThermoDrive HTM-240",
  "engine_version": "V2.0",
  "system": null,
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

- `POST /api/conversations` — crear
- `GET /api/conversations` — listar
- `GET /api/conversations/{id}` — recuperar
- `PUT /api/conversations` — actualizar (body = conversación completa)
- `DELETE /api/conversations/{id}` — eliminar

---

## 8. Tipos TypeScript

Ver `src/types/chat.ts`, `src/types/conversation.ts`, `src/types/document.ts`, `src/types/contract.ts`, `src/types/engine.ts`, `src/types/source.ts`.

---

## 9. Modelos Pydantic equivalentes

Ver `backend-mock/models.py` para los modelos completos en Python.

---

## 10. CORS

El backend debe incluir `CORSMiddleware` permitiendo el origen del frontend en desarrollo (por defecto `http://localhost:5173`).

---

## 11. Dónde encajan RAG, LLM y base de datos

```
Usuario → Frontend → POST /api/chat → Backend (FastAPI)
                                        ├── SQLite + sqlite-vec: búsqueda vectorial de fragmentos
                                        ├── Recupera fragmentos relevantes (por motor/versión)
                                        ├── Construye contexto para el LLM
                                        ├── LLM (Groq): genera respuesta con evidencia
                                        └── Devuelve respuesta estructurada + fuentes
```

El frontend **no** implementa IA, embeddings ni búsqueda vectorial. Solo envía la consulta y renderiza la respuesta estructurada.

---

## 12. Cómo cambiar de mock a backend real

1. En `.env`, cambiar `VITE_USE_MOCK=false`
2. Asegurar que `VITE_API_URL` apunta al backend real
3. Reiniciar la aplicación
4. El endpoint que el equipo de backend debe implementar primero es `POST /api/chat`
