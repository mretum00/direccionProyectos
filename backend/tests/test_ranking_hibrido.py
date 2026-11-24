"""Pruebas del ranking BM25 + RRF, sin SQLite ni llamadas a modelos."""
from __future__ import annotations

import pytest

from services.ranking_hibrido import calcular_bm25, normalizar, ordenar_hibrido, tokenizar


def _resultado(chunk_id: str, texto: str, seccion: str | None = None) -> dict:
    return {
        "chunk_id": chunk_id,
        "texto": texto,
        "categoria": "Manual",
        "score": 0.5,
        "ranking_score": 0.5,
        "seccion": seccion,
        "versiones": ["V2.0"],
        "pagina": 1,
    }


def test_normalizar_quita_tildes_y_minusculiza():
    assert normalizar("BOMBA AUXILIAR: presión y caudal") == "bomba auxiliar: presion y caudal"


def test_tokenizar_elimina_palabras_vacias_y_conserva_codigos():
    assert tokenizar("¿Cómo revisar el caudal de HTM-0101?") == [
        "revisar", "caudal", "htm", "0101"
    ]


def test_bm25_puntua_mas_al_fragmento_con_terminos_tecnicos_coincidentes():
    consulta = "caudal bomba filtro obstruido"
    candidatos = [
        _resultado("manual.pdf_1", "Temperatura del motor y refrigerante"),
        _resultado("prc.pdf_2", "Comprobar el caudal de la bomba y el filtro obstruido"),
        _resultado("otro.pdf_3", "Verificar la bomba auxiliar"),
    ]

    puntuaciones = calcular_bm25(consulta, candidatos)

    assert puntuaciones[1] > puntuaciones[2] > puntuaciones[0]


def test_rrf_puede_promover_coincidencia_lexica_sin_alterar_scores():
    consulta = "caudal bomba filtro obstruido"
    semanticos = [
        _resultado("manual.pdf_1", "Diagnóstico de temperatura del motor"),
        _resultado("prc.pdf_2", "Comprobar caudal de bomba filtro obstruido"),
        _resultado("otro.pdf_3", "Comprobar bomba auxiliar"),
    ]
    semanticos[0]["score"] = 0.95
    semanticos[0]["ranking_score"] = 0.95
    semanticos[1]["score"] = 0.70
    semanticos[1]["ranking_score"] = 0.70
    semanticos[2]["score"] = 0.60
    semanticos[2]["ranking_score"] = 0.60

    fusionados = ordenar_hibrido(consulta, semanticos, rrf_k=60)

    assert fusionados[0]["chunk_id"] == "prc.pdf_2"
    assert fusionados[0]["score"] == pytest.approx(0.70)
    assert fusionados[0]["ranking_score"] == pytest.approx(0.70)
    assert fusionados[0]["bm25_score"] > 0
    # La función devuelve copias y no altera el orden ni los diccionarios originales.
    assert [r["chunk_id"] for r in semanticos] == [
        "manual.pdf_1", "prc.pdf_2", "otro.pdf_3"
    ]


def test_rrf_devuelve_lista_vacia_y_rechaza_constante_invalida():
    assert ordenar_hibrido("consulta", []) == []
    with pytest.raises(ValueError, match="rrf_k"):
        ordenar_hibrido("consulta", [_resultado("a.pdf_1", "texto")], rrf_k=0)
