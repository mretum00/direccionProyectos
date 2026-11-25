"""Reranking combinado R03 para la recuperación de ThermoDrive.

Combina la prioridad de fichas de catálogo CMP explícitas con el reranking
por intención e intercalado. No modifica score, ranking_score ni rrf_score.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .ranking_operativo import codigos_componente, normalizar

_PATRON_CODIGO_HTM = re.compile(
    r"(?<![A-Z0-9])HTM[-‐-‒–—−]?\d{4}(?!\d)",
    re.IGNORECASE,
)
_PATRON_CODIGO_CMP_SECCION = re.compile(
    r"^CMP[-‐-‒–—−]?(\d{2})$",
    re.IGNORECASE,
)
_PATRON_ESPECIFICACION_TECNICA = re.compile(
    r"\b(caudal|caudales|corriente|consumo|presion|temperatura|tension|"
    r"voltaje|potencia|capacidad|rango|rangos|nominal|nominales|"
    r"amperaje|resistencia|frecuencia|velocidad|dimension|dimensiones|"
    r"peso|par de apriete|vida util)\b"
)
_PATRON_ACCION_PROCEDIMENTAL = re.compile(
    r"\b(como|de que manera|pasos|procedimiento|prueba|comprobar|comprueba|"
    r"verificacion|verificar|verifica|realizar|realiza|ejecutar|ejecuta|"
    r"inspeccionar|inspeccion|sustituir|registrar|confirmar|medir|mide|"
    r"probar|revisar|ajustar|regular|purgar|instalar)\b"
)


def documento_de(chunk_id: str) -> str:
    """Obtiene el PDF de origen a partir del identificador de un fragmento."""
    return str(chunk_id or "").rsplit("_", 1)[0]


def normalizar_seccion(seccion: Any) -> str:
    """Normaliza etiquetas de sección sin tildes ni espacios sobrantes."""
    return normalizar(str(seccion or "")).strip()


def es_dtc_exacto(consulta: str) -> bool:
    """Detecta consultas por código HTM y evita alterar su ranking prioritario."""
    return bool(_PATRON_CODIGO_HTM.search(consulta or ""))


def extraer_secciones_preferidas(consulta: str) -> list[str]:
    """Detecta secciones que pueden responder a la intención de la consulta."""
    consulta_normalizada = normalizar(consulta)
    secciones: list[str] = []

    if re.search(
        r"\b(como|pasos|procedimiento|prueba|comprobar|comprueba|"
        r"verificacion|verificar|realizar|realiza|ejecutar|ejecuta|"
        r"inspeccionar|inspeccion|sustituir|registrar|confirmar)\b",
        consulta_normalizada,
    ):
        secciones.append("Pasos")

    if re.search(
        r"\b(valor|valores|caudal|caudales|corriente|consumo|presion|"
        r"temperatura|tolerancia|caida|rango|rangos|medida|medidas|"
        r"medicion|mediciones|nominal|nominales)\b",
        consulta_normalizada,
    ):
        secciones.append("Valores esperados")

    if re.search(
        r"\b(aceptacion|aceptable|aceptar|conforme|conformidad|"
        r"condicion|condiciones|criterio|criterios|cumple|cumplir)\b",
        consulta_normalizada,
    ):
        secciones.append("Criterios de aceptación")

    return secciones


def es_consulta_especificacion_un_cmp(consulta: str) -> bool:
    """Detecta preguntas de atributos técnicos, no de ejecución de procedimientos.

    Para un CMP explícito y único, una consulta como "¿Qué caudal nominal tiene
    CMP-02?" debe priorizar la ficha exacta del catálogo. Las preguntas del tipo
    "¿Cómo comprobar CMP-02?" siguen usando el reranking procedimental.
    """
    texto = normalizar(consulta)
    if _PATRON_ACCION_PROCEDIMENTAL.search(texto):
        return False
    return bool(_PATRON_ESPECIFICACION_TECNICA.search(texto))


def _ficha_exacta_componente(
    ranking: list[dict[str, Any]],
    componente: str,
) -> dict[str, Any] | None:
    """Busca el mejor fragmento cuya sección identifica exactamente el CMP."""
    numero = componente.split("-")[-1]
    for resultado in ranking:
        seccion = str(resultado.get("seccion") or "").strip()
        coincidencia = _PATRON_CODIGO_CMP_SECCION.fullmatch(seccion)
        if coincidencia and coincidencia.group(1) == numero:
            if resultado.get("chunk_id"):
                return resultado
    return None


def _seleccionar_con_fichas_prioritarias(
    consulta: str,
    ranking: list[dict[str, Any]],
    fichas_prioritarias: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Coloca las fichas exactas primero y completa respetando límites por PDF."""
    if top_k <= 0 or not ranking:
        return []

    fichas = []
    ids_fichas: set[str] = set()
    for ficha in fichas_prioritarias:
        chunk_id = str(ficha.get("chunk_id") or "")
        if chunk_id and chunk_id not in ids_fichas:
            fichas.append(ficha)
            ids_fichas.add(chunk_id)

    seleccionados = fichas[:top_k]
    if len(seleccionados) >= top_k:
        return seleccionados

    ranking_restante = [
        resultado for resultado in ranking
        if str(resultado.get("chunk_id") or "") not in ids_fichas
    ]
    plazas_restantes = top_k - len(seleccionados)
    complemento = (
        seleccionar_intencion_intercalada(consulta, ranking_restante, plazas_restantes)
        if ranking_restante else []
    )

    cantidades_por_documento: dict[str, int] = defaultdict(int)
    for resultado in seleccionados:
        cantidades_por_documento[documento_de(resultado.get("chunk_id", ""))] += 1

    documento_principal = documento_de(ranking[0].get("chunk_id", ""))
    limite_principal = 3 if len(extraer_secciones_preferidas(consulta)) >= 3 else 2
    ids_seleccionados = {
        str(resultado.get("chunk_id") or "") for resultado in seleccionados
    }

    for grupo in (complemento, ranking_restante):
        for resultado in grupo:
            chunk_id = str(resultado.get("chunk_id") or "")
            if not chunk_id or chunk_id in ids_seleccionados:
                continue
            documento = documento_de(chunk_id)
            limite = limite_principal if documento == documento_principal else 2
            if cantidades_por_documento[documento] >= limite:
                continue
            seleccionados.append(resultado)
            ids_seleccionados.add(chunk_id)
            cantidades_por_documento[documento] += 1
            if len(seleccionados) >= top_k:
                return seleccionados

    return seleccionados


def _limitar_por_documento(
    resultados: list[dict[str, Any]],
    top_k: int,
    limite: int = 2,
) -> list[dict[str, Any]]:
    """Limita fragmentos por PDF, conservando el orden recibido."""
    if top_k <= 0:
        return []

    seleccionados: list[dict[str, Any]] = []
    cantidades: dict[str, int] = defaultdict(int)
    for resultado in resultados:
        documento = documento_de(resultado.get("chunk_id", ""))
        if cantidades[documento] >= limite:
            continue
        seleccionados.append(resultado)
        cantidades[documento] += 1
        if len(seleccionados) >= top_k:
            break
    return seleccionados


def seleccionar_baseline(
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Aplica el límite habitual de dos fragmentos por documento."""
    return _limitar_por_documento(ranking, top_k, limite=2)


def seleccionar_intencion_intercalada(
    consulta: str,
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Prioriza secciones pertinentes del documento principal e intercala fuentes.

    Orden: primera sección preferida del documento principal; primer resultado
    de hasta dos documentos distintos; otras secciones preferidas del principal;
    y finalmente el resto del ranking original.
    """
    if not ranking or es_dtc_exacto(consulta):
        return seleccionar_baseline(ranking, top_k)

    secciones_preferidas = extraer_secciones_preferidas(consulta)
    if not secciones_preferidas:
        return seleccionar_baseline(ranking, top_k)

    documento_principal = documento_de(ranking[0].get("chunk_id", ""))
    if not documento_principal:
        return seleccionar_baseline(ranking, top_k)

    candidatos_preferidos: list[dict[str, Any]] = []
    for seccion_preferida in secciones_preferidas:
        seccion_normalizada = normalizar_seccion(seccion_preferida)
        for resultado in ranking:
            if (
                documento_de(resultado.get("chunk_id", "")) == documento_principal
                and normalizar_seccion(resultado.get("seccion")) == seccion_normalizada
            ):
                candidatos_preferidos.append(resultado)
                break

    if not candidatos_preferidos:
        return seleccionar_baseline(ranking, top_k)

    candidatos_otros_documentos: list[dict[str, Any]] = []
    documentos_ya_seleccionados: set[str] = set()
    for resultado in ranking:
        documento = documento_de(resultado.get("chunk_id", ""))
        if (
            documento
            and documento != documento_principal
            and documento not in documentos_ya_seleccionados
        ):
            candidatos_otros_documentos.append(resultado)
            documentos_ya_seleccionados.add(documento)
            if len(candidatos_otros_documentos) >= 2:
                break

    ordenados: list[dict[str, Any]] = []
    ids_anadidos: set[str] = set()

    def anadir(resultado: dict[str, Any]) -> None:
        chunk_id = resultado.get("chunk_id")
        if chunk_id not in ids_anadidos:
            ordenados.append(resultado)
            ids_anadidos.add(chunk_id)

    anadir(candidatos_preferidos[0])
    for resultado in candidatos_otros_documentos:
        anadir(resultado)
    for resultado in candidatos_preferidos[1:]:
        anadir(resultado)
    for resultado in ranking:
        anadir(resultado)

    resultados_finales: list[dict[str, Any]] = []
    contador_por_documento: dict[str, int] = defaultdict(int)
    limite_principal = 3 if len(secciones_preferidas) >= 3 else 2

    for resultado in ordenados:
        documento = documento_de(resultado.get("chunk_id", ""))
        limite = limite_principal if documento == documento_principal else 2
        if contador_por_documento[documento] >= limite:
            continue
        resultados_finales.append(resultado)
        contador_por_documento[documento] += 1
        if len(resultados_finales) >= top_k:
            break

    return resultados_finales


def seleccionar_combinada(
    consulta: str,
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Combina fichas CMP exactas y selección intercalada por intención.

    Para consultas de especificación con un solo CMP, prioriza su ficha exacta
    de catálogo. Para consultas con varios CMP, prioriza una ficha exacta por
    cada código y completa los puestos con la selección intercalada. Las fichas
    CMP exactas se conservan aunque varias pertenezcan al mismo PDF. El resto
    respeta un máximo de dos fragmentos por documento (tres para el documento
    principal si se detectan tres tipos de sección preferidos).

    Las consultas que contienen un código HTM mantienen el baseline para no
    interferir con la prioridad absoluta de la ficha DTC exacta.
    """
    if not ranking or es_dtc_exacto(consulta):
        return seleccionar_baseline(ranking, top_k)

    componentes = sorted(codigos_componente(consulta))
    if len(componentes) == 1:
        # En preguntas de especificaciones de un único CMP, la ficha exacta del
        # catálogo debe preceder a fragmentos procedimentales que repiten el valor
        # pero no identifican el componente. Las consultas operativas mantienen
        # el intercalado anterior.
        if es_consulta_especificacion_un_cmp(consulta):
            ficha = _ficha_exacta_componente(ranking, componentes[0])
            if ficha is not None:
                return _seleccionar_con_fichas_prioritarias(
                    consulta, ranking, [ficha], top_k
                )
        return seleccionar_intencion_intercalada(consulta, ranking, top_k)
    if not componentes:
        return seleccionar_intencion_intercalada(consulta, ranking, top_k)

    fichas_componentes: list[dict[str, Any]] = []
    ids_componentes: set[str] = set()
    for componente in componentes:
        numero = componente.split("-")[-1]
        for resultado in ranking:
            seccion = str(resultado.get("seccion") or "").strip()
            coincidencia = _PATRON_CODIGO_CMP_SECCION.fullmatch(seccion)
            if coincidencia and coincidencia.group(1) == numero:
                chunk_id = str(resultado.get("chunk_id") or "")
                if chunk_id and chunk_id not in ids_componentes:
                    fichas_componentes.append(resultado)
                    ids_componentes.add(chunk_id)
                break

    if not fichas_componentes:
        return seleccionar_intencion_intercalada(consulta, ranking, top_k)

    ranking_restante = [
        resultado
        for resultado in ranking
        if str(resultado.get("chunk_id") or "") not in ids_componentes
    ]
    plazas_restantes = max(0, top_k - len(fichas_componentes))
    complemento = (
        seleccionar_intencion_intercalada(consulta, ranking_restante, plazas_restantes)
        if plazas_restantes and ranking_restante
        else []
    )

    seleccionados = list(fichas_componentes)
    ids_seleccionados = set(ids_componentes)
    cantidades_por_documento: dict[str, int] = defaultdict(int)
    for resultado in fichas_componentes:
        cantidades_por_documento[documento_de(resultado.get("chunk_id", ""))] += 1

    documento_principal = documento_de(ranking[0].get("chunk_id", ""))
    limite_principal = 3 if len(extraer_secciones_preferidas(consulta)) >= 3 else 2

    for resultado in complemento:
        chunk_id = str(resultado.get("chunk_id") or "")
        if not chunk_id or chunk_id in ids_seleccionados:
            continue
        documento = documento_de(chunk_id)
        limite = limite_principal if documento == documento_principal else 2
        if cantidades_por_documento[documento] >= limite:
            continue
        seleccionados.append(resultado)
        ids_seleccionados.add(chunk_id)
        cantidades_por_documento[documento] += 1
        if len(seleccionados) >= top_k:
            break

    if len(seleccionados) < top_k:
        for resultado in ranking_restante:
            chunk_id = str(resultado.get("chunk_id") or "")
            if not chunk_id or chunk_id in ids_seleccionados:
                continue
            documento = documento_de(chunk_id)
            limite = limite_principal if documento == documento_principal else 2
            if cantidades_por_documento[documento] >= limite:
                continue
            seleccionados.append(resultado)
            ids_seleccionados.add(chunk_id)
            cantidades_por_documento[documento] += 1
            if len(seleccionados) >= top_k:
                break

    return seleccionados[:top_k]
