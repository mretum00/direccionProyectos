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

Entra en **http://localhost:5173** y disfruta. 🚀

### Autenticación y sesiones

Esta versión del prototipo permite acceder al asistente sin iniciar sesión. Las pantallas de inicio de sesión y registro son solo interfaces: no están conectadas a un sistema de autenticación.

El servidor no crea sesiones de usuario, por lo que la caducidad no aplica a esta versión. Si se incorpora autenticación, el servidor deberá rechazar las sesiones caducadas.

---

## Notas

- Si `thermodrive_rag.db` no existe, genérala antes de arrancar el backend:

  ```bash
  python backend/db/database_generator.py
  ```
- Si cambias el `.env`, reinicia el backend y el frontend.
