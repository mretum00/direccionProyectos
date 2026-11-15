"""Repositorios: un acceso por tabla, para no repartir consultas por el resto del backend."""

from db.repositories.rag_chunk_repository import RagChunkRepository

__all__ = ["RagChunkRepository"]
