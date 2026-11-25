"""Pruebas unitarias del reranking experimental COMBINADA (R03).

Estas pruebas validan la selección de resultados con rankings sintéticos.
No consultan la base de datos, no llaman al LLM y no modifican retrieval.py.

Ubicación en el repositorio:
    backend/tests/test_reranking_r03.py

Ejecución desde la raíz del repositorio:
    py -3 -m pytest backend/tests/test_reranking_r03.py -v
"""

from services.ranking_combinado import (
    seleccionar_baseline,
    seleccionar_combinada,
    seleccionar_intencion_intercalada,
)


def crear_fragmento(documento: str, identificador: str, seccion: str) -> dict:
    """Construye un fragmento mínimo con el formato esperado por el reranking."""
    return {
        "chunk_id": f"{documento}_{identificador}",
        "seccion": seccion,
        "score": 0.8,
        "versiones": ["V2.0"],
    }


def ids(resultados: list[dict]) -> list[str]:
    """Devuelve los identificadores en el orden seleccionado."""
    return [resultado["chunk_id"] for resultado in resultados]


def test_combinada_prioriza_las_dos_fichas_cmp_en_el_orden_del_codigo():
    consulta = "Compara CMP-02 y CMP-03."
    ranking = [
        crear_fragmento("DOC_A", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "cmp03", "CMP-03"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "cmp02", "CMP-02"),
        crear_fragmento("DOC_C", "intro", "Introducción"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=5)

    # Aunque CMP-03 aparezca antes en el ranking, se recorren los códigos
    # ordenados y ambas fichas exactas deben quedar al principio.
    assert ids(resultado)[:2] == ["CATALOGO_cmp02", "CATALOGO_cmp03"]
    assert len(resultado) == 5
    assert len(ids(resultado)) == len(set(ids(resultado)))


def test_combinada_conserva_tres_cmp_aunque_pertenezcan_al_mismo_documento():
    consulta = "Compara los componentes CMP-01, CMP-02 y CMP-03."
    ranking = [
        crear_fragmento("CATALOGO", "cmp03", "CMP-03"),
        crear_fragmento("DOC_A", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "cmp01", "CMP-01"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "cmp02", "CMP-02"),
        crear_fragmento("DOC_C", "intro", "Introducción"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=5)

    assert ids(resultado)[:3] == [
        "CATALOGO_cmp01",
        "CATALOGO_cmp02",
        "CATALOGO_cmp03",
    ]
    # La prioridad de las fichas exactas CMP permite superar el límite
    # ordinario de dos fragmentos del mismo documento.
    assert sum(r["chunk_id"].startswith("CATALOGO_") for r in resultado) == 3
    assert len(resultado) == 5
    assert len(ids(resultado)) == len(set(ids(resultado)))


def test_sin_varios_cmp_combinada_equivale_a_intencion_intercalada():
    consulta = "¿Cómo comprobar el circuito asociado a CMP-02?"
    ranking = [
        crear_fragmento("DOC_PRINCIPAL", "intro", "Introducción"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
        crear_fragmento("DOC_PRINCIPAL", "pasos", "Pasos"),
        crear_fragmento("DOC_C", "intro", "Introducción"),
        crear_fragmento("DOC_PRINCIPAL", "valores", "Valores esperados"),
        crear_fragmento("DOC_D", "intro", "Introducción"),
    ]

    resultado_combinada = seleccionar_combinada(consulta, ranking, top_k=5)
    resultado_intercalada = seleccionar_intencion_intercalada(
        consulta, ranking, top_k=5
    )

    assert ids(resultado_combinada) == ids(resultado_intercalada)
    assert resultado_combinada[0]["seccion"] == "Pasos"


def test_consulta_con_dtc_exacto_conserva_el_comportamiento_baseline():
    consulta = "¿Qué significa HTM-0142? Compara también CMP-01 y CMP-02."
    ranking = [
        crear_fragmento("DOC_A", "uno", "Introducción"),
        crear_fragmento("DOC_A", "dos", "Pasos"),
        crear_fragmento("CATALOGO", "cmp01", "CMP-01"),
        crear_fragmento("CATALOGO", "cmp02", "CMP-02"),
        crear_fragmento("DOC_A", "tres", "Valores esperados"),
        crear_fragmento("DOC_B", "uno", "Introducción"),
    ]

    resultado_combinada = seleccionar_combinada(consulta, ranking, top_k=5)
    resultado_baseline = seleccionar_baseline(ranking, top_k=5)

    assert ids(resultado_combinada) == ids(resultado_baseline)


def test_si_no_hay_fichas_cmp_exactas_se_usa_intencion_intercalada():
    consulta = "¿Cómo comprobar CMP-01 y CMP-02?"
    ranking = [
        crear_fragmento("DOC_PRINCIPAL", "intro", "Introducción"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
        crear_fragmento("DOC_PRINCIPAL", "pasos", "Pasos"),
        # La mera mención del código en el nombre de sección no es una ficha
        # exacta CMP-XX: el script exige que toda la sección coincida.
        crear_fragmento("CATALOGO", "mencion01", "Ficha general de CMP-01"),
        crear_fragmento("DOC_C", "intro", "Introducción"),
    ]

    resultado_combinada = seleccionar_combinada(consulta, ranking, top_k=5)
    resultado_intercalada = seleccionar_intencion_intercalada(
        consulta, ranking, top_k=5
    )

    assert ids(resultado_combinada) == ids(resultado_intercalada)


def test_si_solo_existe_una_ficha_cmp_prioriza_esa_y_no_inventa_la_otra():
    consulta = "Compara CMP-01 y CMP-02."
    ranking = [
        crear_fragmento("DOC_PRINCIPAL", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "cmp01", "CMP-01"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "mencion02", "Ficha general de CMP-02"),
        crear_fragmento("DOC_C", "intro", "Introducción"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=5)

    assert resultado[0]["chunk_id"] == "CATALOGO_cmp01"
    assert not any(r.get("seccion") == "CMP-02" for r in resultado)
    assert len(ids(resultado)) == len(set(ids(resultado)))
    assert len(resultado) <= 5


def test_combinada_no_supera_top_k_aunque_haya_mas_candidatos():
    consulta = "Compara CMP-01 y CMP-02."
    ranking = [
        crear_fragmento("CATALOGO", "cmp01", "CMP-01"),
        crear_fragmento("CATALOGO", "cmp02", "CMP-02"),
        crear_fragmento("DOC_A", "uno", "Introducción"),
        crear_fragmento("DOC_B", "uno", "Introducción"),
        crear_fragmento("DOC_C", "uno", "Introducción"),
        crear_fragmento("DOC_D", "uno", "Introducción"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=3)

    assert len(resultado) == 3
    assert ids(resultado)[:2] == ["CATALOGO_cmp01", "CATALOGO_cmp02"]
    assert len(ids(resultado)) == len(set(ids(resultado)))



def test_especificacion_de_un_cmp_prioriza_su_ficha_exacta_de_catalogo():
    consulta = "¿Qué caudal nominal tiene la bomba eléctrica auxiliar A CMP-02?"
    ranking = [
        crear_fragmento("PRC003", "valores", "Valores esperados"),
        crear_fragmento("DTC", "htm0202", "HTM-0202"),
        crear_fragmento("BOL002", "contenido", "Contenido"),
        crear_fragmento("PRC003", "objetivo", "Objetivo"),
        crear_fragmento("CATALOGO", "cmp02", "CMP-02"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=5)

    assert ids(resultado)[0] == "CATALOGO_cmp02"
    assert len(resultado) == 5
    assert len(ids(resultado)) == len(set(ids(resultado)))
    # La selección conserva intactas las puntuaciones originales.
    assert all(fragmento["score"] == 0.8 for fragmento in resultado)


def test_consulta_procedimental_de_un_cmp_no_prioriza_la_ficha_de_catalogo():
    consulta = "¿Cómo comprobar el caudal de CMP-02?"
    ranking = [
        crear_fragmento("PRC003", "intro", "Objetivo"),
        crear_fragmento("CATALOGO", "cmp02", "CMP-02"),
        crear_fragmento("PRC003", "pasos", "Pasos"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=4)
    esperado = seleccionar_intencion_intercalada(consulta, ranking, top_k=4)

    assert ids(resultado) == ids(esperado)
    assert resultado[0]["seccion"] == "Pasos"


def test_especificacion_de_un_cmp_sin_ficha_exacta_usa_intercalado():
    consulta = "¿Qué caudal nominal tiene CMP-02?"
    ranking = [
        crear_fragmento("PRC003", "valores", "Valores esperados"),
        crear_fragmento("DOC_B", "intro", "Introducción"),
        crear_fragmento("CATALOGO", "mencion", "Ficha general de CMP-02"),
    ]

    resultado = seleccionar_combinada(consulta, ranking, top_k=3)
    esperado = seleccionar_intencion_intercalada(consulta, ranking, top_k=3)

    assert ids(resultado) == ids(esperado)
