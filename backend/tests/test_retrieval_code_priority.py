"""Pruebas de integración para priorizar la entrada DTC del código consultado.

Requieren la base documental real y el modelo de embeddings.
"""
import pytest

from services.retrieval import buscar_fragmentos

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("consulta", "version", "codigo"),
    [
        ("¿Qué significa el código HTM-0101? sobretemperatura motor CIR-01", "V2.0", "HTM-0101"),
        ("HTM-0142 código DTC catálogo", "V2.0", "HTM-0142"),
    ],
)
def test_la_entrada_dtc_del_codigo_consultado_aparece_primera(
    consulta, version, codigo
):
    resultados = buscar_fragmentos(consulta, version, 5)

    assert resultados, f"La búsqueda no devolvió resultados para {codigo}"

    primero = resultados[0]

    assert primero["categoria"] == "DTC"
    assert primero["seccion"] == codigo
