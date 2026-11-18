"""
ARSOFT AI — Backend (FastAPI).
Los endpoints viven en routers/ (un archivo por tema), la lógica en services/ y el acceso
a las bases de datos en db/repositories/.
Toda la configuración procede de variables de entorno (ver config.py y .env.example).

Ejecutar desde esta carpeta (respeta API_HOST / API_PORT del .env):
  pip install -r ../requirements.txt
  python main.py

Con recarga automática en desarrollo:
  uvicorn main:app --reload --port <API_PORT>
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.models import init_app_db
from routers import auth, chat, conversations, documents, versions

logging.basicConfig(level=settings.log_level, format="%(asctime)s - %(levelname)s - %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Usuarios, sesiones y chats: crea las tablas la primera vez (no borra nada).
    init_app_db()
    yield


app = FastAPI(title="ARSOFT AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(versions.router)
app.include_router(documents.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
