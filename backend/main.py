"""
ARSOFT AI — Backend (FastAPI).
Los endpoints viven en controllers/ y la lógica RAG en services/.
Toda la configuración procede de variables de entorno (ver config.py y .env.example).

Ejecutar desde esta carpeta (respeta API_HOST / API_PORT del .env):
  pip install -r ../requirements.txt
  python main.py

Con recarga automática en desarrollo:
  uvicorn main:app --reload --port <API_PORT>
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import APP_VERSION, settings
from controllers import (
    chat_router,
    conversations_router,
    documents_router,
    health_router,
    sources_router,
)

logging.basicConfig(level=settings.log_level, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="ARSOFT AI Backend", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(sources_router)
app.include_router(conversations_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
