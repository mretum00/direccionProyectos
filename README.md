# ThermoDrive · Asistente técnico ARSOFT AI

Asistente técnico basado en RAG (Retrieval-Augmented Generation) sobre la documentación del sistema ficticio **HTM-240 / ThermoDrive**. El usuario hace preguntas en lenguaje natural; el backend busca los fragmentos relevantes de los manuales, los pasa a un LLM (Groq) y devuelve la respuesta junto con las fuentes consultadas.

> **Aviso de uso educativo:** HTM-240 es un sistema ficticio utilizado con fines educativos. Esta aplicación no sustituye a los manuales oficiales ni a la evaluación de un profesional. La interfaz muestra este aviso de forma permanente.

- **Frontend:** React + Vite (TypeScript)
- **Backend:** Python + FastAPI
- **RAG:** SQLite (`thermodrive_rag.db`) + embeddings multilingües + LLM de Groq
- **Persistencia de usuarios y chats:** SQLite (`thermodrive_app.db`)

---

## Índice

1. [Requisitos del sistema](#1-requisitos-del-sistema)
2. [Obtener el código](#2-obtener-el-código)
3. [Configuración de servicios externos (Groq)](#3-configuración-de-servicios-externos-groq)
4. [Variables de entorno](#4-variables-de-entorno)
5. [Instalación y ejecución paso a paso](#5-instalación-y-ejecución-paso-a-paso)
6. [Sistema RAG: generar y regenerar la base documental](#6-sistema-rag-generar-y-regenerar-la-base-documental)
7. [Uso de la aplicación](#7-uso-de-la-aplicación)
8. [Ejecución con Docker](#8-ejecución-con-docker)
9. [Actualizar la aplicación conservando los datos](#9-actualizar-la-aplicación-conservando-los-datos)
10. [Arquitectura y flujo de datos](#10-arquitectura-y-flujo-de-datos)
11. [API](#11-api)
12. [Pruebas automatizadas](#12-pruebas-automatizadas)
13. [Registro de auditoría de consultas](#13-registro-de-auditoría-de-consultas)
14. [Estructura del repositorio](#14-estructura-del-repositorio)
15. [Resolución de problemas frecuentes](#15-resolución-de-problemas-frecuentes)
16. [Seguridad](#16-seguridad)

---

## 1. Requisitos del sistema

### Software

| Componente | Versión mínima recomendada | Comprobar con |
|---|---|---|
| Python | 3.10 o superior | `python --version` (o `python3 --version`) |
| pip | Incluido con Python | `python -m pip --version` |
| Node.js | 18 o superior (recomendado 20 LTS) | `node --version` |
| npm | Incluido con Node.js | `npm --version` |
| Git | Cualquiera reciente | `git --version` |

> En Linux/macOS el comando suele ser `python3` en lugar de `python`. En Windows, si `python` no se reconoce, prueba `py`.

### Hardware y red

- **RAM:** 4 GB mínimo (8 GB recomendado; el modelo de embeddings se carga en memoria).
- **Disco:** unos 3 GB libres (dependencias de Python, `node_modules` y modelo de embeddings).
- **Internet:** necesario para instalar dependencias, **descargar el modelo de embeddings la primera vez** y llamar a la API de Groq en cada consulta.
- **Puertos libres:** `8000` (backend) y `5173` (frontend).

### Sistemas operativos

Windows 10/11, Linux y macOS. Los comandos se indican para ambos tipos de consola cuando difieren.

---

## 2. Obtener el código

```bash
git clone <URL_DEL_REPOSITORIO>
cd <carpeta_del_repositorio>
```

Todos los comandos de este documento se ejecutan desde la **raíz del repositorio** salvo que se indique lo contrario.

---

## 3. Configuración de servicios externos (Groq)

El backend usa la API de **Groq** para generar las respuestas. Sin clave, la aplicación arranca pero no puede responder.

1. Crea una cuenta gratuita en <https://console.groq.com>.
2. Entra en **API Keys** y pulsa **Create API Key**.
3. Copia la clave (empieza por `gsk_...`) y guárdala; solo se muestra una vez.
4. Pégala en tu archivo `.env` como `GROQ_API_KEY` (ver sección 4).

Notas:

- El plan gratuito tiene límites de peticiones y de tokens por minuto/día. Si se superan, las consultas fallan temporalmente (ver [Resolución de problemas](#15-resolución-de-problemas-frecuentes)).
- El modelo usado se configura con `LLM_MODEL` (por defecto `openai/gpt-oss-20b`).
- Una vez arrancado el backend, `GET /api/health` indica si la clave está configurada.

---

## 4. Variables de entorno

El archivo `.env` vive en la **raíz del repositorio** (no dentro de `frontend/` ni de `backend/`) y lo leen los dos lados:

- **Frontend (Vite):** `frontend/vite.config.ts` apunta a la carpeta padre con `envDir`. Solo las variables con prefijo `VITE_` llegan al navegador, por lo que **nunca pongas secretos con ese prefijo**. El código las lee únicamente en `frontend/src/config.ts`.
- **Backend (FastAPI):** `backend/config.py` carga `../.env` de forma explícita, sin depender del directorio desde el que se lance. Es el único módulo que lee variables de entorno.

Crea tu `.env` a partir de la plantilla:

```bash
# Windows (CMD o PowerShell)
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edita `.env` y como mínimo rellena:

```env
GROQ_API_KEY=tu_clave_de_groq
VITE_API_URL=http://localhost:8000
```

> **Importante:** nunca subas el `.env` ni tu clave a Git. Pon la clave solo en `.env`, nunca en `.env.example`. Tras cambiar el `.env`, **reinicia el backend y el frontend**.

### 4.1 Frontend

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `VITE_API_URL` | Sí | — | URL del backend, p. ej. `http://localhost:8000` |
| `VITE_ENABLE_DOCUMENT_UPLOAD` | No | `false` | Activa el botón de subida de PDF |
| `VITE_DEFAULT_ENGINE` | No | — | Motor preseleccionado (debe existir en `ENGINES`) |
| `VITE_DEFAULT_ENGINE_VERSION` | No | vacía | Versión preseleccionada (`V1.0`, `V1.1`, `V2.0`). Vacía: el usuario la elige |

### 4.2 Backend

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `GROQ_API_KEY` | Sí | — | Clave de Groq (secreto) |
| `API_HOST` | No | `127.0.0.1` | Interfaz en la que escucha `python main.py` |
| `API_PORT` | No | `8000` | Puerto del backend |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Orígenes del frontend permitidos (separados por comas) |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DB_NAME` | No | `thermodrive_rag.db` | BD vectorial (ruta relativa a la raíz del repo, o absoluta) |
| `MANUALS_DIR` | No | `manual_htm240` | Carpeta de manuales a indexar (relativa a `backend/db/`, o absoluta) |
| `EMBEDDING_MODEL` | No | `paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings. **Debe ser el mismo al generar la BD y al responder** |
| `LLM_MODEL` | No | `openai/gpt-oss-20b` | Modelo de Groq |
| `LLM_TEMPERATURE` | No | `0.1` | Temperatura del LLM |
| `RAG_TOP_K` | No | `5` | Fragmentos que se pasan al LLM |
| `RAG_DICTIONARY_TOP_K` | No | `3` | Términos del glosario usados para reescribir la consulta |
| `RAG_DICTIONARY_MIN_SCORE` | No | `0.3` | Puntuación mínima de los términos del glosario |
| `RAG_CHUNK_SIZE` | No | `800` | Tamaño de los fragmentos al indexar |
| `RAG_CHUNK_OVERLAP` | No | `200` | Solape entre fragmentos al indexar |
| `SOURCE_EXCERPT_CHARS` | No | `200` | Longitud del extracto mostrado en cada fuente |

---

## 5. Instalación y ejecución paso a paso

Hacen falta **dos terminales**: una para el backend y otra para el frontend.

### Paso 0. Configurar el `.env` (una sola vez)

Ver [sección 4](#4-variables-de-entorno).

### Paso 1. (Recomendado) Entorno virtual de Python

Desde la raíz del repositorio:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Paso 2. Backend (terminal 1)

Desde la raíz del repositorio:

```bash
python -m pip install -r requirements.txt
```

Si **no existe** `thermodrive_rag.db` en la raíz, genérala (una sola vez, o cuando cambien los manuales; ver [sección 6](#6-sistema-rag-generar-y-regenerar-la-base-documental)):

```bash
python backend/db/database_generator.py
```

Arranca el servidor:

```bash
cd backend
python main.py
```

Alternativa con recarga automática (desarrollo):

```bash
cd backend
uvicorn main:app --reload --port 8000
```

El backend queda en `http://localhost:8000`.

Comprobaciones:

- Salud: <http://localhost:8000/api/health> (indica si existe la BD vectorial y si hay clave de Groq).
- Documentación interactiva: <http://localhost:8000/docs>.

> La primera vez que se carga el modelo de embeddings se descarga de internet (puede tardar unos minutos). Las siguientes veces se usa la caché local.

### Paso 3. Frontend (terminal 2)

Abre una nueva consola y, desde la raíz del repositorio:

```bash
cd frontend
npm install
npm run dev
```

El frontend queda en <http://localhost:5173>.

### Paso 4. Comprobación final

1. <http://localhost:8000/api/health> responde correctamente.
2. <http://localhost:5173> carga la interfaz.
3. Puedes registrarte, iniciar sesión y recibir una respuesta a una pregunta (sección 7).

### Resumen de comandos (después de la primera instalación)

| Terminal | Comandos |
|---|---|
| 1 (backend) | `cd backend` → `python main.py` |
| 2 (frontend) | `cd frontend` → `npm run dev` |

---

## 6. Sistema RAG: generar y regenerar la base documental

El RAG usa dos bases de datos SQLite en la raíz del repositorio:

| Archivo | Contenido | Quién la crea | ¿Se borra? |
|---|---|---|---|
| `thermodrive_rag.db` | Fragmentos de los manuales con sus embeddings | `backend/db/database_generator.py` | **Sí: el generador la borra y la recrea cada vez** |
| `thermodrive_app.db` | Usuarios (con su sesión) e historial de chats | Se crea sola al arrancar el backend | **Nunca se borra** |

### Generar la base RAG

```bash
python backend/db/database_generator.py
```

El script lee los manuales de `MANUALS_DIR` (por defecto `manual_htm240`, relativa a `backend/db/`), los divide en fragmentos (`RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP`) y calcula sus embeddings con `EMBEDDING_MODEL`.

### Cuándo hay que regenerarla

- Si `thermodrive_rag.db` no existe.
- Si cambian, se añaden o se eliminan manuales.
- Si cambias `EMBEDDING_MODEL`, `RAG_CHUNK_SIZE` o `RAG_CHUNK_OVERLAP`.

Tras regenerarla, reinicia el backend. **Regenerar la base RAG no afecta a usuarios ni a chats**, que están en `thermodrive_app.db`.

### Cómo funciona una consulta

```
Pregunta del usuario + versión del motor + perfil
  → reescritura de la consulta con el glosario
  → búsqueda vectorial de los fragmentos más cercanos (RAG_TOP_K)
  → construcción del prompt con los fragmentos
  → generación con el LLM de Groq
  → respuesta + fuentes + documentos consultados
```

Si no hay evidencia suficiente en los manuales, el asistente lo indica en lugar de inventar la respuesta.

---

## 7. Uso de la aplicación

1. Abre <http://localhost:5173>.
2. **Primera vez:** pulsa **Regístrate** y crea tu usuario (la contraseña debe tener al menos 8 caracteres). Después inicia sesión.
3. En la cabecera, abre el **selector de motor**, elige la **versión** (`V1.0`, `V1.1` o `V2.0`) y, si procede, el **perfil**.
4. Escribe tu pregunta y envíala. Verás la respuesta y el **panel de evidencia** con las fuentes y los documentos consultados.
5. Gestión de conversaciones: **renombrar**, **marcar como favorita**, **duplicar** y **borrar**.
6. Puedes cancelar una pregunta en curso: no se guardará.
7. Tus conversaciones se guardan en el servidor y se cargan cada vez que inicias sesión, desde cualquier navegador.

### Autenticación y sesiones

- Al iniciar sesión, el backend devuelve un **token**; el frontend lo guarda y lo envía en cada petición (`Authorization: Bearer <token>`).
- En la BD solo se guarda su **hash** (`users.token_hash`).
- Cada usuario tiene **una sola sesión**, que **no caduca**: dura hasta que cierra sesión o entra desde otro navegador (lo que cierra la anterior).
- Si la sesión se cierra o se abre en otro sitio, el backend responde `401` y el frontend vuelve a la pantalla de login.

### Notas sobre el comportamiento de los chats

- El backend es la única fuente de verdad: `POST /api/chat` lee el historial de la BD, ejecuta el RAG y guarda pregunta y respuesta juntas. **Si el RAG falla, no se guarda nada.**
- Un chat nuevo no existe en el backend hasta que se envía su primera pregunta.
- Reenviar el mismo `message_id` devuelve la respuesta ya guardada sin duplicarla.

---

## 8. Ejecución con Docker

> **Estado: pendiente de implementar.** Esta sección describe lo previsto. Actualízala con los comandos reales cuando existan los archivos `Dockerfile` y `docker-compose.yml`.

### Archivos previstos

```
backend/Dockerfile        Imagen del backend (Python + FastAPI)
frontend/Dockerfile       Imagen del frontend (build de Vite + servidor estático)
docker-compose.yml        Orquestación de ambos servicios y volúmenes
```

### Requisitos

- Docker Desktop (Windows/macOS) o Docker Engine + Docker Compose v2 (Linux).
- El archivo `.env` creado como en la [sección 4](#4-variables-de-entorno).

### Comandos previstos

```bash
# Primera vez y tras cada actualización
docker compose up --build -d

# Ver registros
docker compose logs -f

# Parar (conserva los datos)
docker compose down
```

URLs esperadas: frontend en <http://localhost:5173> y backend en <http://localhost:8000>.

### Datos que deben persistir (volúmenes)

| Dato | Ruta | Motivo |
|---|---|---|
| `thermodrive_app.db` | raíz del proyecto | Usuarios y chats |
| `thermodrive_rag.db` | raíz del proyecto | Base RAG (evita regenerarla en cada arranque) |
| `backend/logs/` | `backend/logs/` | Registro de auditoría |
| Caché del modelo de embeddings | caché de Hugging Face | Evita descargarlo en cada build |

> `docker compose down -v` **elimina los volúmenes y, con ellos, los datos**. No lo uses salvo que quieras empezar de cero.

---

## 9. Actualizar la aplicación conservando los datos

Los datos del usuario están en `thermodrive_app.db` (y los registros en `backend/logs/`). El código se puede actualizar sin tocarlos.

### 9.1 Copia de seguridad (antes de actualizar)

Con el backend **parado**, copia el archivo:

```bash
# Windows
copy thermodrive_app.db thermodrive_app.db.bak

# Linux / macOS
cp thermodrive_app.db thermodrive_app.db.bak
```

### 9.2 Actualización (ejecución local)

```bash
# 1. Parar backend y frontend (Ctrl + C en cada terminal)

# 2. Descargar los cambios
git pull

# 3. Reinstalar dependencias
python -m pip install -r requirements.txt
cd frontend && npm install && cd ..

# 4. Comparar .env con .env.example por si hay variables nuevas

# 5. Regenerar la base RAG SOLO si cambiaron manuales o parámetros (sección 6)
python backend/db/database_generator.py

# 6. Arrancar de nuevo (sección 5)
```

### 9.3 Actualización (Docker, cuando esté implementado)

```bash
git pull
docker compose up --build -d
```

Los volúmenes mantienen los datos.

### 9.4 Restaurar una copia de seguridad

Con el backend parado, sustituye `thermodrive_app.db` por la copia (`thermodrive_app.db.bak`) y vuelve a arrancar.

### 9.5 Qué se conserva y qué se regenera

| Elemento | Al actualizar |
|---|---|
| `thermodrive_app.db` (usuarios y chats) | Se conserva |
| `thermodrive_rag.db` | Se regenera solo si ejecutas el generador |
| `.env` | Se conserva (no está en Git) |
| `backend/logs/` | Se conserva (no está en Git) |

---

## 10. Arquitectura y flujo de datos

Las capas van siempre en el mismo sentido, de la vista a la base de datos:

- **Frontend:** vistas (`pages/`, `components/`) → hooks (`useChat`, `useConversations`) y sesión (`auth.tsx`) → `services/api.ts`, el único sitio que llama al backend.
- **Backend:** `routers/` (endpoints HTTP) → `services/` (lógica: `auth.py`, `rag_pipeline.py`…) y `db/repositories/` (el único sitio con consultas a la BD) → `db/models.py`.

---

## 11. API

La documentación interactiva completa está en <http://localhost:8000/docs> y el contrato en `docs/API_CONTRACT.md`.

| Método | Ruta | Sesión | Qué hace |
|---|---|---|---|
| `GET` | `/api/health` | no | Comprueba que existe la BD vectorial y si hay clave de Groq |
| `POST` | `/api/auth/register` | no | Crea un usuario (`username`, `password` ≥ 8 caracteres) |
| `POST` | `/api/auth/login` | no | Devuelve `token` y `user` |
| `POST` | `/api/auth/logout` | sí | Invalida el token |
| `GET` | `/api/auth/me` | sí | Usuario de la sesión actual |
| `POST` | `/api/chat` | sí | Pregunta al asistente y la guarda (`conversation_id`, `message_id`, `message`, `engine_version`, `profile`) |
| `POST` | `/api/chat/{message_id}/cancel` | sí | Cancela la pregunta; si ya estaba guardada, se borra con su respuesta |
| `GET` | `/api/conversations` | sí | Chats del usuario con sus mensajes |
| `PATCH` | `/api/conversations/{id}` | sí | Renombrar (`title`) o marcar favorita (`favorite`) |
| `POST` | `/api/conversations/{id}/duplicate` | sí | Duplica el chat |
| `DELETE` | `/api/conversations/{id}` | sí | Borra el chat y sus mensajes |
| `GET` | `/api/versions`, `/api/documents` | no | Versiones del motor y documentación indexada |

---

## 12. Pruebas automatizadas

Instala las dependencias de desarrollo desde la raíz:

```bash
python -m pip install -r requirements-dev.txt
```

Pruebas unitarias (las de integración se excluyen por defecto):

```bash
python -m pytest -v
```

Pruebas de integración (consultan la base documental y cargan el modelo de embeddings; pueden necesitar una primera descarga del modelo):

```bash
python -m pytest -o addopts= -m integration -v
```

---

## 13. Registro de auditoría de consultas

El backend añade una línea JSONL por cada intento procesado en `backend/logs/consultas.jsonl`. Cada línea incluye un `attempt_id` único, la relación con usuario, conversación y mensaje (cuando está disponible), versión, perfil, estado, evidencia, documentos y duración. Los reintentos de una misma pregunta pueden compartir `message_id`, pero cada ejecución tiene un `attempt_id` distinto.

El historial completo de preguntas y respuestas permanece en `thermodrive_app.db`; el JSONL es un registro de auditoría complementario.

Los archivos de `backend/logs/` están excluidos de Git porque pueden contener texto introducido por usuarios e identificadores. **No subas registros reales al repositorio.**

---

## 14. Estructura del repositorio

```
.env.example                  Plantilla de variables de entorno (se versiona)
.env                          Variables reales (NO se versiona)
requirements.txt              Dependencias de Python del backend
requirements-dev.txt          Dependencias de desarrollo y pruebas
thermodrive_rag.db            BD vectorial (la genera backend/db/database_generator.py)
thermodrive_app.db            Usuarios y chats (se crea sola; no se versiona)
frontend/                     Interfaz React + Vite
  src/config.ts               Única lectura de variables VITE_*
  src/pages/, components/     Vistas
  src/hooks/                  useChat, useConversations
  src/auth.tsx                Sesión
  src/services/api.ts         Único punto de llamada al backend
backend/                      API FastAPI
  config.py                   Única lectura de variables de entorno
  main.py                     Arranque, CORS y registro de rutas
  routers/                    Endpoints HTTP
  services/                   Lógica (auth.py, rag_pipeline.py…)
  db/                         Generador de la BD vectorial, modelos y repositorios
  logs/                       Registro de auditoría (no se versiona)
docs/                         API_CONTRACT.md
```

---

## 15. Resolución de problemas frecuentes

| Problema | Causa probable | Solución |
|---|---|---|
| `python` no se reconoce | Python no instalado o no está en el PATH | Instala Python 3.10+ y marca «Add to PATH». Prueba `python3` o `py` |
| `pip install` falla | Versión antigua de Python o falta de entorno virtual | Usa Python 3.10+, crea el entorno virtual (paso 1) y ejecuta `python -m pip install --upgrade pip` |
| `npm install` falla | Node demasiado antiguo o sin conexión | Actualiza a Node 18+/20 LTS; borra `frontend/node_modules` y reintenta |
| El backend no arranca: falta `thermodrive_rag.db` | La BD RAG no se ha generado | `python backend/db/database_generator.py` |
| Error por falta de `GROQ_API_KEY` | `.env` sin clave, mal ubicado o backend sin reiniciar | Comprueba que `.env` está en la **raíz**, que la clave es correcta, y reinicia el backend. Revisa `/api/health` |
| Error 401/403 de Groq | Clave inválida, revocada o mal copiada (espacios o comillas) | Genera otra clave en console.groq.com y reemplázala |
| Error 429 o respuestas que fallan a ratos | Límite de uso del plan gratuito de Groq | Espera unos minutos o reduce el ritmo de preguntas |
| `Address already in use` / puerto ocupado | Otro proceso usa el 8000 o el 5173 | Cierra el proceso o cambia `API_PORT` (y `VITE_API_URL` y `CORS_ORIGINS` en consecuencia) |
| El frontend dice que no puede conectar | `VITE_API_URL` incorrecta o servicios sin reiniciar | Revisa `VITE_API_URL`, comprueba que el backend responde en `/api/health` y reinicia `npm run dev` |
| Error de CORS en la consola del navegador | `CORS_ORIGINS` no incluye el origen del frontend | Añade el origen (p. ej. `http://localhost:5173`) y reinicia el backend |
| Te devuelve siempre al login | Sesión cerrada o abierta en otro navegador (401) | Inicia sesión de nuevo; solo hay una sesión activa por usuario |
| La primera consulta tarda mucho | Descarga del modelo de embeddings | Es normal la primera vez; necesita internet. Las siguientes son más rápidas |
| La descarga del modelo falla | Sin internet, proxy o firewall | Comprueba la conexión y reintenta; en redes restringidas, permite el acceso a huggingface.co |
| Los cambios del `.env` no se aplican | Servicios no reiniciados | Reinicia backend y frontend |
| Respuestas distintas o sin resultados tras cambiar de modelo de embeddings | La BD se generó con otro modelo | Regenera la BD RAG con el mismo `EMBEDDING_MODEL` |
| `copy` o `cp` no funciona | Comando de otro sistema operativo | Windows: `copy`; Linux/macOS: `cp` |
| `python -m pytest` no encuentra pytest | Faltan dependencias de desarrollo | `python -m pip install -r requirements-dev.txt` |

Si el problema persiste, ejecuta el backend con `LOG_LEVEL=DEBUG` en el `.env` y revisa la salida de la terminal.

---

## 16. Seguridad

- Nunca subas `.env`, claves ni `thermodrive_app.db` a Git.
- No pongas secretos en variables con prefijo `VITE_`: llegan al navegador.
- No subas registros reales de `backend/logs/`.
- La clave de Groq va solo en `.env`, nunca en `.env.example`.