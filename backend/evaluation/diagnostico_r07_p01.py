"""Diagnostica por qué R07-P01-CMP02 pierde suficiencia con COMBINADA.

Ejecutar desde la raíz del repositorio:
    py -3 backend/evaluation/diagnostico_r07_p01.py

Solo realiza recuperación local (embeddings + BD). No llama a Groq y no
modifica archivos, configuración persistente ni la base de datos.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.retrieval import buscar_fragmentos  # noqa: E402

CONSULTA = "¿Qué caudal nominal tiene la bomba eléctrica auxiliar A CMP-02?"
VERSION = "V2.0"
TOP_K = 5
FUENTE_ESPERADA = "HTM240-CAT-001_Catalogo_componentes.pdf_2"
PATRON_CAUDAL = re.compile(r"8\s*(?:-|–|a)\s*14\s*l\s*/\s*min", re.IGNORECASE)


def mostrar_resultado(nombre: str, resultados: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 96)
    print(nombre)
    print("=" * 96)
    ids = [str(r.get("chunk_id", "")) for r in resultados]
    print(f"Fuente esperada del benchmark recuperada: {FUENTE_ESPERADA in ids}")
    if FUENTE_ESPERADA in ids:
        print(f"Posición de la fuente esperada: {ids.index(FUENTE_ESPERADA) + 1}")
    else:
        print("Posición de la fuente esperada: fuera del top 5")

    for posicion, resultado in enumerate(resultados, start=1):
        chunk_id = str(resultado.get("chunk_id") or "")
        texto = str(resultado.get("texto") or "")
        caudal = PATRON_CAUDAL.search(texto)
        print(f"\n{posicion}. {chunk_id}")
        print(
            f"   Sección={resultado.get('seccion')!r} | "
            f"Página={resultado.get('pagina')!r} | "
            f"Categoría={resultado.get('categoria')!r} | "
            f"Score={float(resultado.get('score', 0.0)):.3f}"
        )
        print(f"   Menciona CMP-02: {'CMP-02' in texto.upper() or 'CMP-02' in str(resultado.get('seccion') or '').upper()}")
        print(f"   Contiene el caudal 8-14 l/min: {bool(caudal)}")
        print("   Texto:")
        print("   " + (texto.replace("\n", " ") if texto else "(vacío)"))


def main() -> int:
    if not hasattr(settings, "rag_combined_reranking_enabled"):
        print("ERROR: config.py no contiene rag_combined_reranking_enabled.")
        return 2

    valor_original = settings.rag_combined_reranking_enabled
    print("DIAGNÓSTICO R07-P01 — CAUDAL CMP-02")
    print(f"Consulta: {CONSULTA}")
    print(f"Versión: {VERSION} | top_k: {TOP_K}")
    print(f"BD: {settings.db_path}")
    print("No llama a Groq. Solo compara los cinco fragmentos recuperados en cada modo.")

    try:
        for activado, nombre in (
            (False, "COMBINADA DESACTIVADA (baseline de recuperación)"),
            (True, "COMBINADA ACTIVADA"),
        ):
            object.__setattr__(settings, "rag_combined_reranking_enabled", activado)
            resultados = buscar_fragmentos(CONSULTA, VERSION, TOP_K)
            mostrar_resultado(nombre, resultados)
    finally:
        object.__setattr__(settings, "rag_combined_reranking_enabled", valor_original)

    print("\nConfiguración original restaurada en memoria.")
    print("No se modificó ningún archivo ni la base de datos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
