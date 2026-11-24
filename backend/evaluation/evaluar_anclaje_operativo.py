"""Evalúa un reranking experimental por anclaje de componente y sección operativa.

No modifica retrieval.py, la BD ni el .env. Compara el ranking híbrido actual
con un candidato que, solo en preguntas procedimentales con un código CMP-XX,
prioriza secciones operativas de los mismos documentos que contienen ese código.

Ejecutar desde la raíz del repositorio:
    python backend/evaluation/evaluar_anclaje_operativo.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import retrieval  # noqa: E402
from config import settings  # noqa: E402

_COMPONENT_RE = re.compile(r"(?<![A-Z0-9])CMP[-‐‑‒–—−]?\d{2}(?!\d)", re.IGNORECASE)
_ACTION_SECTIONS = {
    "pasos",
    "valores esperados",
    "criterios de aceptacion",
    "verificacion final",
}


def normalizar(texto: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(char) != "Mn"
    )


def codigos_componente(texto: str) -> set[str]:
    return {
        re.sub(r"[-‐‑‒–—−]", "-", match.upper())
        for match in _COMPONENT_RE.findall(texto or "")
    }


def es_consulta_procedimental(consulta: str) -> bool:
    """Detecta preguntas explícitas de cómo realizar/comprobar algo."""
    texto = normalizar(consulta)
    pregunta_como = bool(re.search(r"\b(como|de que manera)\b", texto))
    accion = bool(re.search(
        r"\b(comprobar|comprueba|verificar|verifica|realizar|realiza|"
        r"ejecutar|ejecuta|medir|mide|probar|prueba|inspeccionar|revisar)\b",
        texto,
    ))
    return pregunta_como and accion


def es_seccion_operativa(seccion: str) -> bool:
    seccion_norm = normalizar(seccion).strip()
    if seccion_norm in _ACTION_SECTIONS:
        return True
    # El apartado 4.5 del manual de diagnóstico también es una sección
    # operativa pertinente para consultas sobre el electroventilador.
    return bool(re.match(r"4\.5\s+electroventilador", seccion_norm))


def documentos_anclados(resultados: list[dict[str, Any]], codigos: set[str]) -> set[str]:
    """Encuentra documentos que mencionan explícitamente el componente consultado."""
    if not codigos:
        return set()
    anclados: set[str] = set()
    for resultado in resultados:
        texto = " ".join((
            str(resultado.get("texto") or ""),
            str(resultado.get("seccion") or ""),
            str(resultado.get("chunk_id") or ""),
        ))
        if codigos.intersection(codigos_componente(texto)):
            anclados.add(retrieval.documento_de(resultado["chunk_id"]))
    return anclados


def reordenar_con_anclaje(
    consulta: str,
    resultados: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Candidato de reranking: no modifica score, ranking_score ni rrf_score."""
    codigos = codigos_componente(consulta)
    procedimental = es_consulta_procedimental(consulta)
    docs_anclados = documentos_anclados(resultados, codigos) if procedimental else set()

    def clave(resultado: dict[str, Any]) -> tuple[bool, bool, float, float]:
        seccion_operativa_anclada = (
            retrieval.documento_de(resultado["chunk_id"]) in docs_anclados
            and es_seccion_operativa(str(resultado.get("seccion") or ""))
        )
        codigos_htm = retrieval._extraer_codigos_htm(consulta)
        dtc_exacto = (
            resultado.get("categoria") == "DTC"
            and bool(codigos_htm.intersection(
                retrieval._extraer_codigos_htm(str(resultado.get("seccion") or ""))
            ))
        )
        return (
            dtc_exacto,
            seccion_operativa_anclada,
            float(resultado.get("rrf_score", 0.0)),
            float(resultado.get("ranking_score", 0.0)),
        )

    return sorted(resultados, key=clave, reverse=True), {
        "codigos_componente": sorted(codigos),
        "consulta_procedimental": procedimental,
        "documentos_anclados": sorted(docs_anclados),
    }


def limitar_diversidad(
    resultados: list[dict[str, Any]], top_k: int, max_por_documento: int = 2
) -> list[dict[str, Any]]:
    salida: list[dict[str, Any]] = []
    conteo: dict[str, int] = {}
    for resultado in resultados:
        doc = retrieval.documento_de(resultado["chunk_id"])
        if conteo.get(doc, 0) >= max_por_documento:
            continue
        salida.append(resultado)
        conteo[doc] = conteo.get(doc, 0) + 1
        if len(salida) >= top_k:
            break
    return salida


def es_relevante(resultado: dict[str, Any], objetivos: list[dict[str, Any]]) -> tuple[bool, bool]:
    documento = retrieval.documento_de(resultado["chunk_id"])
    for objetivo in objetivos:
        if documento != objetivo["documento"]:
            continue
        return True, str(resultado.get("seccion") or "") in objetivo.get("secciones", [])
    return False, False


def primer_hit(resultados: list[dict[str, Any]], objetivos: list[dict[str, Any]], seccion: bool) -> int | None:
    for posicion, resultado in enumerate(resultados, 1):
        hit_doc, hit_seccion = es_relevante(resultado, objetivos)
        if hit_seccion if seccion else hit_doc:
            return posicion
    return None


def metricas(casos: list[dict[str, Any]], rankings: dict[str, list[dict[str, Any]]]) -> dict[str, float]:
    n = len(casos)
    hits_doc = {k: 0 for k in (1, 3, 5)}
    hits_sec = {k: 0 for k in (1, 3, 5)}
    mrr = 0.0
    for caso in casos:
        resultados = rankings[caso["id"]]
        for k in hits_doc:
            if primer_hit(resultados[:k], caso["relevantes"], False) is not None:
                hits_doc[k] += 1
            if primer_hit(resultados[:k], caso["relevantes"], True) is not None:
                hits_sec[k] += 1
        posicion = primer_hit(resultados[:5], caso["relevantes"], True)
        if posicion:
            mrr += 1.0 / posicion
    salida: dict[str, float] = {}
    for k in hits_doc:
        salida[f"documento@{k}"] = hits_doc[k] / n
        salida[f"seccion@{k}"] = hits_sec[k] / n
    salida["mrr_seccion@5"] = mrr / n
    return salida


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa reranking operativo anclado a códigos CMP")
    parser.add_argument(
        "--benchmark",
        default="backend/evaluation/benchmark_rag_v1_1.json",
        help="Ruta al benchmark v1.1",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k debe ser mayor que cero")
    if not getattr(settings, "rag_hybrid_retrieval_enabled", False):
        parser.error("Activa RAG_HYBRID_RETRIEVAL_ENABLED=true en el .env antes de evaluar")

    benchmark_path = (ROOT / args.benchmark).resolve()
    if not benchmark_path.exists():
        parser.error(f"No se encuentra el benchmark: {benchmark_path}")
    casos = json.loads(benchmark_path.read_text(encoding="utf-8")).get("casos", [])
    if not casos:
        parser.error("El benchmark no contiene casos")

    limite_original = retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO
    retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = 100_000
    ranking_actual: dict[str, list[dict[str, Any]]] = {}
    ranking_candidato: dict[str, list[dict[str, Any]]] = {}
    detalles: dict[str, dict[str, Any]] = {}
    try:
        for caso in casos:
            brutos = retrieval.buscar_fragmentos(caso["consulta"], caso["version"], top_k=100_000)
            ranking_actual[caso["id"]] = limitar_diversidad(brutos, args.top_k)
            reordenados, diagnostico = reordenar_con_anclaje(caso["consulta"], brutos)
            ranking_candidato[caso["id"]] = limitar_diversidad(reordenados, args.top_k)
            detalles[caso["id"]] = diagnostico
    finally:
        retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = limite_original

    met_actual = metricas(casos, ranking_actual)
    met_candidato = metricas(casos, ranking_candidato)

    print("=" * 88)
    print("EXPERIMENTO — RANKING HÍBRIDO ACTUAL vs ANCLAJE OPERATIVO POR COMPONENTE")
    print(f"Consultas: {len(casos)} | top_k: {args.top_k} | Sin llamadas a Groq ni cambios en BD")
    print("=" * 88)
    for nombre, datos in (("HÍBRIDO ACTUAL", met_actual), ("CANDIDATO CON ANCLAJE", met_candidato)):
        print(f"\n{nombre}")
        for k in (1, 3, 5):
            print(
                f"  Documento@{k}: {datos[f'documento@{k}']:.1%}"
                f" | Sección@{k}: {datos[f'seccion@{k}']:.1%}"
            )
        print(f"  MRR sección@5: {datos['mrr_seccion@5']:.3f}")

    print("\nCOMPARACIÓN POR CONSULTA — primera sección relevante")
    print("ID | Actual | Candidato")
    print("-" * 88)
    for caso in casos:
        id_caso = caso["id"]
        actual = primer_hit(ranking_actual[id_caso], caso["relevantes"], True)
        candidato = primer_hit(ranking_candidato[id_caso], caso["relevantes"], True)
        print(f"{id_caso} | {actual or 'NO TOP'} | {candidato or 'NO TOP'}")

    print("\nDETALLE PRC-005")
    caso_prc = next((c for c in casos if c["id"] == "PRC-005-ELECTROVENTILADOR"), None)
    if caso_prc:
        print("Diagnóstico:", detalles[caso_prc["id"]])
        for nombre, resultados in (
            ("ACTUAL", ranking_actual[caso_prc["id"]]),
            ("CANDIDATO", ranking_candidato[caso_prc["id"]]),
        ):
            print(f"  {nombre}:")
            for posicion, resultado in enumerate(resultados, 1):
                hit_doc, hit_sec = es_relevante(resultado, caso_prc["relevantes"])
                marca = "SECCIÓN" if hit_sec else ("DOC" if hit_doc else "")
                print(
                    f"    {posicion}. [{marca}] {retrieval.documento_de(resultado['chunk_id'])}"
                    f" | {resultado.get('seccion')}"
                    f" | rrf={float(resultado.get('rrf_score', 0.0)):.5f}"
                    f" | score={float(resultado.get('score', 0.0)):.3f}"
                )

    print("\nNota: el candidato solo añade prioridad de orden para secciones operativas dentro de")
    print("documentos que mencionan el CMP consultado, y solo ante preguntas explícitas de cómo.")
    print("No altera score, ranking_score, rrf_score ni la base de datos.")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
