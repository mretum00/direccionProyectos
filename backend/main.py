"""
ARSOFT AI — Backend (FastAPI).
Los endpoints viven en controllers/. La lógica se añadirá después.

Ejecutar desde esta carpeta:
  pip install -r requirements.txt
  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from controllers import (
    chat_router,
    conversations_router,
    documents_router,
    health_router,
    sources_router,
)

app = FastAPI(title="ARSOFT AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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

    uvicorn.run(app, host="0.0.0.0", port=8000)
