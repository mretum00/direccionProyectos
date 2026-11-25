"""Evalúa la recuperación semántica del RAG sin llamar a Groq ni modificar la BD.

Uso desde la raíz del proyecto:
    python backend/evaluation/evaluar_retrieval.py
    python backend/evaluation/evaluar_retrieval.py --top-k 10

El script emplea la misma función de recuperación y el mismo modelo de embeddings
que la aplicación. Los resultados se miden contra fuentes/secciones revisadas en
el corpus ThermoDrive incluido en el benchmark.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.retrieval import buscar_fragmentos  # noqa: E402
from db.repositories import RagChunkRepository  # noqa: E402

BENCHMARK_PATH = Path(__file__).with_name("benchmark_rag.json")


def documento_de(chunk_id: str) -> str:
    """Obtiene el identificador del documento quitando el sufijo del fragmento."""
    return chunk_id.rsplit("_", 1)[0]


def coincide_seccion(resultado: dict[str, Any], relevantes: list[dict[str, Any]]) -> bool:
    documento = documento_de(resultado["chunk_id"])
    seccion = resultado.get("seccion")

    for objetivo in relevantes:
        if documento != objetivo["documento"]:
            continue
        secciones = objetivo.get("secciones", [])
        if not secciones or seccion in secciones:
            return True
    return False


def coincide_documento(resultado: dict[str, Any], relevantes: list[dict[str, Any]]) -> bool:
    documento = documento_de(resultado["chunk_id"])
    return any(documento == objetivo["documento"] for objetivo in relevantes)


def validar_benchmark(casos: list[dict[str, Any]]) -> None:
    """Comprueba que los objetivos anotados existen en la BD antes de evaluar."""
    filas = RagChunkRepository().list_all()
    disponibles: dict[str, set[str]] = {}
    for fila in filas:
        doc = documento_de(fila.chunk_id)
        disponibles.setdefault(doc, set()).add(fila.section or "")

    errores: list[str] = []
    for caso in casos:
        if caso["version"] not in {"V1.0", "V1.1", "V2.0"}:
            errores.append(f"{caso['id']}: versión no válida ({caso['version']})")
        for objetivo in caso["relevantes"]:
            doc = objetivo["documento"]
            if doc not in disponibles:
                errores.append(f"{caso['id']}: no existe el documento objetivo {doc}")
                continue
            for seccion in objetivo.get("secciones", []):
                if seccion not in disponibles[doc]:
                    errores.append(
                        f"{caso['id']}: no existe la sección {seccion!r} en {doc}"
                    )
    if errores:
        raise ValueError("El benchmark contiene objetivos no encontrados:\n- " + "\n- ".join(errores))


def porcentaje(valor: int, total: int) -> str:
    return f"{(100 * valor / total):5.1f}% ({valor}/{total})" if total else "n/d"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa la recuperación del RAG ThermoDrive.")
    parser.add_argument("--top-k", type=int, default=5, help="Número de fragmentos por consulta (por defecto: 5).")
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_PATH, help="Ruta al JSON de preguntas de evaluación.")
    parser.add_argument("--output", type=Path, default=None, help="Guarda el detalle y las métricas en un JSON (opcional).")
    args = parser.parse_args()

    if args.top_k < 5:
        parser.error("--top-k debe ser al menos 5 porque el informe calcula métricas hasta @5")

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    casos = benchmark["casos"]
    validar_benchmark(casos)

    aciertos_seccion = {k: 0 for k in (1, 3, 5)}
    aciertos_documento = {k: 0 for k in (1, 3, 5)}
    suma_reciproca = 0.0
    fugas_version = 0
    sin_resultados = 0
    tiempos: list[float] = []
    filas_resultados: list[dict[str, Any]] = []

    print("=" * 78)
    print("EVALUACIÓN DE RECUPERACIÓN RAG — THERMODRIVE HTM-240")
    print(f"Consultas: {len(casos)} | top_k: {args.top_k} | Sin llamadas a Groq")
    print("=" * 78)

    for indice, caso in enumerate(casos, start=1):
        inicio = time.perf_counter()
        resultados = buscar_fragmentos(caso["consulta"], caso["version"], args.top_k)
        duracion = time.perf_counter() - inicio
        tiempos.append(duracion)

        if not resultados:
            sin_resultados += 1

        rango_seccion = next(
            (i for i, r in enumerate(resultados, start=1) if coincide_seccion(r, caso["relevantes"])),
            None,
        )
        rango_documento = next(
            (i for i, r in enumerate(resultados, start=1) if coincide_documento(r, caso["relevantes"])),
            None,
        )

        if rango_seccion is not None:
            suma_reciproca += 1.0 / rango_seccion
        for k in (1, 3, 5):
            if rango_seccion is not None and rango_seccion <= k:
                aciertos_seccion[k] += 1
            if rango_documento is not None and rango_documento <= k:
                aciertos_documento[k] += 1

        resultados_salida = []
        print(f"\n{indice:02d}. {caso['id']} [{caso['version']}]")
        print(f"    Consulta: {caso['consulta']}")
        print(
            "    Primer resultado válido: "
            + (f"posición {rango_seccion}" if rango_seccion is not None else "NO ENCONTRADO en top_k")
        )
        for posicion, resultado in enumerate(resultados, start=1):
            versiones = resultado.get("versiones") or []
            if caso["version"] not in versiones:
                fugas_version += 1
            doc = documento_de(resultado["chunk_id"])
            exacto = coincide_seccion(resultado, caso["relevantes"])
            marca = "OK" if exacto else "  "
            print(
                f"    {posicion}. [{marca}] {doc} | pág. {resultado.get('pagina')} | "
                f"{resultado.get('seccion')} | score={float(resultado['score']):.3f} | "
                f"ranking={float(resultado['ranking_score']):.3f}"
            )
            resultados_salida.append({
                "posicion": posicion,
                "chunk_id": resultado["chunk_id"],
                "documento": doc,
                "pagina": resultado.get("pagina"),
                "seccion": resultado.get("seccion"),
                "score": float(resultado["score"]),
                "ranking_score": float(resultado["ranking_score"]),
                "versiones": versiones,
                "coincide_seccion_esperada": exacto,
            })

        filas_resultados.append({
            "id": caso["id"],
            "version": caso["version"],
            "consulta": caso["consulta"],
            "rango_seccion": rango_seccion,
            "rango_documento": rango_documento,
            "tiempo_segundos": round(duracion, 4),
            "resultados": resultados_salida,
        })

    total = len(casos)
    print("\n" + "=" * 78)
    print("RESUMEN")
    for k in (1, 3, 5):
        print(f"Hit de documento@{k}: {porcentaje(aciertos_documento[k], total)}")
    for k in (1, 3, 5):
        print(f"Hit de sección@{k}:   {porcentaje(aciertos_seccion[k], total)}")
    print(f"MRR de sección@{args.top_k}: {suma_reciproca / total:.3f}" if total else "MRR: n/d")
    print(f"Consultas sin resultados: {sin_resultados}/{total}")
    print(f"Resultados de versión incorrecta: {fugas_version}")
    print(f"Tiempo medio por consulta: {(sum(tiempos) / total):.3f} s" if total else "Tiempo medio: n/d")
    print("=" * 78)

    salida = {
        "benchmark": benchmark.get("nombre"),
        "total_consultas": total,
        "top_k": args.top_k,
        "metricas": {
            "hit_documento": {str(k): aciertos_documento[k] / total if total else None for k in (1, 3, 5)},
            "hit_seccion": {str(k): aciertos_seccion[k] / total if total else None for k in (1, 3, 5)},
            "mrr_seccion": suma_reciproca / total if total else None,
            "consultas_sin_resultados": sin_resultados,
            "resultados_version_incorrecta": fugas_version,
            "tiempo_medio_segundos": sum(tiempos) / total if total else None,
        },
        "casos": filas_resultados,
    }

    # Se guarda un resultado JSON solo si se solicita explícitamente.
    # Por defecto el script no escribe ni modifica ningún archivo del proyecto.
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Resultado JSON guardado en: {args.output}")

    return 0


if __name__ == "__main__":
    # --output se declara aquí de forma explícita para que sea opcional.
    # argparse permite que los resultados queden solo en consola por defecto.
    sys.exit(main())
