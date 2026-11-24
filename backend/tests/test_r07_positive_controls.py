"""Controles positivos del benchmark R07: los datos sí están en el catálogo."""

import json
from pathlib import Path

import pytest

from services.suficiencia_evidencia import evaluar_suficiencia_evidencia


BENCHMARK = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "benchmark_r07_controles_positivos.json"
)

# Extractos fieles a los fragmentos reales de HTM240-CAT-001 incluidos en SQLite.
# El test valida la puerta local de citas; no simula que el LLM haya respondido en producción.
EVIDENCIAS = {
    "R07-P01-CAUDAL-CMP02": {
        "chunk_id": "HTM240-CAT-001_Catalogo_componentes.pdf_2",
        "texto": (
            "CMP-02 — Bomba eléctrica auxiliar A (circuito batería) "
            "Valores nominales: Caudal 8-14 l/min, 12V, 3-6A"
        ),
        "cita": "Valores nominales: Caudal 8-14 l/min, 12V, 3-6A",
    },
    "R07-P02-CONSUMO-CMP09": {
        "chunk_id": "HTM240-CAT-001_Catalogo_componentes.pdf_10",
        "texto": (
            "CMP-09 — Electroventilador de velocidad variable "
            "Valores nominales: 0-100% PWM, consumo max 18A"
        ),
        "cita": "Valores nominales: 0-100% PWM, consumo max 18A",
    },
    "R07-P03-PRESION-CMP07": {
        "chunk_id": "HTM240-CAT-001_Catalogo_componentes.pdf_8",
        "texto": (
            "CMP-07 — Vaso de expansión "
            "Valores nominales: Nivel MIN-MAX, tapón 1.4 bar"
        ),
        "cita": "Valores nominales: Nivel MIN-MAX, tapón 1.4 bar",
    },
}


@pytest.mark.parametrize(
    "caso",
    json.loads(BENCHMARK.read_text(encoding="utf-8"))["casos"],
    ids=lambda caso: caso["id"],
)
def test_control_positivo_r07_acepta_dato_y_cita_literal(caso):
    evidencia = EVIDENCIAS[caso["id"]]
    fragmento = {
        "chunk_id": evidencia["chunk_id"],
        "texto": evidencia["texto"],
        "seccion": caso["id"],
        "pagina": None,
        "score": 0.9,
    }
    salida = {
        "items": [
            {
                "item": caso["dato_esperado"],
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": evidencia["cita"],
            }
        ]
    }

    resultado = evaluar_suficiencia_evidencia(
        caso["consulta"],
        [fragmento],
        generador=lambda _prompt: json.dumps(salida, ensure_ascii=False),
    )

    assert caso["fuente_esperada"] == evidencia["chunk_id"]
    assert resultado["status"] == "sufficient"
    assert resultado["requested_items"][0]["status"] == "supported"
    assert resultado["requested_items"][0]["source_ids"] == [evidencia["chunk_id"]]
    assert resultado["missing_information"] == []
