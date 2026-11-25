"""Normalización de guiones, comillas y espacios del modelo frente a los documentos."""

from services.suficiencia_evidencia import evaluar_suficiencia_evidencia
from services.texto import limpiar_salida_llm, normalizar_cita


def test_guion_no_separable_del_modelo_coincide_con_el_guion_del_documento():
    assert normalizar_cita("Bomba CMP‑02 «activa»") == normalizar_cita('bomba CMP-02 "activa"')


def test_limpiar_salida_llm_respeta_las_rayas_de_la_prosa():
    assert limpiar_salida_llm("CMP‑02 — bomba al 100\u202f%") == "CMP-02 — bomba al 100 %"


def test_r07_acepta_una_cita_con_guion_tipografico():
    fragmentos = [{"chunk_id": "PRC-003_8", "texto": "3. Forzar la activación de la bomba CMP-02 al 100%."}]
    salida = (
        '{"items": [{"item": "pasos", "status": "supported", "source_refs": ["F1"], '
        '"evidence_quote": "Forzar la activación de la bomba CMP\u201102 al 100%"}]}'
    )
    resultado = evaluar_suficiencia_evidencia("¿Cómo compruebo CMP-02?", fragmentos, generador=lambda _p: salida)
    assert resultado["status"] == "sufficient"


def test_r07_acepta_una_cita_entre_comillas():
    fragmentos = [{"chunk_id": "PRC-003_8", "texto": "Pasos 1. ... 3. Forzar la activación de la bomba CMP-02 al 100% desde el menú."}]
    salida = (
        '{"items": [{"item": "pasos", "status": "supported", "source_refs": ["F1"], '
        '"evidence_quote": "\\"Forzar la activación de la bomba CMP-02 al 100% desde el menú.\\""}]}'
    )
    resultado = evaluar_suficiencia_evidencia("¿Cómo compruebo CMP-02?", fragmentos, generador=lambda _p: salida)
    assert resultado["status"] == "sufficient"
    assert not resultado["requested_items"][0]["evidence_excerpt"].startswith('"')


def test_cita_abreviada_con_puntos_suspensivos_debe_respetar_el_orden():
    from services.texto import cita_en_texto

    texto = "2. Consultar el caudal instantáneo reportado por el sensor CMP-18 con la bomba en reposo (debe ser 0 l/min)."
    assert cita_en_texto("Consultar el caudal instantáneo … (debe ser 0 l/min)", texto)
    assert not cita_en_texto("(debe ser 0 l/min) ... Consultar el caudal", texto)
    assert not cita_en_texto("... 0 ...", texto)
