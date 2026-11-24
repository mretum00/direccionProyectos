import pytest

from services.ranking_operativo import (
    codigos_componente,
    es_consulta_procedimental,
    es_seccion_operativa,
    reordenar_con_anclaje,
)


def _resultado(chunk_id, seccion, texto="", categoria="Manual", **scores):
    return {
        "chunk_id": chunk_id,
        "seccion": seccion,
        "texto": texto,
        "categoria": categoria,
        "score": scores.get("score", 0.5),
        "ranking_score": scores.get("ranking_score", 0.5),
        "rrf_score": scores.get("rrf_score", 0.02),
    }


def test_extrae_codigos_cmp_y_normaliza_guiones():
    assert codigos_componente("cmp09 CMP‑12 CMP-100") == {"CMP-09", "CMP-12"}


@pytest.mark.parametrize(
    "consulta",
    [
        "¿Cómo se comprueba el electroventilador CMP-09?",
        "¿De qué manera se puede verificar CMP-09?",
    ],
)
def test_detecta_consultas_procedimentales(consulta):
    assert es_consulta_procedimental(consulta)


@pytest.mark.parametrize(
    "consulta",
    [
        "¿Qué referencia tiene el electroventilador CMP-09?",
        "¿Cómo se llama el componente CMP-09?",
        "Comprueba el electroventilador CMP-09.",
    ],
)
def test_no_activa_anclaje_en_consultas_no_procedimentales(consulta):
    assert not es_consulta_procedimental(consulta)


@pytest.mark.parametrize(
    "seccion",
    [
        "Pasos",
        "Valores esperados",
        "Criterios de aceptación",
        "Verificación final",
        "4.5 Electroventilador funcionando de forma continua",
    ],
)
def test_reconoce_secciones_operativas(seccion):
    assert es_seccion_operativa(seccion)


def test_prioriza_pasos_del_documento_que_menciona_cmp_consultado():
    consulta = "¿Cómo se comprueba el funcionamiento del electroventilador CMP-09?"
    resultados = [
        _resultado(
            "PRC005.pdf_1",
            "Objetivo",
            "Comprobar el electroventilador CMP-09.",
            rrf_score=0.04,
        ),
        _resultado(
            "PRC005.pdf_2",
            "Pasos",
            "Conectar HTM-SCAN y probar PWM al 25, 50, 75 y 100 por ciento.",
            rrf_score=0.01,
        ),
        _resultado(
            "PRC005.pdf_3",
            "Valores esperados",
            "La velocidad debe ser proporcional a la consigna.",
            rrf_score=0.009,
        ),
        _resultado(
            "OTRO.pdf_1",
            "Pasos",
            "Procedimiento de otro componente CMP-10.",
            rrf_score=0.03,
        ),
    ]
    originales = [dict(resultado) for resultado in resultados]

    ordenados, diagnostico = reordenar_con_anclaje(consulta, resultados)

    assert ordenados[0]["chunk_id"] == "PRC005.pdf_2"
    assert ordenados[1]["chunk_id"] == "PRC005.pdf_3"
    assert diagnostico["documentos_anclados"] == ["PRC005.pdf"]
    # El reranker es no destructivo.
    assert resultados == originales


def test_no_aplica_anclaje_si_no_hay_codigo_cmp_en_consulta():
    consulta = "¿Cómo se comprueba el funcionamiento del electroventilador?"
    resultados = [
        _resultado("PRC005.pdf_1", "Objetivo", "Electroventilador CMP-09.", rrf_score=0.04),
        _resultado("PRC005.pdf_2", "Pasos", "Conectar HTM-SCAN.", rrf_score=0.01),
    ]

    ordenados, diagnostico = reordenar_con_anclaje(consulta, resultados)

    assert [r["chunk_id"] for r in ordenados] == [
        "PRC005.pdf_1",
        "PRC005.pdf_2",
    ]
    assert diagnostico["documentos_anclados"] == []


def test_no_modifica_score_ranking_ni_rrf():
    consulta = "¿Cómo se comprueba el electroventilador CMP-09?"
    resultados = [
        _resultado("PRC005.pdf_1", "Objetivo", "CMP-09.", score=0.8, ranking_score=0.9, rrf_score=0.04),
        _resultado("PRC005.pdf_2", "Pasos", "Medir PWM.", score=0.4, ranking_score=0.5, rrf_score=0.01),
    ]

    ordenados, _ = reordenar_con_anclaje(consulta, resultados)
    por_id = {r["chunk_id"]: r for r in ordenados}

    assert por_id["PRC005.pdf_2"]["score"] == 0.4
    assert por_id["PRC005.pdf_2"]["ranking_score"] == 0.5
    assert por_id["PRC005.pdf_2"]["rrf_score"] == 0.01


def test_dtc_exacto_mantiene_prioridad_sobre_anclaje_operativo():
    consulta = (
        "¿Cómo comprobar CMP-09 ante el código HTM-0142?"
    )
    resultados = [
        _resultado(
            "PRC005.pdf_1",
            "Pasos",
            "Procedimiento para CMP-09.",
            categoria="Manual",
            rrf_score=0.03,
        ),
        _resultado(
            "catalogo.pdf_1",
            "HTM-0142",
            "Ficha DTC exacta.",
            categoria="DTC",
            rrf_score=0.001,
        ),
    ]

    ordenados, _ = reordenar_con_anclaje(consulta, resultados)

    assert ordenados[0]["chunk_id"] == "catalogo.pdf_1"
