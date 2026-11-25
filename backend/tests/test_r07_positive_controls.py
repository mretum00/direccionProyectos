
"""Controles positivos y parciales del benchmark R07.

Comprueba que:
- SUFFICIENT: todos los datos solicitados están documentados.
- PARTIAL: hay datos documentados y otros que faltan.
- Las citas aceptadas existen literalmente en los fragmentos.
"""

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
# El test valida la comprobación local de citas, sin llamar a Groq.
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
    # El caso parcial reutiliza el fragmento real de CMP-02:
    # contiene el caudal, pero no documenta la vida útil.
    "R07-P04-CAUDAL-VIDA-CMP02": {
        "chunk_id": "HTM240-CAT-001_Catalogo_componentes.pdf_2",
        "texto": (
            "CMP-02 — Bomba eléctrica auxiliar A (circuito batería) "
            "Valores nominales: Caudal 8-14 l/min, 12V, 3-6A"
        ),
        "cita": "Valores nominales: Caudal 8-14 l/min, 12V, 3-6A",
    },
}


def normalizar(texto):
    """Normaliza mayúsculas y espacios para comparar nombres de elementos."""
    return " ".join(str(texto).casefold().split())


def construir_respuesta_simulada(caso, evidencia):
    """Simula la respuesta del evaluador LLM sin realizar llamadas externas."""

    estado_esperado = caso.get("estado_suficiencia_esperado", "sufficient")

    if estado_esperado == "partial":
        return {
            "items": [
                {
                    "item": "Caudal nominal de la bomba eléctrica auxiliar A CMP-02",
                    "status": "supported",
                    "source_refs": ["F1"],
                    "evidence_quote": evidencia["cita"],
                },
                {
                    "item": "Vida útil de la bomba eléctrica auxiliar A CMP-02",
                    "status": "not_found",
                    "source_refs": [],
                    "evidence_quote": "",
                },
            ]
        }

    return {
        "items": [
            {
                "item": caso["dato_esperado"],
                "status": "supported",
                "source_refs": ["F1"],
                "evidence_quote": evidencia["cita"],
            }
        ]
    }


@pytest.mark.parametrize(
    "caso",
    json.loads(BENCHMARK.read_text(encoding="utf-8"))["casos"],
    ids=lambda caso: caso["id"],
)
def test_control_r07_respeta_suficiencia_y_citas(caso):
    evidencia = EVIDENCIAS[caso["id"]]
    estado_esperado = caso.get("estado_suficiencia_esperado", "sufficient")

    fragmento = {
        "chunk_id": evidencia["chunk_id"],
        "texto": evidencia["texto"],
        "seccion": caso["id"],
        "pagina": None,
        "score": 0.9,
    }

    salida = construir_respuesta_simulada(caso, evidencia)

    resultado = evaluar_suficiencia_evidencia(
        caso["consulta"],
        [fragmento],
        generador=lambda _prompt: json.dumps(salida, ensure_ascii=False),
    )

    # Comprobación de la fuente documental.
    assert caso["fuente_esperada"] == evidencia["chunk_id"]

    # Comprobación del estado global.
    assert resultado["status"] == estado_esperado

    elementos = resultado["requested_items"]

    if estado_esperado == "sufficient":
        # Todos los datos deben estar respaldados.
        assert elementos
        assert all(item["status"] == "supported" for item in elementos)
        assert resultado["missing_information"] == []

        for item in elementos:
            assert item["source_ids"] == [evidencia["chunk_id"]]
            assert item["evidence_excerpt"] == evidencia["cita"]

    elif estado_esperado == "partial":
        # Debe existir al menos un dato respaldado y otro no respaldado.
        assert any(item["status"] == "supported" for item in elementos)
        assert any(item["status"] == "not_found" for item in elementos)

        assert resultado["missing_information"]

        # Cada elemento esperado debe aparecer con su estado correspondiente.
        for esperado in caso.get("elementos_esperados", []):
            texto_esperado = normalizar(esperado["contiene"])
            estado_item = esperado["estado"]

            encontrados = [
                item
                for item in elementos
                if texto_esperado in normalizar(item["item"])
            ]

            assert encontrados, (
                f"No se encontró el elemento solicitado: {esperado['contiene']}"
            )

            assert any(
                item["status"] == estado_item
                for item in encontrados
            ), (
                f"El elemento '{esperado['contiene']}' debía ser "
                f"{estado_item}, pero se obtuvo "
                f"{[item['status'] for item in encontrados]}"
            )

        # El dato respaldado debe conservar su cita literal.
        respaldados = [
            item for item in elementos
            if item["status"] == "supported"
        ]

        for item in respaldados:
            assert item["source_ids"] == [evidencia["chunk_id"]]
            assert item["evidence_excerpt"] == evidencia["cita"]

        # El dato ausente no puede tener citas ni fuentes inventadas.
        no_respaldados = [
            item for item in elementos
            if item["status"] == "not_found"
        ]

        for item in no_respaldados:
            assert item["source_ids"] == []
            assert item["evidence_excerpt"] is None
