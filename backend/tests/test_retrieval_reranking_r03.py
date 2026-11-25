"""Pruebas de integración del flag R03 en el recuperador real."""
from types import SimpleNamespace

import numpy as np

from services import retrieval


def _fragmento(documento: str, identificador: str, seccion: str, categoria: str = "Manual") -> dict:
    return {
        "chunk_id": f"{documento}_{identificador}",
        "texto": f"Contenido técnico de {seccion}",
        "categoria": categoria,
        "versiones": ["V2.0"],
        "vector": np.array([1.0], dtype=np.float32),
        "pagina": 1,
        "seccion": seccion,
    }


def _preparar(monkeypatch, fragmentos, *, combinado: bool):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: fragmentos)
    monkeypatch.setattr(retrieval, "embedding_normalizado", lambda _consulta: np.array([1.0], dtype=np.float32))
    monkeypatch.setattr(retrieval, "reordenar_con_anclaje", lambda _consulta, resultados: (resultados, {}))
    monkeypatch.setattr(
        retrieval,
        "settings",
        SimpleNamespace(
            rag_code_match_bonus=0.15,
            rag_hybrid_retrieval_enabled=False,
            rag_component_anchor_enabled=False,
            rag_combined_reranking_enabled=combinado,
            rag_rrf_k=60,
        ),
    )


def test_flag_desactivado_conserva_limite_actual_de_dos_por_pdf(monkeypatch):
    fragmentos = [
        _fragmento("CATALOGO", "cmp03", "CMP-03"),
        _fragmento("DOC_A", "intro", "Introducción"),
        _fragmento("CATALOGO", "cmp01", "CMP-01"),
        _fragmento("DOC_B", "intro", "Introducción"),
        _fragmento("CATALOGO", "cmp02", "CMP-02"),
        _fragmento("DOC_C", "intro", "Introducción"),
    ]
    _preparar(monkeypatch, fragmentos, combinado=False)

    resultado = retrieval.buscar_fragmentos("Compara CMP-01, CMP-02 y CMP-03", "V2.0", 5)

    ids = [r["chunk_id"] for r in resultado]
    assert ids == ["CATALOGO_cmp03", "DOC_A_intro", "CATALOGO_cmp01", "DOC_B_intro", "DOC_C_intro"]
    assert sum(r["chunk_id"].startswith("CATALOGO_") for r in resultado) == 2


def test_flag_activado_aplica_combinada_antes_del_limite_de_dos_por_pdf(monkeypatch):
    fragmentos = [
        _fragmento("CATALOGO", "cmp03", "CMP-03"),
        _fragmento("DOC_A", "intro", "Introducción"),
        _fragmento("CATALOGO", "cmp01", "CMP-01"),
        _fragmento("DOC_B", "intro", "Introducción"),
        _fragmento("CATALOGO", "cmp02", "CMP-02"),
        _fragmento("DOC_C", "intro", "Introducción"),
    ]
    _preparar(monkeypatch, fragmentos, combinado=True)

    resultado = retrieval.buscar_fragmentos("Compara CMP-01, CMP-02 y CMP-03", "V2.0", 5)

    ids = [r["chunk_id"] for r in resultado]
    assert ids[:3] == ["CATALOGO_cmp01", "CATALOGO_cmp02", "CATALOGO_cmp03"]
    assert len(resultado) == 5
    assert len(ids) == len(set(ids))
    # El reranking no debe alterar la similitud coseno usada para la evidencia.
    assert all(r["score"] == 1.0 for r in resultado)


def test_consulta_con_codigo_htm_conserva_prioridad_dtc_aunque_flag_este_activo(monkeypatch):
    fragmentos = [
        _fragmento("DOC_MANUAL", "intro", "Introducción"),
        _fragmento("CATALOGO", "cmp01", "CMP-01"),
        _fragmento("CATALOGO", "cmp02", "CMP-02"),
        _fragmento("DTC", "htm0142", "HTM-0142", categoria="DTC"),
    ]
    _preparar(monkeypatch, fragmentos, combinado=True)

    resultado = retrieval.buscar_fragmentos(
        "¿Qué significa HTM-0142? Compara CMP-01 y CMP-02.", "V2.0", 5
    )

    assert resultado[0]["chunk_id"] == "DTC_htm0142"
    # Al incluir un código HTM, COMBINADA delega al baseline para no tocar
    # la prioridad estructural que ya garantiza la recuperación.
    assert [r["chunk_id"] for r in resultado] == [
        "DTC_htm0142", "DOC_MANUAL_intro", "CATALOGO_cmp01", "CATALOGO_cmp02"
    ]



def test_especificacion_de_un_cmp_prioriza_ficha_exacta_con_flag_activo(monkeypatch):
    fragmentos = [
        _fragmento("PRC003", "valores", "Valores esperados"),
        _fragmento("DTC", "htm0202", "HTM-0202", categoria="DTC"),
        _fragmento("BOL002", "contenido", "Contenido"),
        _fragmento("PRC003", "objetivo", "Objetivo"),
        _fragmento("CATALOGO", "cmp02", "CMP-02"),
    ]
    _preparar(monkeypatch, fragmentos, combinado=True)

    resultado = retrieval.buscar_fragmentos(
        "¿Qué caudal nominal tiene la bomba eléctrica auxiliar A CMP-02?",
        "V2.0",
        5,
    )

    assert resultado[0]["chunk_id"] == "CATALOGO_cmp02"
    assert resultado[0]["seccion"] == "CMP-02"
    assert all(r["score"] == 1.0 for r in resultado)


def test_consulta_procedimental_de_un_cmp_conserva_prioridad_de_pasos(monkeypatch):
    fragmentos = [
        _fragmento("PRC003", "intro", "Objetivo"),
        _fragmento("CATALOGO", "cmp02", "CMP-02"),
        _fragmento("PRC003", "pasos", "Pasos"),
        _fragmento("DOC_B", "intro", "Introducción"),
    ]
    _preparar(monkeypatch, fragmentos, combinado=True)

    resultado = retrieval.buscar_fragmentos(
        "¿Cómo comprobar el caudal de CMP-02?", "V2.0", 4
    )

    assert resultado[0]["seccion"] == "Pasos"
