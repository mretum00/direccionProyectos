from types import SimpleNamespace

import numpy as np

from services import retrieval


def test_retrieval_aplica_anclaje_antes_del_limite_por_documento(monkeypatch):
    fragmentos = [
        {
            "chunk_id": "PRC005.pdf_1",
            "texto": "Comprobar electroventilador CMP-09.",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.array([1.0, 0.0], dtype=np.float32),
            "pagina": 1,
            "seccion": "Objetivo",
        },
        {
            "chunk_id": "PRC005.pdf_2",
            "texto": "Conectar HTM-SCAN y probar los niveles PWM.",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.array([0.4, 0.9165], dtype=np.float32),
            "pagina": 2,
            "seccion": "Pasos",
        },
        {
            "chunk_id": "PRC005.pdf_3",
            "texto": "La velocidad debe ser proporcional a la consigna.",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.array([0.3, 0.9539], dtype=np.float32),
            "pagina": 2,
            "seccion": "Valores esperados",
        },
        {
            "chunk_id": "OTRO.pdf_1",
            "texto": "Información general no relacionada.",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.array([0.95, 0.3122], dtype=np.float32),
            "pagina": 1,
            "seccion": "Introducción",
        },
    ]
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: fragmentos)
    monkeypatch.setattr(
        retrieval,
        "embedding_normalizado",
        lambda _: np.array([1.0, 0.0], dtype=np.float32),
    )
    monkeypatch.setattr(
        retrieval,
        "settings",
        SimpleNamespace(
            rag_code_match_bonus=0.15,
            rag_hybrid_retrieval_enabled=False,
            rag_rrf_k=60,
            rag_component_anchor_enabled=True,
        ),
    )

    resultados = retrieval.buscar_fragmentos(
        "¿Cómo se comprueba el funcionamiento del electroventilador CMP-09?",
        "V2.0",
        3,
    )

    assert resultados[0]["seccion"] == "Pasos"
    assert resultados[1]["seccion"] == "Valores esperados"
    assert len(resultados) == 3
    assert all("score" in resultado for resultado in resultados)


def test_retrieval_anclaje_deshabilitado_conserva_ranking_base(monkeypatch):
    fragmentos = [
        {
            "chunk_id": "PRC005.pdf_1",
            "texto": "Comprobar electroventilador CMP-09.",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.array([1.0, 0.0], dtype=np.float32),
            "pagina": 1,
            "seccion": "Objetivo",
        },
        {
            "chunk_id": "PRC005.pdf_2",
            "texto": "Conectar HTM-SCAN y probar niveles PWM.",
            "categoria": "Manual",
            "versiones": ["V2.0"],
            "vector": np.array([0.4, 0.9165], dtype=np.float32),
            "pagina": 2,
            "seccion": "Pasos",
        },
    ]
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: fragmentos)
    monkeypatch.setattr(
        retrieval,
        "embedding_normalizado",
        lambda _: np.array([1.0, 0.0], dtype=np.float32),
    )
    monkeypatch.setattr(
        retrieval,
        "settings",
        SimpleNamespace(
            rag_code_match_bonus=0.15,
            rag_hybrid_retrieval_enabled=False,
            rag_rrf_k=60,
            rag_component_anchor_enabled=False,
        ),
    )

    resultados = retrieval.buscar_fragmentos(
        "¿Cómo se comprueba el funcionamiento del electroventilador CMP-09?",
        "V2.0",
        2,
    )

    assert resultados[0]["seccion"] == "Objetivo"
    assert resultados[1]["seccion"] == "Pasos"


def test_consulta_procedimental_en_primera_persona():
    from services.ranking_operativo import es_consulta_procedimental

    assert es_consulta_procedimental("¿Cómo compruebo la bomba CMP-02?")
    assert es_consulta_procedimental("¿Cómo reviso el filtro CMP-24?")
    assert es_consulta_procedimental("¿Cómo mido el caudal de CMP-02?")
    assert not es_consulta_procedimental("¿Cómo es el problema de la bomba CMP-02?")
