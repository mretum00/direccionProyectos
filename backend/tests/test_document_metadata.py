"""Pruebas unitarias de extracción de metadatos de secciones y páginas."""

from db.database_generator import (
    Documento,
    construir_texto,
    detectar_apartado,
    pagina_de,
    procesar_diccionario,
    procesar_documento_tecnico,
)


def crear_documento(tipo, categoria, paginas):
    texto, inicios_pagina, apartados = construir_texto(paginas, tipo)
    return Documento(
        archivo=f"HTM240-{tipo or 'MAN'}-001_documento.pdf",
        codigo=f"HTM240-{tipo or 'MAN'}-001",
        tipo=tipo,
        categoria=categoria,
        sustituido=False,
        versiones=["V1.0", "V1.1", "V2.0"],
        lineas=[linea for pagina in paginas for linea in pagina],
        texto=texto,
        inicios_pagina=inicios_pagina,
        apartados=apartados,
    )


def test_detecta_encabezados_no_numerados_de_procedimientos():
    assert detectar_apartado("Objetivo", "PRC") == ("Objetivo", None)
    assert detectar_apartado("Equipos de protección individual", "PRC") == (
        "Equipos de protección individual",
        None,
    )
    assert detectar_apartado("Pasos", "PRC") == ("Pasos", None)


def test_detecta_seccion_de_contenido_en_boletines():
    assert detectar_apartado("Contenido", "BOL") == ("Contenido", None)


def test_asigna_intro_y_secciones_a_fragmentos_de_procedimiento():
    paginas = [[
        "HTM240-PRC-001 — Inspección del nivel de refrigerante. Versión 1.0 y estado vigente.",
        "Objetivo",
        "Verificar que el nivel de refrigerante se encuentra dentro del rango MIN-MAX establecido.",
        "Aplicabilidad",
        "El procedimiento es aplicable a todas las versiones V1.0, V1.1 y V2.0 del sistema.",
    ]]
    documento = crear_documento("PRC", "Manual", paginas)

    fragmentos = list(procesar_documento_tecnico(documento, chunk_size=1200, overlap=100))

    assert [fragmento["seccion"] for fragmento in fragmentos] == [
        "Introducción",
        "Objetivo",
        "Aplicabilidad",
    ]


def test_diccionario_conserva_termino_y_pagina_del_pdf():
    paginas = [
        [
            "HTM240-DIC-001 — Diccionario técnico",
            "• Se calienta: El motor o la batería superan su temperatura normal de funcionamiento.",
        ],
        [
            "• Sube la aguja: Expresión coloquial para el aumento de temperatura mostrado en el cuadro.",
        ],
    ]
    documento = crear_documento("DIC", "Dictionary", paginas)

    fragmentos = list(procesar_diccionario(documento))

    assert len(fragmentos) == 2
    assert fragmentos[0]["seccion"] == "Se calienta"
    assert fragmentos[1]["seccion"] == "Sube la aguja"
    assert pagina_de(fragmentos[0]["inicio"], documento.inicios_pagina) == 1
    assert pagina_de(fragmentos[1]["inicio"], documento.inicios_pagina) == 2
