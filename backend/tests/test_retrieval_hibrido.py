"""Prueba de integración unitaria del modo híbrido en buscar_fragmentos."""
from types import SimpleNamespace

import numpy as np
import pytest

from services import retrieval


def test_retrieval_hibrido_conserva_prioridad_absoluta_del_dtc_exacto(monkeypatch):
    fragmentos = [
        {
            "chunk_id": "manual_general.pdf_1",
            "texto": "HTM-0142 código DTC catálogo diagnóstico del sistema",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.asarray([1.0, 0.0], dtype=np.float32),
            "pagina": 1,
            "seccion": "Diagnóstico general",
        },
        {
            "chunk_id": "catalogo_DTC.pdf_2",
            "texto": "Estrategia y comprobación del fallo de la bomba",
            "categoria": "DTC",
            "versiones": ["V2.0"],
            "vector": np.asarray([0.4, 0.9165], dtype=np.float32),
            "pagina": 2,
            "seccion": "HTM-0142",
        },
    ]
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: fragmentos)
    monkeypatch.setattr(
        retrieval,
        "embedding_normalizado",
        lambda _consulta: np.asarray([1.0, 0.0], dtype=np.float32),
    )
    monkeypatch.setattr(
        retrieval,
        "settings",
        SimpleNamespace(
            rag_code_match_bonus=0.15,
            rag_hybrid_retrieval_enabled=True,
            rag_rrf_k=60,
        ),
    )

    resultados = retrieval.buscar_fragmentos(
        "HTM-0142 código DTC catálogo", "V2.0", 5
    )

    assert resultados[0]["categoria"] == "DTC"
    assert resultados[0]["seccion"] == "HTM-0142"
    assert resultados[0]["score"] == pytest.approx(0.4)
    assert all("rrf_score" in resultado for resultado in resultados)
