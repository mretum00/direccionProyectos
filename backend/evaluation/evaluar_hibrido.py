"""Compara la recuperación semántica actual con un ranking híbrido BM25 + RRF.

Este script es SOLO de evaluación: no modifica retrieval.py, la BD ni el .env.
Ejecutar desde la raíz del repositorio:
    python backend/evaluation/evaluar_hibrido.py

El baseline usa el ranking semántico/ranking_score actual. El candidato fusiona
ese ranking con BM25 léxico mediante Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import retrieval  # noqa: E402

STOPWORDS = set("""
 a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
 durante e el ella ellas ellos en entre era erais eran eras eres es esa esas ese eso
 esos esta estaba estaban estado estamos están estar estas este esto estos fue fueron
 ha habia han hasta hay la las le les lo los mas más me mi mis mucha muchas mucho
 muchos muy no nos o os otra otras otro otros para pero poca pocas poco pocos por porque
 que quien quienes se sea sean ser si sin sobre son su sus te tiene tienen todo todos tu
 tus un una unas uno unos y ya cada cuanto deberia debería debe pueden puede permite

""".split())
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalizar(texto: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(ch) != "Mn"
    )


def tokenizar(texto: str) -> list[str]:
    return [
        token for token in TOKEN_RE.findall(normalizar(texto))
        if len(token) > 1 and token not in STOPWORDS
    ]


def documento_de(resultado: dict[str, Any]) -> str:
    return retrieval.documento_de(resultado["chunk_id"])


def calcular_bm25(
    consulta: str,
    resultados: list[dict[str, Any]],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """BM25 ligero sin dependencias externas; corpus = fragmentos aplicables."""
    if not resultados:
        return []

    tokenizados = [
        tokenizar(" ".join([
            str(r.get("seccion") or ""),
            str(r.get("texto") or ""),
            documento_de(r),
        ]))
        for r in resultados
    ]
    cantidades = [Counter(tokens) for tokens in tokenizados]
    longitudes = [len(tokens) for tokens in tokenizados]
    total = len(tokenizados)
    promedio = sum(longitudes) / total if total else 0.0
    if promedio == 0:
        return [0.0] * total

    df: Counter[str] = Counter()
    for tokens in tokenizados:
        df.update(set(tokens))

    terminos_consulta = Counter(tokenizar(consulta))
    puntuaciones: list[float] = []
    for frecuencia, longitud in zip(cantidades, longitudes):
        score = 0.0
        for termino, qf in terminos_consulta.items():
            tf = frecuencia.get(termino, 0)
            if not tf:
                continue
            documentos_con_termino = df[termino]
            idf = math.log(
                1.0 + (total - documentos_con_termino + 0.5)
                / (documentos_con_termino + 0.5)
            )
            normalizador = tf + k1 * (1.0 - b + b * longitud / promedio)
            score += idf * (tf * (k1 + 1.0) / normalizador) * min(qf, 2)
        puntuaciones.append(score)
    return puntuaciones


def ordenar_hibrido(
    consulta: str,
    resultados_semanticos: list[dict[str, Any]],
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Fusiona ranking semántico y BM25. No altera score ni ranking_score."""
    if not resultados_semanticos:
        return []

    bm25 = calcular_bm25(consulta, resultados_semanticos)
    orden_lexico = sorted(
        range(len(resultados_semanticos)),
        key=lambda i: (-bm25[i], i),
    )
    rango_lexico = {indice: posicion for posicion, indice in enumerate(orden_lexico, 1)}

    fusionados: list[dict[str, Any]] = []
    for rango_semantico, resultado in enumerate(resultados_semanticos, 1):
        rango_bm25 = rango_lexico[rango_semantico - 1]
        rrf = 1.0 / (rrf_k + rango_semantico) + 1.0 / (rrf_k + rango_bm25)
        copia = dict(resultado)
        copia["bm25_score"] = bm25[rango_semantico - 1]
        copia["semantic_rank"] = rango_semantico
        copia["bm25_rank"] = rango_bm25
        copia["rrf_score"] = rrf
        fusionados.append(copia)

    fusionados.sort(
        key=lambda r: (-r["rrf_score"], r["semantic_rank"], r["bm25_rank"])
    )
    return fusionados


def es_relevante(resultado: dict[str, Any], relevantes: list[dict[str, Any]]) -> tuple[bool, bool]:
    documento = documento_de(resultado)
    for objetivo in relevantes:
        if documento != objetivo["documento"]:
            continue
        return True, resultado.get("seccion") in objetivo.get("secciones", [])
    return False, False


def limitar_diversidad(
    resultados: list[dict[str, Any]], top_k: int, max_por_documento: int = 2
) -> list[dict[str, Any]]:
    seleccionados: list[dict[str, Any]] = []
    conteo: dict[str, int] = {}
    for resultado in resultados:
        documento = documento_de(resultado)
        if conteo.get(documento, 0) >= max_por_documento:
            continue
        seleccionados.append(resultado)
        conteo[documento] = conteo.get(documento, 0) + 1
        if len(seleccionados) >= top_k:
            break
    return seleccionados


def primer_hit(resultados: list[dict[str, Any]], relevantes: list[dict[str, Any]], seccion: bool) -> int | None:
    for posicion, resultado in enumerate(resultados, 1):
        doc_hit, section_hit = es_relevante(resultado, relevantes)
        if section_hit if seccion else doc_hit:
            return posicion
    return None


def metricas(casos: list[dict[str, Any]], rankings: dict[str, list[dict[str, Any]]], corte: int) -> dict[str, float]:
    n = len(casos)
    doc_hits = {k: 0 for k in (1, 3, 5, 10)}
    sec_hits = {k: 0 for k in (1, 3, 5, 10)}
    mrr = 0.0
    for caso in casos:
        resultados = rankings[caso["id"]]
        for k in doc_hits:
            if primer_hit(resultados[:k], caso["relevantes"], False) is not None:
                doc_hits[k] += 1
            if primer_hit(resultados[:k], caso["relevantes"], True) is not None:
                sec_hits[k] += 1
        rank = primer_hit(resultados[:corte], caso["relevantes"], True)
        if rank is not None:
            mrr += 1.0 / rank
    salida: dict[str, float] = {}
    for k in doc_hits:
        salida[f"documento@{k}"] = doc_hits[k] / n
        salida[f"seccion@{k}"] = sec_hits[k] / n
    salida[f"mrr_seccion@{corte}"] = mrr / n
    return salida


def formato_metricas(nombre: str, datos: dict[str, float]) -> None:
    print(f"\n{nombre}")
    for k in (1, 3, 5, 10):
        print(
            f"  Documento@{k}: {datos[f'documento@{k}']:.1%}"
            f" | Sección@{k}: {datos[f'seccion@{k}']:.1%}"
        )
    print(f"  MRR sección@10: {datos['mrr_seccion@10']:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparación experimental Semántico vs BM25+RRF")
    parser.add_argument(
        "--benchmark",
        default="backend/evaluation/benchmark_rag_v1_1.json",
        help="Ruta al benchmark (por defecto: benchmark_rag_v1_1.json)",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Tamaño final tras diversidad (por defecto 10)")
    parser.add_argument("--rrf-k", type=int, default=60, help="Constante RRF (por defecto 60)")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k debe ser mayor que cero")
    benchmark_path = (ROOT / args.benchmark).resolve()
    if not benchmark_path.exists():
        parser.error(f"No se encuentra el benchmark: {benchmark_path}")

    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    casos = data.get("casos", [])
    if not casos:
        parser.error("El benchmark no contiene una lista 'casos'")

    limite_original = retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO
    retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = 100_000
    try:
        print("=" * 88)
        print("EVALUACIÓN EXPERIMENTAL — SEMÁNTICO ACTUAL vs BM25 + RRF")
        print(f"Consultas: {len(casos)} | salida: top {args.top_k} | RRF k={args.rrf_k}")
        print("No modifica retrieval.py, configuración ni base de datos.")
        print("=" * 88)

        baseline: dict[str, list[dict[str, Any]]] = {}
        hibrido: dict[str, list[dict[str, Any]]] = {}

        for caso in casos:
            brutos = retrieval.buscar_fragmentos(
                caso["consulta"], caso["version"], top_k=100_000
            )
            # búsqueda_semántica ya está ordenada por la lógica de producción actual.
            baseline[caso["id"]] = limitar_diversidad(brutos, args.top_k)
            fusionados = ordenar_hibrido(caso["consulta"], brutos, args.rrf_k)
            hibrido[caso["id"]] = limitar_diversidad(fusionados, args.top_k)

        base_metrics = metricas(casos, baseline, 10)
        hybrid_metrics = metricas(casos, hibrido, 10)
        formato_metricas("BASELINE — RANKING SEMÁNTICO ACTUAL", base_metrics)
        formato_metricas("CANDIDATO — BM25 + RRF", hybrid_metrics)

        print("\nCOMPARACIÓN POR CONSULTA (primera posición de sección relevante)")
        print("ID | Semántico | Híbrido")
        print("-" * 88)
        for caso in casos:
            sem_rank = primer_hit(baseline[caso["id"]], caso["relevantes"], True)
            rrf_rank = primer_hit(hibrido[caso["id"]], caso["relevantes"], True)
            print(f"{caso['id']} | {sem_rank or 'NO TOP'} | {rrf_rank or 'NO TOP'}")

        print("\nDETALLE DE LAS CUATRO CONSULTAS AUDITADAS")
        ids_auditar = {
            "BOL-001-INTERVALO-BOMBA", "TES-05-ALTA-TENSION",
            "PRC-003-FLUJO-BAJO", "ESQ-ARQUITECTURA",
        }
        for caso in casos:
            if caso["id"] not in ids_auditar:
                continue
            print(f"\n{caso['id']}")
            for nombre, resultados in (("SEM", baseline[caso["id"]]), ("HYB", hibrido[caso["id"]])):
                print(f"  {nombre}:")
                for pos, r in enumerate(resultados[:5], 1):
                    doc_hit, sec_hit = es_relevante(r, caso["relevantes"])
                    marca = "OK" if sec_hit else ("DOC" if doc_hit else "  ")
                    print(
                        f"    {pos}. [{marca}] {documento_de(r)}"
                        f" | {r.get('seccion')}"
                        f" | cos={float(r.get('score', 0)):.3f}"
                        f" | bm25={float(r.get('bm25_score', 0)):.3f}"
                        f" | rrf={float(r.get('rrf_score', 0)):.5f}"
                    )
        print("\nNota: BM25+RRF es experimental. No lo copies a producción hasta comparar métricas y revisar regresiones.")
    finally:
        retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = limite_original
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
