
"""Diagnóstico de recuperación de secciones R03.

No modifica la BD ni escribe archivos.
Compara:
1. Fragmentos realmente indexados.
2. Ranking completo antes del límite por documento.
3. Los cinco fragmentos que conservaría la recuperación final.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np

from config import settings
import services.retrieval as retrieval
from services.embeddings import embedding_normalizado
from services.ranking_hibrido import ordenar_hibrido
from services.ranking_operativo import reordenar_con_anclaje


BENCHMARK_PATH = Path(__file__).with_name("benchmark_rag_v2.json")

CASOS_OBJETIVO = {
    "PRC-004-VALIDACION-CIR02",
    "PRC-009-PRESION-CIR01",
    "PRC-012-PRUEBA-INTEGRAL",
    "CAT-CAUDALES-BOMBAS-AUX",
}


def documento_de(chunk_id: str) -> str:
    return chunk_id.rsplit("_", 1)[0]


def coincide_objetivo(resultado: dict, relevantes: list[dict]) -> bool:
    documento = documento_de(resultado["chunk_id"])
    seccion = resultado.get("seccion")

    return any(
        documento == objetivo["documento"]
        and seccion in objetivo.get("secciones", [])
        for objetivo in relevantes
    )


def construir_ranking_completo(
    consulta: str,
    version: str,
    fragmentos: list[dict],
) -> list[dict]:
    """Replica el ranking de retrieval.py, pero sin limitar a dos fragmentos
    por documento. Así podemos observar las posiciones que el límite ocultaría.
    """

    vector_pregunta = embedding_normalizado(consulta)
    codigos = retrieval._extraer_codigos_htm(consulta)

    aplicables = [
        f for f in fragmentos
        if f["categoria"] != "Dictionary"
        and version in f["versiones"]
    ]

    hay_dtc_exacto = bool(codigos) and any(
        f["categoria"] == "DTC"
        and codigos.intersection(
            retrieval._extraer_codigos_htm(f.get("seccion") or "")
        )
        for f in aplicables
    )

    if hay_dtc_exacto:
        aplicables = [
            f for f in aplicables
            if not retrieval._es_entrada_de_otro_codigo(f, codigos)
        ]

    resultados = []

    for f in aplicables:
        score = float(np.dot(f["vector"], vector_pregunta))

        resultados.append({
            "chunk_id": f["chunk_id"],
            "texto": f["texto"],
            "categoria": f["categoria"],
            "score": score,
            "ranking_score": (
                score + retrieval._ajuste_orden_codigo(f, codigos)
            ),
            "versiones": f["versiones"],
            "pagina": f["pagina"],
            "seccion": f["seccion"],
        })

    def clave_orden(resultado: dict) -> tuple[bool, float]:
        dtc_exacto = (
            resultado["categoria"] == "DTC"
            and bool(codigos.intersection(
                retrieval._extraer_codigos_htm(
                    resultado.get("seccion") or ""
                )
            ))
        )
        return dtc_exacto, resultado["ranking_score"]

    resultados.sort(key=clave_orden, reverse=True)

    if settings.rag_hybrid_retrieval_enabled:
        resultados = ordenar_hibrido(
            consulta,
            resultados,
            rrf_k=settings.rag_rrf_k,
        )

        resultados.sort(
            key=lambda resultado: (
                resultado["categoria"] == "DTC"
                and bool(codigos.intersection(
                    retrieval._extraer_codigos_htm(
                        resultado.get("seccion") or ""
                    )
                )),
                float(resultado["rrf_score"]),
                float(resultado["ranking_score"]),
            ),
            reverse=True,
        )

    if getattr(settings, "rag_component_anchor_enabled", False):
        resultados, _ = reordenar_con_anclaje(
            consulta,
            resultados,
        )

    return resultados


def mostrar_resultado(
    posicion: int,
    resultado: dict,
    relevantes: list[dict],
) -> None:
    documento = documento_de(resultado["chunk_id"])
    seccion = resultado.get("seccion") or "(sin sección)"

    if coincide_objetivo(resultado, relevantes):
        marca = "OBJETIVO"
    elif any(
        documento == objetivo["documento"]
        for objetivo in relevantes
    ):
        marca = "DOC"
    else:
        marca = "     "

    sem_rank = resultado.get("semantic_rank", "-")
    bm25_rank = resultado.get("bm25_rank", "-")
    rrf = resultado.get("rrf_score")

    texto = " ".join((resultado.get("texto") or "").split())
    texto = texto[:150]

    print(
        f"{posicion:>3}. [{marca}] {documento}"
        f" | pág. {resultado.get('pagina')}"
        f" | sección: {seccion}"
    )
    print(
        f"     score={resultado['score']:.4f}"
        f" | semantic_rank={sem_rank}"
        f" | bm25_rank={bm25_rank}"
        f" | RRF={rrf if rrf is None else round(rrf, 6)}"
    )
    print(f"     Texto: {texto}")


def main() -> int:
    if not BENCHMARK_PATH.exists():
        print(f"No existe el benchmark: {BENCHMARK_PATH}")
        return 1

    benchmark = json.loads(
        BENCHMARK_PATH.read_text(encoding="utf-8")
    )

    casos = [
        caso for caso in benchmark["casos"]
        if caso["id"] in CASOS_OBJETIVO
    ]

    if len(casos) != len(CASOS_OBJETIVO):
        print("AVISO: no se han encontrado los cuatro casos esperados.")

    fragmentos = retrieval.cargar_fragmentos()

    print("=" * 90)
    print("DIAGNÓSTICO R03 — RECUPERACIÓN DE SECCIONES")
    print("=" * 90)
    print(f"Base de datos: {settings.db_path}")
    print(
        f"Configuración declarada: "
        f"chunk={settings.rag_chunk_size}, "
        f"overlap={settings.rag_chunk_overlap}"
    )
    print(f"Fragmentos cargados: {len(fragmentos)}")
    print(f"BM25 + RRF activado: {settings.rag_hybrid_retrieval_enabled}")
    print(
        "Anclaje por componente activado: "
        f"{getattr(settings, 'rag_component_anchor_enabled', False)}"
    )

    if settings.db_path.name != "thermodrive_rag.db":
        print(
            "AVISO: la BD activa no es thermodrive_rag.db. "
            "Comprueba que estás usando la referencia 800/200."
        )

    for caso in casos:
        consulta = caso["consulta"]
        version = caso["version"]
        relevantes = caso["relevantes"]

        documentos_objetivo = {
            objetivo["documento"] for objetivo in relevantes
        }

        secciones_objetivo = {
            (objetivo["documento"], seccion)
            for objetivo in relevantes
            for seccion in objetivo.get("secciones", [])
        }

        print("\n" + "=" * 90)
        print(f"CASO: {caso['id']} [{version}]")
        print(f"CONSULTA: {consulta}")
        print("=" * 90)

        # 1. Comprobar qué se ha indexado realmente.
        filas_objetivo = [
            f for f in fragmentos
            if documento_de(f["chunk_id"]) in documentos_objetivo
            and version in f["versiones"]
        ]

        print("\n1) FRAGMENTOS INDEXADOS DEL DOCUMENTO OBJETIVO")
        print(f"Fragmentos aplicables a {version}: {len(filas_objetivo)}")

        if not filas_objetivo:
            print("NO HAY FRAGMENTOS APLICABLES PARA ESTA VERSIÓN.")
        else:
            secciones = Counter(
                f.get("seccion") or "(sin sección)"
                for f in filas_objetivo
            )
            print(f"Secciones encontradas: {dict(secciones)}")

            for f in filas_objetivo:
                documento = documento_de(f["chunk_id"])
                seccion = f.get("seccion") or "(sin sección)"
                esperado = (documento, seccion) in secciones_objetivo
                marca = "OBJETIVO" if esperado else "      "

                texto = " ".join((f.get("texto") or "").split())
                texto = texto[:190]

                print(
                    f"[{marca}] pág. {f.get('pagina')}"
                    f" | {seccion}"
                    f" | {f['chunk_id']}"
                )
                print(f"          Texto: {texto}")

        # 2. Ranking completo, sin límite de dos fragmentos por documento.
        ranking = construir_ranking_completo(
            consulta,
            version,
            fragmentos,
        )

        posiciones_objetivo = [
            (posicion, resultado)
            for posicion, resultado in enumerate(ranking, start=1)
            if coincide_objetivo(resultado, relevantes)
        ]

        print("\n2) RANKING COMPLETO ANTES DEL LÍMITE POR DOCUMENTO")
        print(f"Candidatos aplicables: {len(ranking)}")

        if posiciones_objetivo:
            print("Posiciones de las secciones objetivo:")
            for posicion, resultado in posiciones_objetivo:
                print(
                    f"  - Posición {posicion}: "
                    f"{documento_de(resultado['chunk_id'])}"
                    f" | {resultado.get('seccion')}"
                    f" | {resultado['chunk_id']}"
                )
        else:
            print("Ninguna sección objetivo aparece en el ranking.")

        print("\nPrimeros 15 candidatos:")
        for posicion, resultado in enumerate(ranking[:15], start=1):
            mostrar_resultado(posicion, resultado, relevantes)

        # 3. Aplicar el mismo límite de dos fragmentos por documento
        # que utiliza buscar_fragmentos(), y mostrar el top 5 efectivo.
        top5 = retrieval._limitar_fragmentos_por_documento(
            ranking,
            5,
        )

        print("\n3) TOP 5 DESPUÉS DEL LÍMITE DE FRAGMENTOS POR DOCUMENTO")
        for posicion, resultado in enumerate(top5, start=1):
            mostrar_resultado(posicion, resultado, relevantes)

        acierto_final = any(
            coincide_objetivo(resultado, relevantes)
            for resultado in top5
        )
        print(
            "\nResultado del caso: "
            + ("SECCIÓN OBJETIVO EN TOP 5" if acierto_final
               else "SECCIÓN OBJETIVO FUERA DEL TOP 5")
        )

    print("\n" + "=" * 90)
    print("FIN DEL DIAGNÓSTICO. NO SE HA MODIFICADO NINGÚN ARCHIVO NI LA BD.")
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
