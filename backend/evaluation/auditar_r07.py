"""Audita la recuperación y, opcionalmente, la suficiencia de las consultas R07.

Uso desde la raíz del proyecto:
    python backend/evaluation/auditar_r07.py
    python backend/evaluation/auditar_r07.py --top-k 5

Por defecto audita la similitud sin llamar a Groq. Con --comprobar-suficiencia,
ejecuta además la nueva evaluación R07 sobre los fragmentos recuperados (una
llamada de verificación por consulta), sin generar la respuesta final.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.retrieval import anadir_notas_de_alcance, buscar_fragmentos  # noqa: E402
from services.suficiencia_evidencia import evaluar_suficiencia_evidencia  # noqa: E402

BENCHMARK_DEFAULT = Path(__file__).with_name("benchmark_r06_r07_v1.json")
CONTROLES_POSITIVOS_DEFAULT = Path(__file__).with_name("benchmark_r07_controles_positivos.json")


def documento_de(chunk_id: str) -> str:
    return chunk_id.rsplit("_", 1)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita consultas sin respuesta documental para R07.")
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_DEFAULT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--comprobar-suficiencia",
        action="store_true",
        help="Ejecuta R07 con Groq para los 8 casos negativos y los controles positivos.",
    )
    parser.add_argument(
        "--pausa-segundos",
        type=float,
        default=10.0,
        help="Espera entre llamadas R07 para respetar límites TPM de Groq (0 para desactivar).",
    )
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k debe ser mayor que cero")
    if args.pausa_segundos < 0:
        parser.error("--pausa-segundos no puede ser negativo")

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    casos = [c for c in benchmark["casos"] if c.get("requisito") == "R07"]
    controles = json.loads(CONTROLES_POSITIVOS_DEFAULT.read_text(encoding="utf-8"))["casos"]
    threshold = float(settings.rag_evidence_min_score)

    abstenciones_automaticas = 0
    pasan_umbral = 0
    sin_resultados = 0
    llamadas_r07 = 0
    resumen_suficiencia = {"sufficient": 0, "partial": 0, "insufficient": 0, "unavailable": 0}

    def comprobar_suficiencia(consulta: str, resultados: list[dict], version: str) -> dict:
        nonlocal llamadas_r07
        if llamadas_r07 and args.pausa_segundos:
            time.sleep(args.pausa_segundos)
        llamadas_r07 += 1
        contexto_r07 = anadir_notas_de_alcance(consulta, resultados, version)
        cobertura = evaluar_suficiencia_evidencia(consulta, contexto_r07)
        resumen_suficiencia[cobertura["status"]] = resumen_suficiencia.get(cobertura["status"], 0) + 1
        return cobertura

    print("=" * 88)
    print("AUDITORÍA R07 — CONSULTAS SIN RESPUESTA DOCUMENTAL")
    print(
        f"Casos negativos: {len(casos)} | controles positivos: {len(controles)} | "
        f"top_k: {args.top_k} | umbral de evidencia: {threshold:.3f}"
    )
    print(
        f"Con llamadas a Groq para R07; pausa entre llamadas: {args.pausa_segundos:g} s; "
        "no se modifica la BD ni ningún archivo del proyecto."
        if args.comprobar_suficiencia
        else "Sin llamadas a Groq; no se modifica la BD ni ningún archivo del proyecto."
    )
    print("=" * 88)

    for index, caso in enumerate(casos, start=1):
        resultados = buscar_fragmentos(caso["consulta"], caso["version"], args.top_k)
        mejor_score = max((float(r.get("score", 0.0)) for r in resultados), default=0.0)
        if not resultados:
            sin_resultados += 1
        if mejor_score < threshold:
            estado = "ABSTENCIÓN AUTOMÁTICA PREVIA AL LLM"
            abstenciones_automaticas += 1
        else:
            estado = "SUPERA EL UMBRAL: R07 DEBE DECIDIR; NO ES PRUEBA DE RESPUESTA"
            pasan_umbral += 1

        print(f"\n{index:02d}. {caso['id']} [{caso['version']}]")
        print(f"    Pregunta: {caso['consulta']}")
        print(f"    Dato ausente: {caso['dato_no_documentado']}")
        print(f"    Mejor score semántico: {mejor_score:.3f} | umbral: {threshold:.3f}")
        print(f"    Resultado de la puerta por similitud: {estado}")
        if args.comprobar_suficiencia and mejor_score >= threshold and resultados:
            try:
                cobertura = comprobar_suficiencia(
                    caso["consulta"], resultados, caso["version"]
                )
                print(f"    Resultado R07: {cobertura['status'].upper()}")
                for item in cobertura["requested_items"]:
                    print(f"      - {item['item']}: {item['status']}")
                if cobertura["missing_information"]:
                    print("      No localizado: " + "; ".join(cobertura["missing_information"]))
            except Exception as exc:
                resumen_suficiencia["unavailable"] += 1
                print(f"    Resultado R07: NO DISPONIBLE ({type(exc).__name__})")
        for rank, resultado in enumerate(resultados[:3], start=1):
            print(
                f"    {rank}. {documento_de(resultado['chunk_id'])} | "
                f"{resultado.get('seccion')} | score={float(resultado.get('score', 0.0)):.3f}"
            )

    if args.comprobar_suficiencia:
        print("\n" + "-" * 88)
        print("CONTROLES POSITIVOS — LA DOCUMENTACIÓN SÍ CONTIENE EL DATO")
        for index, caso in enumerate(controles, start=1):
            resultados = buscar_fragmentos(caso["consulta"], caso["version"], args.top_k)
            mejor_score = max((float(r.get("score", 0.0)) for r in resultados), default=0.0)
            print(f"\nP{index:02d}. {caso['id']} [{caso['version']}]")
            print(f"    Pregunta: {caso['consulta']}")
            print(f"    Dato esperado: {caso['dato_esperado']}")
            if mejor_score < threshold or not resultados:
                print(f"    Resultado R07: NO EVALUADO (score {mejor_score:.3f} por debajo del umbral)")
                continue
            try:
                cobertura = comprobar_suficiencia(
                    caso["consulta"], resultados, caso["version"]
                )
                print(f"    Resultado R07: {cobertura['status'].upper()}")
                for item in cobertura["requested_items"]:
                    print(f"      - {item['item']}: {item['status']}")
                if cobertura["missing_information"]:
                    print("      No localizado: " + "; ".join(cobertura["missing_information"]))
            except Exception as exc:
                resumen_suficiencia["unavailable"] += 1
                print(f"    Resultado R07: NO DISPONIBLE ({type(exc).__name__})")

    print("\n" + "=" * 88)
    print("RESUMEN DE LA PUERTA DETERMINISTA")
    print(f"Abstención automática por score bajo: {abstenciones_automaticas}/{len(casos)}")
    print(f"Superan el umbral y pasan a la etapa LLM/R07: {pasan_umbral}/{len(casos)}")
    print(f"Sin resultados recuperados: {sin_resultados}/{len(casos)}")
    print("IMPORTANTE: superar el umbral no significa que la pregunta esté contestada.")
    if args.comprobar_suficiencia:
        print("R07 evalúa cobertura y valida localmente las citas; los controles positivos ayudan a detectar abstenciones excesivas.")
        print(
            "Resumen R07: "
            + ", ".join(f"{estado.upper()}={cantidad}" for estado, cantidad in resumen_suficiencia.items())
        )
    else:
        print("Esta auditoría mide solo la similitud, no la abstención final de la aplicación.")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
