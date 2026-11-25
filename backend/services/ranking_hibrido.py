"""Ranking híbrido BM25 + Reciprocal Rank Fusion (RRF).

El módulo no modifica la puntuación semántica original. BM25 aporta una señal
léxica complementaria y RRF combina posiciones, no magnitudes de puntuación.
No requiere dependencias externas.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Any

RRF_K_DEFAULT = 60

_STOPWORDS = set("""
 a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
 durante e el ella ellas ellos en entre era erais eran eras eres es esa esas ese eso
 esos esta estaba estaban estado estamos están estar estas este esto estos fue fueron
 ha habia han hasta hay la las le les lo los mas más me mi mis mucha muchas mucho
 muchos muy no nos o os otra otras otro otros para pero poca pocas poco pocos por porque
 que quien quienes se sea sean ser si sin sobre son su sus te tiene tienen todo todos tu
 tus un una unas uno unos y ya cada cuanto deberia debería debe pueden puede permite
""".split())
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalizar(texto: str) -> str:
    """Pasa a minúsculas y elimina diacríticos para igualar términos españoles."""
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(caracter) != "Mn"
    )


def tokenizar(texto: str) -> list[str]:
    """Tokeniza texto, elimina palabras vacías y conserva códigos/números."""
    return [
        token
        for token in _TOKEN_RE.findall(normalizar(texto))
        if len(token) > 1 and token not in _STOPWORDS
    ]


def _documento_de(resultado: dict[str, Any]) -> str:
    chunk_id = str(resultado.get("chunk_id") or "")
    return chunk_id.rsplit("_", 1)[0]


def calcular_bm25(
    consulta: str,
    resultados: list[dict[str, Any]],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Calcula BM25 sobre los fragmentos candidatos aplicables a la versión.

    El campo sección y el nombre del documento se añaden al texto para mejorar
    la recuperación de títulos y referencias técnicas. Los candidatos sin
    coincidencias léxicas reciben puntuación cero.
    """
    if not resultados:
        return []
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requiere k1 > 0 y 0 <= b <= 1")

    documentos_tokenizados = [
        tokenizar(" ".join((
            str(resultado.get("seccion") or ""),
            str(resultado.get("texto") or ""),
            _documento_de(resultado),
        )))
        for resultado in resultados
    ]
    frecuencias = [Counter(tokens) for tokens in documentos_tokenizados]
    longitudes = [len(tokens) for tokens in documentos_tokenizados]
    total = len(documentos_tokenizados)
    longitud_media = sum(longitudes) / total if total else 0.0
    if longitud_media == 0:
        return [0.0] * total

    frecuencia_documental: Counter[str] = Counter()
    for tokens in documentos_tokenizados:
        frecuencia_documental.update(set(tokens))

    terminos_consulta = Counter(tokenizar(consulta))
    puntuaciones: list[float] = []
    for frecuencia, longitud in zip(frecuencias, longitudes):
        puntuacion = 0.0
        for termino, frecuencia_consulta in terminos_consulta.items():
            frecuencia_termino = frecuencia.get(termino, 0)
            if frecuencia_termino == 0:
                continue

            documentos_con_termino = frecuencia_documental[termino]
            idf = math.log(
                1.0
                + (total - documentos_con_termino + 0.5)
                / (documentos_con_termino + 0.5)
            )
            normalizador = frecuencia_termino + k1 * (
                1.0 - b + b * longitud / longitud_media
            )
            puntuacion += (
                idf
                * (frecuencia_termino * (k1 + 1.0) / normalizador)
                * min(frecuencia_consulta, 2)
            )
        puntuaciones.append(puntuacion)

    return puntuaciones


def ordenar_hibrido(
    consulta: str,
    resultados_semanticos: list[dict[str, Any]],
    rrf_k: int = RRF_K_DEFAULT,
) -> list[dict[str, Any]]:
    """Combina ranking semántico y BM25 con Reciprocal Rank Fusion.

    La lista recibida debe estar previamente ordenada por el ranking semántico
    de producción. Los fragmentos se copian: no se muta la lista original.
    `score` y `ranking_score` se conservan sin cambios.
    """
    if rrf_k < 1:
        raise ValueError("rrf_k debe ser un entero mayor que cero")
    if not resultados_semanticos:
        return []

    puntuaciones_bm25 = calcular_bm25(consulta, resultados_semanticos)
    orden_lexico = sorted(
        range(len(resultados_semanticos)),
        key=lambda indice: (-puntuaciones_bm25[indice], indice),
    )
    rango_lexico = {
        indice: posicion
        for posicion, indice in enumerate(orden_lexico, start=1)
    }

    fusionados: list[dict[str, Any]] = []
    for rango_semantico, resultado in enumerate(resultados_semanticos, start=1):
        indice = rango_semantico - 1
        rango_bm25 = rango_lexico[indice]
        rrf_score = (
            1.0 / (rrf_k + rango_semantico)
            + 1.0 / (rrf_k + rango_bm25)
        )
        copia = dict(resultado)
        copia["bm25_score"] = puntuaciones_bm25[indice]
        copia["semantic_rank"] = rango_semantico
        copia["bm25_rank"] = rango_bm25
        copia["rrf_score"] = rrf_score
        fusionados.append(copia)

    fusionados.sort(
        key=lambda resultado: (
            -float(resultado["rrf_score"]),
            int(resultado["semantic_rank"]),
            int(resultado["bm25_rank"]),
        )
    )
    return fusionados
