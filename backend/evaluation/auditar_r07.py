"""Audita la recuperación y la suficiencia documental de las consultas R07.

Uso desde la raíz del proyecto:
    py -3 backend/evaluation/auditar_r07.py
    py -3 backend/evaluation/auditar_r07.py --comprobar-suficiencia
    py -3 backend/evaluation/auditar_r07.py --comprobar-suficiencia --pausa-segundos 0

Sin --comprobar-suficiencia solo se audita recuperación (sin Groq).
Con esa opción se evalúa cobertura con Groq y se compara cada resultado con
el estado declarado en los benchmarks. El proceso devuelve código 1 si hay
algún fallo de evaluación.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.retrieval import anadir_notas_de_alcance, buscar_fragmentos  # noqa: E402
from services.suficiencia_evidencia import evaluar_suficiencia_evidencia  # noqa: E402

BENCHMARK_DEFAULT = Path(__file__).with_name("benchmark_r06_r07_v1_1.json")
CONTROLES_DEFAULT = Path(__file__).with_name("benchmark_r07_controles_positivos.json")
ESTADOS_VALIDOS = {"sufficient", "partial", "insufficient"}


def documento_de(chunk_id: str) -> str:
    return chunk_id.rsplit("_", 1)[0]


def normalizar(texto: str) -> str:
    """Normaliza mayúsculas, espacios y acentos para comparar nombres de elementos."""
    texto = unicodedata.normalize("NFKD", str(texto)).casefold()
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split())


def validar_cobertura(caso: dict, cobertura: dict) -> list[str]:
    """Compara el resultado global y, si se declaran, los estados de cada elemento."""
    esperado = str(caso.get("estado_suficiencia_esperado", "")).lower()
    obtenido = str(cobertura.get("status", "unavailable")).lower()
    errores: list[str] = []

    if esperado not in ESTADOS_VALIDOS:
        return [f"estado esperado no válido: {esperado or '(vacío)'}"]

    if obtenido != esperado:
        errores.append(f"estado global esperado {esperado.upper()}, obtenido {obtenido.upper()}")

    elementos = cobertura.get("requested_items", [])
    if not isinstance(elementos, list):
        elementos = []
    estados = [
        str(item.get("status", "uncertain")).lower()
        for item in elementos
        if isinstance(item, dict)
    ]

    # El estado global debe ser coherente con la cobertura de sus elementos.
    if esperado == "sufficient" and (not estados or any(e != "supported" for e in estados)):
        errores.append("SUFFICIENT requiere que todos los elementos estén supported")
    elif esperado == "insufficient" and any(e == "supported" for e in estados):
        errores.append("INSUFFICIENT no debe contener elementos supported")
    elif esperado == "partial":
        if not any(e == "supported" for e in estados):
            errores.append("PARTIAL requiere al menos un elemento supported")
        if not any(e != "supported" for e in estados):
            errores.append("PARTIAL requiere al menos un elemento no respaldado")

    # En el control parcial comprobamos además cada dato concreto solicitado.
    for esperado_item in caso.get("elementos_esperados", []):
        termino = normalizar(esperado_item.get("contiene", ""))
        estado_item = str(esperado_item.get("estado", "")).lower()
        encontrados = [
            item for item in elementos
            if isinstance(item, dict)
            and termino
            and termino in normalizar(item.get("item", ""))
        ]
        if not encontrados:
            errores.append(f"no se encontró el elemento esperado: {esperado_item.get('contiene')}")
        elif not any(str(item.get("status", "")).lower() == estado_item for item in encontrados):
            estados_encontrados = ", ".join(
                str(item.get("status", "uncertain")) for item in encontrados
            )
            errores.append(
                f"el elemento '{esperado_item.get('contiene')}' debía ser {estado_item}, "
                f"pero se obtuvo {estados_encontrados}"
            )

    return errores


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audita recuperación y cobertura documental de las consultas R07."
    )
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_DEFAULT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--comprobar-suficiencia",
        action="store_true",
        help="Ejecuta R07 con Groq y valida automáticamente los estados esperados.",
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
    casos_negativos = [
        caso for caso in benchmark["casos"] if caso.get("requisito") == "R07"
    ]
    controles = json.loads(CONTROLES_DEFAULT.read_text(encoding="utf-8"))["casos"]
    casos = [(caso, "NEGATIVO") for caso in casos_negativos]
    casos += [(caso, "CONTROL") for caso in controles]

    for caso, _ in casos:
        esperado = str(caso.get("estado_suficiencia_esperado", "")).lower()
        if esperado not in ESTADOS_VALIDOS:
            raise ValueError(
                f"El caso {caso.get('id')} no declara un "
                "estado_suficiencia_esperado válido."
            )

    threshold = float(settings.rag_evidence_min_score)
    abstenciones_automaticas = 0
    pasan_umbral = 0
    sin_resultados = 0
    llamadas_r07 = 0
    veredictos = {"PASS": 0, "FAIL": 0, "NO EVALUADO": 0}
    resumen_suficiencia = {
        "sufficient": 0,
        "partial": 0,
        "insufficient": 0,
        "unavailable": 0,
    }

    def comprobar_suficiencia(consulta: str, resultados: list[dict], version: str) -> dict:
        nonlocal llamadas_r07
        if llamadas_r07 and args.pausa_segundos:
            time.sleep(args.pausa_segundos)
        llamadas_r07 += 1
        contexto = anadir_notas_de_alcance(consulta, resultados, version)
        cobertura = evaluar_suficiencia_evidencia(consulta, contexto)
        estado = str(cobertura.get("status", "unavailable")).lower()
        resumen_suficiencia[estado] = resumen_suficiencia.get(estado, 0) + 1
        return cobertura

    print("=" * 88)
    print("AUDITORÍA R07 — RECUPERACIÓN Y SUFICIENCIA DOCUMENTAL")
    print(
        f"Casos negativos: {len(casos_negativos)} | controles positivos/parciales: {len(controles)} "
        f"| total: {len(casos)} | top_k: {args.top_k} | umbral: {threshold:.3f}"
    )
    if args.comprobar_suficiencia:
        print(
            f"Con llamadas a Groq; pausa entre llamadas: {args.pausa_segundos:g} s. "
            "No se modifica la BD ni ningún archivo del proyecto."
        )
    else:
        print(
            "Sin llamadas a Groq: solo se comprueba la recuperación. "
            "Los veredictos de suficiencia quedan sin evaluar."
        )
    print("=" * 88)

    for index, (caso, tipo) in enumerate(casos, start=1):
        resultados = buscar_fragmentos(caso["consulta"], caso["version"], args.top_k)
        mejor_score = max(
            (float(resultado.get("score", 0.0)) for resultado in resultados),
            default=0.0,
        )
        if not resultados:
            sin_resultados += 1
        if not resultados or mejor_score < threshold:
            abstenciones_automaticas += 1
            estado_puerta = "ABSTENCIÓN AUTOMÁTICA PREVIA A R07"
        else:
            pasan_umbral += 1
            estado_puerta = "SUPERA EL UMBRAL: DEBE EVALUARSE LA SUFICIENCIA"

        print(f"\n{index:02d}. {caso['id']} [{caso['version']}] — {tipo}")
        print(f"    Pregunta: {caso['consulta']}")
        if caso.get("dato_no_documentado"):
            print(f"    Dato ausente: {caso['dato_no_documentado']}")
        if caso.get("dato_esperado"):
            print(f"    Dato esperado: {caso['dato_esperado']}")
        print(f"    Mejor score: {mejor_score:.3f} | umbral: {threshold:.3f}")
        print(f"    Puerta por similitud: {estado_puerta}")

        if not args.comprobar_suficiencia:
            veredictos["NO EVALUADO"] += 1
            print("    Resultado R07: NO EVALUADO (falta --comprobar-suficiencia)")
        elif not resultados or mejor_score < threshold:
            esperado = caso["estado_suficiencia_esperado"]
            if esperado == "insufficient":
                # La aplicación ya se abstendría antes de invocar el evaluador R07.
                veredictos["PASS"] += 1
                print(
                    "    Veredicto: PASS — abstención previa correcta; "
                    "la etapa LLM/R07 no se ejecutó en este caso."
                )
            else:
                veredictos["FAIL"] += 1
                print(
                    "    Veredicto: FAIL — el caso debía poder llegar a R07, "
                    "pero la recuperación no superó el umbral."
                )
        else:
            try:
                cobertura = comprobar_suficiencia(
                    caso["consulta"], resultados, caso["version"]
                )
                obtenido = str(cobertura.get("status", "unavailable")).upper()
                print(f"    Resultado R07: {obtenido}")
                for item in cobertura.get("requested_items", []):
                    print(
                        f"      - {item.get('item', '(sin nombre)')}: "
                        f"{item.get('status', 'uncertain')}"
                    )
                if cobertura.get("missing_information"):
                    print(
                        "    No localizado: "
                        + "; ".join(cobertura["missing_information"])
                    )

                errores = validar_cobertura(caso, cobertura)
                if errores:
                    veredictos["FAIL"] += 1
                    print("    Veredicto: FAIL")
                    for error in errores:
                        print(f"      - {error}")
                else:
                    veredictos["PASS"] += 1
                    print(
                        "    Veredicto: PASS — coincide con el estado esperado "
                        "y con la cobertura de sus elementos."
                    )
            except Exception as exc:
                resumen_suficiencia["unavailable"] += 1
                veredictos["FAIL"] += 1
                print(f"    Resultado R07: UNAVAILABLE ({type(exc).__name__})")
                print("    Veredicto: FAIL — no se pudo completar la evaluación.")

        for rank, resultado in enumerate(resultados[:3], start=1):
            print(
                f"    {rank}. {documento_de(resultado['chunk_id'])} | "
                f"{resultado.get('seccion')} | "
                f"score={float(resultado.get('score', 0.0)):.3f}"
            )

    print("\n" + "=" * 88)
    print("RESUMEN DE RECUPERACIÓN")
    print(
        f"Abstención automática por score bajo/sin resultados: "
        f"{abstenciones_automaticas}/{len(casos)}"
    )
    print(f"Casos que superan el umbral: {pasan_umbral}/{len(casos)}")
    print(f"Sin resultados recuperados: {sin_resultados}/{len(casos)}")
    print("IMPORTANTE: superar el umbral no significa que la pregunta esté contestada.")

    print("\nRESUMEN DE SUFICIENCIA")
    print(
        "Estados observados: "
        + ", ".join(
            f"{estado.upper()}={cantidad}"
            for estado, cantidad in resumen_suficiencia.items()
        )
    )
    print(f"Llamadas R07 realizadas: {llamadas_r07}")
    print(
        "Veredictos: "
        + ", ".join(f"{estado}={cantidad}" for estado, cantidad in veredictos.items())
    )

    if args.comprobar_suficiencia:
        fallos = veredictos["FAIL"]
        print(f"Resultado de auditoría: {'PASS' if fallos == 0 else 'FAIL'}")
        print("=" * 88)
        return 1 if fallos else 0

    print("Repite con --comprobar-suficiencia para validar los estados esperados.")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
