"""Pruebas unitarias para la trazabilidad de fuentes declaradas por el modelo."""

from services.respuestas import construir_fuentes, extraer_referencias_citadas


def test_extrae_solo_referencias_de_la_seccion_fuente():
    respuesta = """### RESUMEN
La conclusión se apoya en [F2], pero esta mención no está en la sección de fuentes.

### FUENTE
- [F1] Catálogo DTC, página 1.
- [F3] Manual de diagnóstico, página 4.
"""
    assert extraer_referencias_citadas(respuesta, total_fragmentos=3) == {1, 3}


def test_ignora_identificadores_inventados_o_fuera_de_rango():
    respuesta = """### FUENTE
- [F1] Documento real.
- [F8] Identificador fuera del contexto.
- [F0] Índice no válido.
- [X2] Marcador desconocido.
"""
    assert extraer_referencias_citadas(respuesta, total_fragmentos=3) == {1}


def test_sin_seccion_fuente_no_declara_citas():
    respuesta = "### RESUMEN\nLa respuesta menciona [F1], pero no incluye una sección de fuentes."
    assert extraer_referencias_citadas(respuesta, total_fragmentos=2) == set()


def test_construir_fuentes_distingue_citadas_y_recuperadas():
    fragmentos = [
        {
            "chunk_id": "HTM240-DTC-001_Catalogo_DTC.pdf_1",
            "texto": "Definición del código HTM-0101.",
            "categoria": "DTC",
            "versiones": ["V1.1"],
            "pagina": 1,
            "seccion": "HTM-0101",
        },
        {
            "chunk_id": "HTM240-DIA-001_Manual_diagnostico.pdf_3",
            "texto": "Procedimiento de diagnóstico.",
            "categoria": "Manual",
            "versiones": ["V1.1"],
            "pagina": 3,
            "seccion": None,
        },
    ]

    fuentes = construir_fuentes(fragmentos, "V1.1", referencias_citadas={1})

    assert fuentes[0]["citation_status"] == "cited"
    assert fuentes[1]["citation_status"] == "retrieved"
    assert fuentes[0]["document"] == "HTM240-DTC-001_Catalogo_DTC.pdf"


def test_contrato_source_admite_cita_literal_verificada_por_backend():
    from models.schemas import Source

    fuente = Source(
        id="HTM240-CAT-001_Catalogo_componentes.pdf_2",
        document="HTM240-CAT-001_Catalogo_componentes.pdf",
        source_type="manual",
        citation_status="verified",
    )

    assert fuente.citation_status == "verified"
