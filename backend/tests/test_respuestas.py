"""Pruebas de la separación del cierre del LLM (pasos y fragmentos utilizados)."""

from services.respuestas import citar_fragmentos, extraer_referencias, fragmentos_utilizados, separar_cierre


def _fragmento(chunk_id, pagina=None):
    return {"chunk_id": chunk_id, "pagina": pagina}


FRAGMENTOS = [
    _fragmento("HTM240-MNT-001_Mantenimiento.pdf_3", pagina=4),
    _fragmento("HTM240-DTC-001_Codigos.pdf_7"),
    _fragmento("HTM240-BOL-006_Boletin.pdf_1"),
]


def test_separa_pasos_y_fragmentos_del_texto():
    texto = (
        "### RESUMEN\nRespuesta.\n\n### FUENTE\nHTM240-MNT-001\n\n"
        "### Pasos seguidos:\n1. Primer paso.\n2) Segundo paso.\n- Tercer paso.\n\n"
        "### **FRAGMENTOS UTILIZADOS**\nF1, f3"
    )

    contenido, pasos, numeros = separar_cierre(texto)

    assert contenido == "### RESUMEN\nRespuesta.\n\n### FUENTE\nHTM240-MNT-001"
    assert pasos == ["Primer paso.", "Segundo paso.", "Tercer paso."]
    assert numeros == [1, 3]


def test_ninguno_y_seccion_ausente_se_distinguen():
    assert separar_cierre("Texto\n### FRAGMENTOS UTILIZADOS\nNinguno")[2] == []
    assert separar_cierre("Texto sin cierre")[2] is None


def test_solo_se_quedan_los_fragmentos_indicados():
    usados = fragmentos_utilizados(FRAGMENTOS, [3, 1, 3, 9], "")

    assert [f["chunk_id"] for f in usados] == [
        "HTM240-MNT-001_Mantenimiento.pdf_3",
        "HTM240-BOL-006_Boletin.pdf_1",
    ]


def test_sin_seccion_se_usan_los_documentos_citados_en_el_texto():
    usados = fragmentos_utilizados(FRAGMENTOS, None, "Según HTM240‑BOL‑006, el intervalo es...")

    assert [f["chunk_id"] for f in usados] == ["HTM240-BOL-006_Boletin.pdf_1"]


def test_sin_seccion_ni_citas_no_hay_fuentes():
    assert fragmentos_utilizados(FRAGMENTOS, None, "Respuesta sin citas") == []


def test_cita_las_referencias_con_el_documento():
    assert citar_fragmentos("Consulté F1 y F2; F9 no existe.", FRAGMENTOS) == (
        "Consulté HTM240-MNT-001 · pág. 4 y HTM240-DTC-001; F9 no existe."
    )


def test_no_repite_el_documento_que_el_llm_escribe_junto_a_la_referencia():
    # Código detrás, nombre del fichero delante y referencias entre paréntesis.
    assert citar_fragmentos("Revisé F3 (BOL‑006).", FRAGMENTOS) == "Revisé HTM240-BOL-006."
    assert citar_fragmentos("Consulté HTM240-MNT-001_Mantenimiento.pdf (F1).", FRAGMENTOS) == (
        "Consulté HTM240-MNT-001 · pág. 4."
    )
    assert citar_fragmentos("El catálogo (F2, F3) lo confirma.", FRAGMENTOS) == (
        "El catálogo HTM240-DTC-001, HTM240-BOL-006 lo confirma."
    )
    # Si el documento escrito delante es otro, se conserva.
    assert citar_fragmentos("HTM240-SEG-001 F1", FRAGMENTOS) == "HTM240-SEG-001 HTM240-MNT-001 · pág. 4"


def test_extrae_las_referencias_de_un_paso_y_limpia_el_texto():
    assert extraer_referencias("Identifiqué el testigo TES‑01 (F1).", FRAGMENTOS) == (
        "Identifiqué el testigo TES-01.", ["HTM240-MNT-001 · pág. 4"],
    )
    # Documento escrito por el LLM + referencia: el código se queda en el texto, sin repetirse.
    assert extraer_referencias("Revisé la tabla de HTM240‑DTC‑001_Codigos.pdf F2 para la criticidad.", FRAGMENTOS) == (
        "Revisé la tabla de HTM240-DTC-001 para la criticidad.", ["HTM240-DTC-001"],
    )
    assert extraer_referencias("Lo confirma el boletín (HTM240‑BOL‑006, F3).", FRAGMENTOS) == (
        "Lo confirma el boletín (HTM240-BOL-006).", ["HTM240-BOL-006"],
    )


def test_ids_internos_y_referencias_en_medio_de_la_frase():
    # El LLM copia el id interno del fragmento: se trata como su referencia.
    assert extraer_referencias("Identifiqué el testigo TES-01 en HTM240-BOL-006_Boletin.pdf_1.", FRAGMENTOS) == (
        "Identifiqué el testigo TES-01.", ["HTM240-BOL-006"],
    )
    # En medio de la frase se deja el código para que se siga entendiendo.
    assert extraer_referencias("Consulté F2 para ver la criticidad.", FRAGMENTOS) == (
        "Consulté HTM240-DTC-001 para ver la criticidad.", ["HTM240-DTC-001"],
    )
    assert extraer_referencias("Dato vigente (F1 y F3).", FRAGMENTOS) == (
        "Dato vigente.", ["HTM240-MNT-001 · pág. 4", "HTM240-BOL-006"],
    )
