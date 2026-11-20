"""Pruebas de integración: requieren la BD documental y el modelo de embeddings."""

import pytest

pytestmark = pytest.mark.integration

import pytest
from config import settings
from services.retrieval import buscar_fragmentos


def test_nunca_devuelve_otra_version():
    for version in ("V1.0", "V1.1", "V2.0"):
        for f in buscar_fragmentos("mantenimiento del refrigerante", version, 5):
            assert version in f["versiones"]


def test_pregunta_fuera_de_tema_no_pasa_el_umbral():
    resultados = buscar_fragmentos("¿Cuál es la capital de Francia?", "V1.0", 5)
    assert resultados[0]["score"] < settings.rag_evidence_min_score



def test_codigo_dtc_encuentra_el_catalogo():
    resultados = buscar_fragmentos(
        "HTM-0142 código DTC catálogo",
        "V2.0",
        10
    )

    print("\n--- RESULTADOS DE LA BUSQUEDA ---")
    print(f"Base de datos: {settings.db_path}")
    print(f"Resultados encontrados: {len(resultados)}")

    for r in resultados:
        print(
            f"ID: {r['chunk_id']} | "
            f"Categoría: {r['categoria']} | "
            f"Puntuación: {r['score']:.4f} | "
            f"Contiene HTM-0142: {'HTM-0142' in r['texto']}"
        )

    assert any(
        r["categoria"] == "DTC"
        and "HTM-0142" in r["texto"]
        for r in resultados
    )
