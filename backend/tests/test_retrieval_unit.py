"""Pruebas unitarias de recuperación; no descargan el modelo ni necesitan SQLite real."""

import numpy as np
import pytest

from services import retrieval


@pytest.fixture
def vectores(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "embedding_normalizado",
        lambda _consulta: np.array([1.0, 0.0], dtype=np.float32),
    )


def fragmento(chunk_id, texto, categoria="Manual", versiones=("V1.0",), vector=(1.0, 0.0)):
    return {
        "chunk_id": chunk_id,
        "texto": texto,
        "categoria": categoria,
        "versiones": list(versiones),
        "vector": np.asarray(vector, dtype=np.float32),
        "pagina": 1,
        "seccion": None,
    }


def test_solo_devuelve_fragmentos_de_la_version_seleccionada_y_no_el_glosario(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento("manual_v1_1", "Mantenimiento del refrigerante", versiones=("V1.0",)),
        fragmento("manual_v2_1", "Mantenimiento del refrigerante", versiones=("V2.0",)),
        fragmento("diccionario_1", "Refrigerante: fluido térmico", categoria="Dictionary"),
    ])

    resultados = retrieval.buscar_fragmentos("mantenimiento", "V1.0", 5)

    assert [resultado["chunk_id"] for resultado in resultados] == ["manual_v1_1"]
    assert all("V1.0" in resultado["versiones"] for resultado in resultados)


def test_prioriza_la_coincidencia_exacta_de_codigo_dtc(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento("dtc_otra", "Código HTM-0143", vector=(0.8, 0.6)),
        fragmento("dtc_exacto", "Código HTM-0142: fallo de bomba", vector=(0.8, 0.6)),
    ])

    resultados = retrieval.buscar_fragmentos("significado HTM-0142", "V1.0", 2)

    assert resultados[0]["chunk_id"] == "dtc_exacto"
    assert resultados[0]["score"] > resultados[1]["score"]


def test_respeta_top_k_y_ordena_por_similitud(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento("bajo", "Coincidencia baja", vector=(0.2, 0.98)),
        fragmento("alto", "Coincidencia alta", vector=(0.9, 0.435)),
        fragmento("medio", "Coincidencia media", vector=(0.6, 0.8)),
    ])

    resultados = retrieval.buscar_fragmentos("consulta", "V1.0", 2)

    assert [resultado["chunk_id"] for resultado in resultados] == ["alto", "medio"]
    assert len(resultados) == 2


def test_devuelve_lista_vacia_si_no_hay_fragmentos_aplicables(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento("solo_v2", "Documento de otra versión", versiones=("V2.0",)),
    ])

    assert retrieval.buscar_fragmentos("consulta", "V1.0", 5) == []
