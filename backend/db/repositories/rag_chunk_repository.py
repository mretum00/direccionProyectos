"""Repositorio de la tabla `rag_documents` (fragmentos de los manuales)."""

from typing import Iterable

from config import settings
from db.models import RagChunk, rag_db

# SQLite limita las variables por consulta: los fragmentos se insertan en lotes.
TAMANO_LOTE = 100


class RagChunkRepository:
    def recreate(self) -> None:
        """Deja la BD vacía: borra el archivo si existe y crea la tabla desde cero."""
        self.delete_database()

        with rag_db.connection_context():
            rag_db.create_tables([RagChunk])

    def delete_database(self) -> None:
        """Borra el archivo de la BD (lanza PermissionError si otro proceso lo tiene abierto)."""
        rag_db.close()

        if settings.db_path.exists():
            settings.db_path.unlink()

    def add_many(self, chunks: Iterable[RagChunk]) -> None:
        """Inserta los fragmentos en una sola transacción: o entran todos o ninguno."""
        with rag_db.connection_context(), rag_db.atomic():
            RagChunk.bulk_create(list(chunks), batch_size=TAMANO_LOTE)

    def list_all(self) -> list[RagChunk]:
        """Todos los fragmentos, con su embedding."""
        with rag_db.connection_context():
            return list(RagChunk.select())

    def list_summaries(self) -> list[tuple[str, str | None, int | None]]:
        """(chunk_id, applicable_versions, page) de todos los fragmentos, sin el texto ni el embedding."""
        with rag_db.connection_context():
            query = RagChunk.select(RagChunk.chunk_id, RagChunk.applicable_versions, RagChunk.page)
            return [(c.chunk_id, c.applicable_versions, c.page) for c in query]

    def count(self) -> int:
        with rag_db.connection_context():
            return RagChunk.select().count()
