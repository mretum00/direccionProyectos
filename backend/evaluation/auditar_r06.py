"""Audita los casos R06 del benchmark contra la lógica determinista.

Uso desde la raíz del repositorio:
    py -3 backend/evaluation/auditar_r06.py

No llama a Groq ni modifica la base de datos. El caso sin versión se comprueba
contra el pipeline, que debe pedir la versión antes de reformular o recuperar.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.ambiguedad import detectar_aclaracion_tecnica  # noqa: E402
from services.rag_pipeline import armar_respuesta  # noqa: E402

BENCHMARK_DEFAULT = Path(__file__).with_name("benchmark_r06_r07_v1_1.json")

FRASES_OBLIGATORIAS = {
    "R06-06-TESTIGO-ROJO": ("amarillo fijo", "rojo parpadeante"),
    "R06-07-CALEFACCION-GENERICA": (
        "diagnóstico 4.6",
        "frío extremo",
        "temperaturas moderadas",
        "empeorado progresivamente",
    ),
    "R06-08-MANTENIMIENTO-GENERICO": ("CMP-24", "CMP-09"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita las aclaraciones R06 del benchmark.")
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_DEFAULT)
    args = parser.parse_args()

    casos = json.loads(args.benchmark.read_text(encoding="utf-8"))["casos"]
    casos = [caso for caso in casos if caso.get("requisito") == "R06"]
    if not settings.rag_ambiguity_detection_enabled:
        print("ERROR: RAG_AMBIGUITY_DETECTION_ENABLED está desactivado en .env/configuración.")
        return 2

    fallos = []
    print(f"AUDITORÍA R06 v1.1 — {len(casos)} casos; sin llamadas a Groq")
    print("=" * 88)

    for caso in casos:
        caso_id = caso["id"]
        if not caso.get("version"):
            resultado = armar_respuesta(caso["consulta"], caso["version"], "mechanic", [])
            correcto = (
                resultado.get("needs_clarification") is True
                and resultado.get("clarification_kind") == "engine_version"
            )
            mensaje = str(resultado.get("message", {}).get("content", ""))
            detalle = "petición de versión" if correcto else "no pidió la versión"
        else:
            aclaracion = detectar_aclaracion_tecnica(caso["consulta"])
            mensaje = aclaracion["message"] if aclaracion else ""
            correcto = aclaracion is not None
            if correcto:
                codigos_esperados = set(
                    re.findall(r"\b(?:CMP|CIR|TES)-\d{2}\b", caso.get("aclaracion_necesaria", ""))
                )
                codigos_obtenidos = set(re.findall(r"\b(?:CMP|CIR|TES)-\d{2}\b", mensaje))
                faltan = sorted(codigos_esperados - codigos_obtenidos)
                frases_faltantes = [
                    frase for frase in FRASES_OBLIGATORIAS.get(caso_id, ())
                    if frase.casefold() not in mensaje.casefold()
                ]
                correcto = not faltan and not frases_faltantes
                if faltan or frases_faltantes:
                    detalle = "faltan códigos/frases: " + ", ".join(faltan + frases_faltantes)
                else:
                    detalle = aclaracion["code"]
            else:
                detalle = "no solicitó aclaración"

        estado = "PASS" if correcto else "FAIL"
        print(f"{estado} {caso_id}: {detalle}")
        if not correcto:
            fallos.append(caso_id)

    print("=" * 88)
    print(f"Resultado: {len(casos) - len(fallos)}/{len(casos)} casos correctos")
    if fallos:
        print("Fallos: " + ", ".join(fallos))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
