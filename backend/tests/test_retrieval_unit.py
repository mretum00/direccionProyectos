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
    # La coincidencia exacta modifica el orden, pero no infla la similitud coseno.
    assert resultados[0]["score"] == pytest.approx(0.8)
    assert resultados[0]["ranking_score"] > resultados[1]["ranking_score"]


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


def test_prioriza_la_seccion_dtc_exacta_frente_a_otra_entrada_muy_similar(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento(
            "dtc_htm0205",
            "HTM-0205 desequilibrio térmico de batería",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.99, 0.141),
        ) | {"seccion": "HTM-0205"},
        fragmento(
            "dtc_htm0101",
            "HTM-0101 sobretemperatura del motor",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.75, 0.661),
        ) | {"seccion": "HTM-0101"},
    ])

    resultados = retrieval.buscar_fragmentos("significado del código HTM-0101", "V2.0", 2)

    assert resultados[0]["chunk_id"] == "dtc_htm0101"
    # Con una entrada exacta disponible, la entrada DTC de otro código se excluye.
    assert len(resultados) == 1
    # La prioridad exacta no altera la puntuación semántica usada por el pipeline.
    assert resultados[0]["score"] == pytest.approx(0.75)
    assert resultados[0]["ranking_score"] > resultados[0]["score"]


def test_normaliza_guion_unicode_en_codigos_htm():
    assert retrieval._extraer_codigos_htm("significado HTM‑0101") == {"HTM-0101"}


def test_no_aplica_ajuste_de_codigo_si_la_consulta_no_contiene_codigo():
    fragmento_sin_codigo = fragmento("manual_1", "Sobretemperatura del motor")
    assert retrieval._ajuste_orden_codigo(fragmento_sin_codigo, set()) == 0.0


def test_excluye_otras_entradas_dtc_si_existe_el_codigo_solicitado(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento(
            "catalogo_0101_1",
            "HTM-0101 sobretemperatura del motor",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.70, 0.714),
        ) | {"seccion": "HTM-0101"},
        fragmento(
            "catalogo_0205_1",
            "HTM-0205 desequilibrio térmico de batería",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.99, 0.141),
        ) | {"seccion": "HTM-0205"},
        fragmento(
            "diagnostico_1",
            "4.1 Sobrecalentamiento del motor: comprobar refrigerante y electroventilador",
            categoria="Manual",
            versiones=("V2.0",),
            vector=(0.85, 0.527),
        ) | {"seccion": "4.1 Sobrecalentamiento del motor"},
    ])

    resultados = retrieval.buscar_fragmentos("significado del código HTM-0101", "V2.0", 5)

    ids = [r["chunk_id"] for r in resultados]
    assert ids[0] == "catalogo_0101_1"
    assert "catalogo_0205_1" not in ids
    assert "diagnostico_1" in ids


def test_excluye_boletin_dedicado_a_otro_codigo_si_no_menciona_el_solicitado(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento(
            "catalogo_0101_1",
            "HTM-0101 sobretemperatura del motor",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.70, 0.714),
        ) | {"seccion": "HTM-0101"},
        fragmento(
            "BOL-003.pdf_0",
            "HTM240-BOL-003 — Cambio de significado del código HTM-0142 entre V1.x y V2.0. Explica el fallo CMP-18.",
            categoria="Manual",
            versiones=("V2.0",),
            vector=(0.99, 0.141),
        ),
        fragmento(
            "diagnostico_1",
            "4.1 Sobrecalentamiento del motor: comprobar refrigerante y electroventilador",
            categoria="Manual",
            versiones=("V2.0",),
            vector=(0.85, 0.527),
        ) | {"seccion": "4.1 Sobrecalentamiento del motor"},
    ])

    resultados = retrieval.buscar_fragmentos("significado del código HTM-0101", "V2.0", 5)

    ids = [r["chunk_id"] for r in resultados]
    assert "BOL-003.pdf_0" not in ids
    assert "diagnostico_1" in ids


def test_no_excluye_contexto_si_el_codigo_consultado_no_existe_en_catalogo(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento(
            "catalogo_0205_1",
            "HTM-0205 desequilibrio térmico de batería",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.99, 0.141),
        ) | {"seccion": "HTM-0205"},
        fragmento(
            "manual_1",
            "Manual de diagnóstico térmico general",
            categoria="Manual",
            versiones=("V2.0",),
            vector=(0.80, 0.60),
        ),
    ])

    resultados = retrieval.buscar_fragmentos("significado del código HTM-9999", "V2.0", 5)

    assert {r["chunk_id"] for r in resultados} == {"catalogo_0205_1", "manual_1"}


def test_limita_a_dos_fragmentos_por_documento_para_evitar_redundancia(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento("Manual_A.pdf_1", "A1", vector=(0.99, 0.141)),
        fragmento("Manual_A.pdf_2", "A2", vector=(0.95, 0.312)),
        fragmento("Manual_A.pdf_3", "A3", vector=(0.90, 0.436)),
        fragmento("Manual_B.pdf_1", "B1", vector=(0.85, 0.527)),
        fragmento("Manual_C.pdf_1", "C1", vector=(0.80, 0.60)),
    ])

    resultados = retrieval.buscar_fragmentos("consulta", "V1.0", 4)

    assert [r["chunk_id"] for r in resultados] == [
        "Manual_A.pdf_1",
        "Manual_A.pdf_2",
        "Manual_B.pdf_1",
        "Manual_C.pdf_1",
    ]
    assert len(resultados) == 4

def test_dtc_exacto_va_antes_del_manual_aunque_tenga_menor_similitud(monkeypatch, vectores):
    """Una ficha DTC del código pedido debe encabezar la recuperación.

    Un manual general puede obtener una similitud coseno mayor por compartir
    términos con la consulta. La coincidencia exacta en la sección DTC es una
    señal estructural más específica y debe prevalecer en el orden.
    """
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [
        fragmento(
            "manual_general_1",
            "Manual general: descripción y diagnóstico del código HTM-0142",
            categoria="Manual",
            versiones=("V2.0",),
            vector=(1.0, 0.0),
        ),
        fragmento(
            "catalogo_dtc_0142_1",
            "HTM-0142 — estrategia de diagnóstico",
            categoria="DTC",
            versiones=("V2.0",),
            vector=(0.4, 0.9165),
        ) | {"seccion": "HTM-0142"},
    ])

    resultados = retrieval.buscar_fragmentos("HTM-0142 código DTC catálogo", "V2.0", 5)

    assert resultados[0]["chunk_id"] == "catalogo_dtc_0142_1"
    assert resultados[0]["categoria"] == "DTC"
    assert resultados[0]["seccion"] == "HTM-0142"
    # La prioridad no modifica la similitud coseno usada para evaluar evidencia.
    assert resultados[0]["score"] == pytest.approx(0.4)
    assert any(r["chunk_id"] == "manual_general_1" for r in resultados)



def test_anade_nota_de_aire_acondicionado_fuera_de_alcance_al_contexto_r07(monkeypatch, vectores):
    nota = fragmento(
        "diccionario_aire_acondicionado_1",
        "El aire acondicionado no enfría: Fuera del alcance de este corpus; ThermoDrive no gestiona el circuito de A/C del habitáculo.",
        categoria="Dictionary",
        versiones=("V2.0",),
    )
    manual = fragmento(
        "manual_refrigerante_1",
        "El refrigerante ThermoGlyc HX-40 circula por tres circuitos térmicos.",
        categoria="Manual",
        versiones=("V2.0",),
    )
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [manual, nota])

    resultados = retrieval.anadir_notas_de_alcance(
        "¿Qué refrigerante usa el aire acondicionado del habitáculo?",
        [{
            "chunk_id": manual["chunk_id"],
            "texto": manual["texto"],
            "categoria": manual["categoria"],
            "score": 0.7,
            "ranking_score": 0.7,
            "versiones": manual["versiones"],
            "pagina": manual["pagina"],
            "seccion": manual["seccion"],
        }],
        "V2.0",
    )

    assert [r["chunk_id"] for r in resultados] == [
        "manual_refrigerante_1",
        "diccionario_aire_acondicionado_1",
    ]
    assert resultados[1]["categoria"] == "Dictionary"


def test_no_anade_notas_del_diccionario_a_consultas_sin_subsistema_ac(monkeypatch, vectores):
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: pytest.fail("no debe cargar glosario"))

    resultados = retrieval.anadir_notas_de_alcance("¿Qué caudal tiene CMP-02?", [], "V2.0")

    assert resultados == []


def test_edicion_sustituida_que_remite_a_la_vigente_hereda_su_version():
    from services.retrieval import _versiones_efectivas, _versiones_heredadas

    fragmentos = [
        {
            "chunk_id": "HTM240-PRC-003_Verificacion_v1.0_SUSTITUIDO.pdf_1",
            "texto": "El resto de pasos de esta versión obsoleta coincide sustancialmente con la versión vigente.",
            "versiones": ["V1.0"],
        },
        {"chunk_id": "HTM240-PRC-003_Verificacion.pdf_8", "texto": "Pasos 1. ...", "versiones": ["V1.1", "V2.0"]},
        {"chunk_id": "HTM240-PRC-011_Filtro.pdf_7", "texto": "Pasos 1. ...", "versiones": ["V1.1", "V2.0"]},
    ]
    heredadas = _versiones_heredadas(fragmentos)

    assert _versiones_efectivas(fragmentos[1], heredadas) == ["V1.0", "V1.1", "V2.0"]
    # Otro documento sin edición sustituida no cambia.
    assert _versiones_efectivas(fragmentos[2], heredadas) == ["V1.1", "V2.0"]
    # La propia edición sustituida conserva solo sus versiones.
    assert _versiones_efectivas(fragmentos[0], heredadas) == ["V1.0"]


def test_fragmento_heredado_lleva_una_nota_de_version(monkeypatch):
    import numpy as np
    from services import retrieval

    vector = np.ones(4, dtype=np.float32) / 2
    fragmentos = [
        {
            "chunk_id": "HTM240-PRC-003_v1.0_SUSTITUIDO.pdf_1", "categoria": "Manual",
            "texto": "El resto de pasos de esta versión obsoleta coincide sustancialmente con la versión vigente.",
            "versiones": ["V1.0"], "vector": vector, "pagina": 1, "seccion": None,
        },
        {
            "chunk_id": "HTM240-PRC-003_Verificacion.pdf_8", "categoria": "Manual",
            "texto": "Pasos 1. Verificar...", "versiones": ["V1.1", "V2.0"], "vector": vector,
            "pagina": 1, "seccion": "Pasos",
        },
    ]
    monkeypatch.setattr(retrieval, "cargar_fragmentos", lambda: [dict(f) for f in fragmentos])
    monkeypatch.setattr(retrieval, "embedding_normalizado", lambda _texto: vector)
    monkeypatch.setattr(retrieval, "settings", type("S", (), {
        "rag_hybrid_retrieval_enabled": False, "rag_component_anchor_enabled": False,
        "rag_combined_reranking_enabled": False, "rag_rrf_k": 60,
    })())

    resultados = {r["chunk_id"]: r for r in retrieval.buscar_fragmentos("bomba", "V1.0", 5)}

    assert "HTM240-PRC-003" in resultados["HTM240-PRC-003_Verificacion.pdf_8"]["nota_version"]
    assert resultados["HTM240-PRC-003_v1.0_SUSTITUIDO.pdf_1"]["nota_version"] is None
