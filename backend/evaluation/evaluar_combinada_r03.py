"""Compara la recuperación real con COMBINADA desactivada y activada.

Ejecutar desde la raíz del repositorio:
    py -3 backend/evaluation/evaluar_combinada_r03.py
    py -3 backend/evaluation/evaluar_combinada_r03.py --benchmark backend/evaluation/benchmark_rag_v2_1.json

El script llama a buscar_fragmentos() con el mismo benchmark y la misma BD,
primero con el flag desactivado y después activado. No llama al LLM/Groq,
no modifica archivos, no escribe en la BD y restaura la configuración original
al terminar.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import services.retrieval as retrieval  # noqa: E402
from db.repositories import RagChunkRepository  # noqa: E402
from services.ranking_operativo import codigos_componente  # noqa: E402
from experimento_reranking_r03 import (  # noqa: E402
    calcular_metricas,
    imprimir_metricas,
    validar_benchmark,
)

BENCHMARK_DEFAULT = Path(__file__).with_name("benchmark_rag_v2_1.json")
_PATRON_CMP_SECCION = re.compile(r"^CMP[-‐‑‒–—−]?(\d{2})$", re.IGNORECASE)


def codigos_en_resultados(resultados: list[dict[str, Any]]) -> set[str]:
    """Extrae CMP-XX de etiquetas de sección exactas del catálogo."""
    encontrados: set[str] = set()
    for resultado in resultados:
        seccion = str(resultado.get("seccion") or "").strip()
        coincidencia = _PATRON_CMP_SECCION.fullmatch(seccion)
        if coincidencia:
            encontrados.add(f"CMP-{coincidencia.group(1)}")
    return encontrados


def recuperar_todos_los_casos(
    casos: list[dict[str, Any]],
    flag_combinada: bool,
    top_k: int,
) -> tuple[dict[str, list[dict[str, Any]]], float]:
    """Ejecuta el recuperador de producción con el flag solicitado."""
    configuracion_original = retrieval.settings
    retrieval.settings = replace(
        configuracion_original,
        rag_combined_reranking_enabled=flag_combinada,
    )

    resultados_por_caso: dict[str, list[dict[str, Any]]] = {}
    tiempos: list[float] = []
    try:
        for indice, caso in enumerate(casos, start=1):
            inicio = time.perf_counter()
            resultados = retrieval.buscar_fragmentos(
                caso["consulta"],
                caso["version"],
                top_k=top_k,
            )
            tiempos.append(time.perf_counter() - inicio)
            resultados_por_caso[caso["id"]] = resultados
            print(
                f"  Recuperando {indice}/{len(casos)}: {caso['id']} "
                f"({len(resultados)} fragmentos)"
            )
    finally:
        retrieval.settings = configuracion_original

    tiempo_medio = sum(tiempos) / len(tiempos) if tiempos else 0.0
    return resultados_por_caso, tiempo_medio


def imprimir_comparacion(
    sin_combinada: dict[str, Any],
    con_combinada: dict[str, Any],
) -> None:
    """Muestra cambios absolutos entre los dos modos reales de recuperación."""
    total = sin_combinada["total"]

    def delta_texto(antes: float, despues: float, decimales: int = 1) -> str:
        signo = "+" if despues - antes >= 0 else ""
        return f"{signo}{despues - antes:.{decimales}f}"

    print("\n" + "=" * 88)
    print("DIFERENCIA: ACTIVAR COMBINADA - RECUPERACIÓN ACTUAL")
    print("=" * 88)
    for k in (1, 3, 5):
        antes = 100 * sin_combinada["documento"][k] / total if total else 0
        despues = 100 * con_combinada["documento"][k] / total if total else 0
        print(f"Documento@{k}: {delta_texto(antes, despues)} puntos porcentuales")
    for k in (1, 3, 5):
        antes = 100 * sin_combinada["seccion"][k] / total if total else 0
        despues = 100 * con_combinada["seccion"][k] / total if total else 0
        print(f"Sección@{k}:   {delta_texto(antes, despues)} puntos porcentuales")

    print(f"MRR: {delta_texto(sin_combinada['mrr'], con_combinada['mrr'], 3)}")
    print(
        "Cobertura estricta de secciones: "
        f"{sin_combinada['secciones_encontradas']}/"
        f"{sin_combinada['secciones_objetivo']} -> "
        f"{con_combinada['secciones_encontradas']}/"
        f"{con_combinada['secciones_objetivo']}"
    )
    print(
        "Consultas con todas las secciones objetivo: "
        f"{sin_combinada['casos_cobertura_completa']}/{total} -> "
        f"{con_combinada['casos_cobertura_completa']}/{total}"
    )
    print(
        "CMP explícitos cubiertos: "
        f"{sin_combinada['componentes_encontrados']}/"
        f"{sin_combinada['componentes_exigidos']} -> "
        f"{con_combinada['componentes_encontrados']}/"
        f"{con_combinada['componentes_exigidos']}"
    )
    print(
        "Consultas multi-CMP totalmente cubiertas: "
        f"{sin_combinada['consultas_multi_cmp_completas']}/"
        f"{sin_combinada['consultas_multi_cmp']} -> "
        f"{con_combinada['consultas_multi_cmp_completas']}/"
        f"{con_combinada['consultas_multi_cmp']}"
    )
    print(
        "Sin resultados: "
        f"{sin_combinada['sin_resultados']}/{total} -> "
        f"{con_combinada['sin_resultados']}/{total}"
    )
    print(
        "Fugas de versión: "
        f"{sin_combinada['fugas_version']} -> {con_combinada['fugas_version']}"
    )


def imprimir_detalle_multi_cmp(
    casos: list[dict[str, Any]],
    resultados_por_caso: dict[str, list[dict[str, Any]]],
    top_k: int,
) -> None:
    """Detalla si cada consulta que pide varios CMP recupera sus fichas."""
    print("\n" + "=" * 88)
    print("COMPROBACIÓN DE CONSULTAS MULTI-CMP CON COMBINADA ACTIVADA")
    print("=" * 88)
    cantidad = 0
    completas = 0
    for caso in casos:
        exigidos = codigos_componente(caso.get("consulta", ""))
        if len(exigidos) < 2:
            continue
        cantidad += 1
        resultados = resultados_por_caso.get(caso["id"], [])[:top_k]
        encontrados = codigos_en_resultados(resultados)
        cubiertos = exigidos.intersection(encontrados)
        correcto = exigidos.issubset(encontrados)
        completas += int(correcto)
        faltantes = sorted(exigidos - encontrados)
        print(
            f"{caso['id']}: {'COMPLETA' if correcto else 'INCOMPLETA'} | "
            f"exigidos={','.join(sorted(exigidos))} | "
            f"recuperados={','.join(sorted(encontrados)) or '(ninguno)'}"
        )
        if faltantes:
            print(f"  Faltan: {', '.join(faltantes)}")
    print(f"Resultado multi-CMP: {completas}/{cantidad} consultas completas")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evalúa la recuperación de producción con COMBINADA OFF y ON."
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=BENCHMARK_DEFAULT,
        help="JSON del benchmark (por defecto: benchmark_rag_v2_1.json).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de fragmentos evaluados (mínimo 5).",
    )
    args = parser.parse_args()

    if args.top_k < 5:
        parser.error("--top-k debe ser al menos 5 para calcular métricas hasta @5")
    if not args.benchmark.exists():
        parser.error(f"No se encuentra el benchmark: {args.benchmark}")

    import json

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    casos = benchmark.get("casos", [])
    if not casos:
        parser.error("El benchmark no contiene una lista 'casos'")

    validar_benchmark(casos)
    fragmentos_bd = RagChunkRepository().list_all()

    print("=" * 88)
    print("EVALUACIÓN DE RECUPERACIÓN REAL R03 — COMBINADA OFF vs ON")
    print("=" * 88)
    print(f"Benchmark: {args.benchmark} | consultas: {len(casos)} | top_k: {args.top_k}")
    print(f"Base de datos: {retrieval.settings.db_path}")
    print(f"Fragmentos en BD: {len(fragmentos_bd)}")
    print(f"BM25 + RRF: {retrieval.settings.rag_hybrid_retrieval_enabled}")
    print(f"Anclaje operativo: {retrieval.settings.rag_component_anchor_enabled}")
    print("Sin llamadas a Groq/LLM. No modifica archivos ni la base de datos.")

    print("\n--- 1/2: RECUPERACIÓN ACTUAL (COMBINADA DESACTIVADA) ---")
    resultados_off, tiempo_off = recuperar_todos_los_casos(
        casos, flag_combinada=False, top_k=args.top_k
    )
    metricas_off = calcular_metricas(casos, resultados_off, args.top_k)
    imprimir_metricas("PRODUCCIÓN ACTUAL — COMBINADA OFF", metricas_off)

    print("\n--- 2/2: RECUPERACIÓN CON COMBINADA ACTIVADA ---")
    resultados_on, tiempo_on = recuperar_todos_los_casos(
        casos, flag_combinada=True, top_k=args.top_k
    )
    metricas_on = calcular_metricas(casos, resultados_on, args.top_k)
    imprimir_metricas("PRODUCCIÓN — COMBINADA ON", metricas_on)

    imprimir_comparacion(metricas_off, metricas_on)
    imprimir_detalle_multi_cmp(casos, resultados_on, args.top_k)

    print("\n" + "=" * 88)
    print("TIEMPO MEDIO DE RECUPERACIÓN")
    print(f"COMBINADA OFF: {tiempo_off:.3f} s/consulta")
    print(f"COMBINADA ON:  {tiempo_on:.3f} s/consulta")
    print("Evaluación terminada. La configuración original del proceso se ha restaurado.")
    print("No se ha modificado ningún archivo ni la BD.")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
