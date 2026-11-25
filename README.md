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

El backend queda en http://localhost:8000. Compruébalo en http://localhost:8000/docs.

## 2. Frontend (terminal 2)

Abre una **nueva consola** y, desde la raíz del proyecto:

```bash
cd frontend
npm install
npm run dev
```

## 3. Usar la aplicación

Entra en **http://localhost:5173**. La primera vez, pulsa **Regístrate** para crear tu usuario y después inicia sesión. Tus conversaciones se guardan en el servidor y se cargan cada vez que entras con tu usuario, desde cualquier navegador.

---

## Notas

- Si `thermodrive_rag.db` no existe, genérala antes de arrancar el backend:

  ```bash
  python backend/db/database_generator.py
  ```
- Si cambias el `.env`, reinicia el backend y el frontend.
- Hay **dos bases de datos SQLite** en la raíz del proyecto:
  - `thermodrive_rag.db`: fragmentos de los manuales para el RAG. La crea (y la borra antes de volver a crearla) `database_generator.py`.
  - `thermodrive_app.db`: usuarios (con su sesión) y el historial de chats. Se crea sola al arrancar el backend, no se borra nunca y **no se sube a Git**.

## Arquitectura y flujo de datos

Las capas van siempre en el mismo sentido (de la vista a la base de datos):

- **Frontend**: vistas (`pages/`, `components/`) → hooks (`useChat`, `useConversations`) y sesión (`auth.tsx`) → `services/api.ts`, el único sitio que llama al backend.
- **Backend**: `routers/` (endpoints HTTP) → `services/` (lógica: `auth.py`, `rag_pipeline.py`...) y `db/repositories/` (el único sitio con consultas a la BD) → `db/models.py`.

- Al iniciar sesión el backend devuelve un **token**; el frontend lo guarda y lo envía en cada petición (`Authorization: Bearer <token>`). En la BD solo se guarda su hash, en la fila del usuario (`users.token_hash`): **cada usuario tiene una sola sesión**, que no caduca: dura hasta cerrar sesión o entrar desde otro navegador, que cierra la anterior. Si se cierra o se abre en otro sitio, el backend responde 401 y el frontend vuelve al login.
- El backend es la **única fuente de verdad** de los chats: `POST /api/chat` lee el historial de la conversación de la BD, ejecuta el RAG y guarda la pregunta y la respuesta juntas (si el RAG falla no se guarda nada). Devuelve la conversación ya guardada.
- Un chat nuevo no existe en el backend hasta que se envía su primera pregunta.

| Método | Ruta | Sesión | Qué hace |
|---|---|---|---|
| POST | `/api/auth/register` | no | Crea un usuario (`username`, `password` ≥ 8 caracteres) |
| POST | `/api/auth/login` | no | Devuelve `token` y `user` |
| POST | `/api/auth/logout` | sí | Invalida el token |
| GET | `/api/auth/me` | sí | Usuario de la sesión actual |
| POST | `/api/chat` | sí | Pregunta al asistente y la guarda (`conversation_id`, `message_id`, `message`, `engine_version`, `profile`). Reenviar el mismo `message_id` devuelve la respuesta ya guardada sin duplicarla |
| POST | `/api/chat/{message_id}/cancel` | sí | Cancela la pregunta: no se guarda aunque el RAG termine (y si ya estaba guardada, se borra con su respuesta) |
| GET | `/api/conversations` | sí | Chats del usuario con sus mensajes |
| PATCH | `/api/conversations/{id}` | sí | Renombrar (`title`) o marcar como favorita (`favorite`) |
| POST | `/api/conversations/{id}/duplicate` | sí | Duplica el chat |
| DELETE | `/api/conversations/{id}` | sí | Borra el chat y sus mensajes |
| GET | `/api/versions`, `/api/documents` | no | Versiones del motor y documentación indexada |

La documentación interactiva de todos los endpoints está en http://localhost:8000/docs.


## Pruebas automatizadas del backend

Instala las dependencias de desarrollo desde la raíz del repositorio:

```bash
python -m pip install -r requirements-dev.txt
```

Ejecuta las pruebas unitarias (las pruebas de integración se excluyen por defecto):

```bash
python -m pytest -v
```

Ejecuta aparte las pruebas que consultan la base documental y cargan el modelo de embeddings:

```bash
python -m pytest -o addopts= -m integration -v
```

Las pruebas de integración pueden necesitar una primera descarga del modelo de embeddings.

## Registro de auditoría de consultas

El backend añade una línea JSONL por cada intento procesado en `backend/logs/consultas.jsonl`.
Cada línea incluye un `attempt_id` único, la relación con usuario/conversación/mensaje cuando está
disponible, versión, perfil, estado, evidencia, documentos y duración. Los reintentos de una misma
pregunta pueden compartir `message_id`, pero cada ejecución tiene un `attempt_id` diferente.

El historial completo de preguntas y respuestas permanece en `thermodrive_app.db`; el JSONL es un
registro de auditoría complementario. Los archivos de `backend/logs/` están excluidos de Git porque
pueden contener texto introducido por usuarios e identificadores. No subas registros reales al repositorio.

## Aviso de uso educativo

La interfaz muestra un aviso permanente de que HTM-240 es un sistema ficticio utilizado con fines
educativos. La aplicación no sustituye los manuales oficiales ni la evaluación de un profesional.
