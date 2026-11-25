"""Compara variantes experimentales de reranking para R03 (ThermoDrive).

Uso desde la raíz del repositorio:
    py -3 backend/evaluation/experimento_reranking_r03.py
    py -3 backend/evaluation/experimento_reranking_r03.py --top-k 5
    py -3 backend/evaluation/experimento_reranking_r03.py --benchmark backend/evaluation/benchmark_rag_v2.json

El experimento compara:
- BASELINE: ranking actual de producción y límite de dos fragmentos por documento.
- INTENCION: promoción amplia de secciones preferidas en los cinco primeros
  documentos distintos del ranking.
- COMPONENTES: cobertura explícita de todos los códigos CMP presentes en una
  consulta que mencione dos o más componentes.
- INTENCION_INTERCALADA: prioridad de secciones dentro del documento principal,
  intercalada con resultados de otros documentos para conservar diversidad.
- COMBINADA: si la consulta exige varios CMP, coloca primero las fichas exactas
  de todos ellos y completa el top_k con la selección intercalada; en el resto
  de consultas utiliza directamente INTENCION_INTERCALADA.

El script no modifica retrieval.py, la configuración, la base de datos ni el
benchmark. No llama al LLM/Groq y no escribe archivos salvo que se modifique
expresamente este comportamiento en el código.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import services.retrieval as retrieval  # noqa: E402
from services.ranking_operativo import codigos_componente, normalizar  # noqa: E402
from db.repositories import RagChunkRepository  # noqa: E402

BENCHMARK_DEFAULT = Path(__file__).with_name("benchmark_rag_v2.json")

_PATRON_CODIGO_HTM = re.compile(
    r"(?<![A-Z0-9])HTM[-‐‑‒–—−]?\d{4}(?!\d)",
    re.IGNORECASE,
)
_PATRON_CODIGO_CMP_SECCION = re.compile(
    r"^CMP[-‐‑‒–—−]?(\d{2})$",
    re.IGNORECASE,
)


def documento_de(chunk_id: str) -> str:
    """Devuelve el nombre del documento a partir del identificador del chunk."""
    return str(chunk_id or "").rsplit("_", 1)[0]


def normalizar_seccion(seccion: Any) -> str:
    """Normaliza una etiqueta de sección para comparar sin tildes ni espacios extra."""
    return normalizar(str(seccion or "")).strip()


def es_dtc_exacto(consulta: str) -> bool:
    """Evita que las variantes experimentales desplacen consultas por código HTM."""
    return bool(_PATRON_CODIGO_HTM.search(consulta or ""))


def extraer_secciones_preferidas(consulta: str) -> list[str]:
    """Detecta los tipos de sección que pueden responder a la intención consultada."""
    consulta_normalizada = normalizar(consulta)
    secciones: list[str] = []

    # Consultas que piden instrucciones, una comprobación o una prueba.
    if re.search(
        r"\b(como|pasos|procedimiento|prueba|comprobar|comprueba|"
        r"verificacion|verificar|realizar|realiza|ejecutar|ejecuta|"
        r"inspeccionar|inspeccion|sustituir|registrar|confirmar)\b",
        consulta_normalizada,
    ):
        secciones.append("Pasos")

    # Consultas que buscan magnitudes, tolerancias o valores técnicos.
    if re.search(
        r"\b(valor|valores|caudal|caudales|corriente|consumo|presion|"
        r"temperatura|tolerancia|caida|rango|rangos|medida|medidas|"
        r"medicion|mediciones|nominal|nominales)\b",
        consulta_normalizada,
    ):
        secciones.append("Valores esperados")

    # Consultas que preguntan por conformidad o condiciones de aceptación.
    if re.search(
        r"\b(aceptacion|aceptable|aceptar|conforme|conformidad|"
        r"condicion|condiciones|criterio|criterios|cumple|cumplir)\b",
        consulta_normalizada,
    ):
        secciones.append("Criterios de aceptación")

    return secciones


def coincide_seccion(
    resultado: dict[str, Any],
    relevantes: list[dict[str, Any]],
) -> bool:
    """Comprueba si resultado coincide con algún documento/sección objetivo."""
    documento = documento_de(resultado.get("chunk_id", ""))
    seccion = normalizar_seccion(resultado.get("seccion"))

    for objetivo in relevantes:
        if documento != objetivo.get("documento"):
            continue
        secciones = objetivo.get("secciones", [])
        if not secciones or seccion in {
            normalizar_seccion(item) for item in secciones
        }:
            return True
    return False


def coincide_documento(
    resultado: dict[str, Any],
    relevantes: list[dict[str, Any]],
) -> bool:
    """Comprueba si el fragmento procede de uno de los documentos objetivo."""
    documento = documento_de(resultado.get("chunk_id", ""))
    return any(documento == objetivo.get("documento") for objetivo in relevantes)


def validar_benchmark(casos: list[dict[str, Any]]) -> None:
    """Comprueba que los documentos y secciones objetivo existen en la BD."""
    filas = RagChunkRepository().list_all()
    disponibles: dict[str, set[str]] = {}

    for fila in filas:
        documento = documento_de(fila.chunk_id)
        disponibles.setdefault(documento, set()).add(
            normalizar_seccion(fila.section)
        )

    errores: list[str] = []
    for caso in casos:
        version = caso.get("version")
        if version not in {"V1.0", "V1.1", "V2.0"}:
            errores.append(f"{caso.get('id')}: versión no válida ({version})")

        for objetivo in caso.get("relevantes", []):
            documento = objetivo.get("documento", "")
            if documento not in disponibles:
                errores.append(
                    f"{caso.get('id')}: no existe el documento objetivo {documento}"
                )
                continue

            for seccion in objetivo.get("secciones", []):
                if normalizar_seccion(seccion) not in disponibles[documento]:
                    errores.append(
                        f"{caso.get('id')}: no existe la sección {seccion!r} en {documento}"
                    )

    if errores:
        raise ValueError(
            "El benchmark contiene objetivos no encontrados:\n- "
            + "\n- ".join(errores)
        )


def limitar_por_documento(
    resultados: list[dict[str, Any]],
    top_k: int,
    limite: int = 2,
) -> list[dict[str, Any]]:
    """Limita la cantidad de fragmentos por documento sin cambiar su orden."""
    seleccionados: list[dict[str, Any]] = []
    cantidades: dict[str, int] = defaultdict(int)

    for resultado in resultados:
        documento = documento_de(resultado.get("chunk_id", ""))
        if cantidades[documento] >= limite:
            continue

        seleccionados.append(resultado)
        cantidades[documento] += 1
        if len(seleccionados) >= top_k:
            break

    return seleccionados


def seleccionar_baseline(
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Aplica el límite de producción (dos fragmentos por documento)."""
    return limitar_por_documento(ranking, top_k, limite=2)


def seleccionar_intencion(
    consulta: str,
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Variante amplia: promueve secciones preferidas en los cinco primeros docs.

    La variante es deliberadamente experimental. Reúne documentos según el
    ranking original, promueve las secciones que parecen responder a la consulta
    y después conserva el límite de dos fragmentos por documento.
    """
    if not ranking or es_dtc_exacto(consulta):
        return seleccionar_baseline(ranking, top_k)

    preferidas = {normalizar_seccion(s) for s in extraer_secciones_preferidas(consulta)}
    if not preferidas:
        return seleccionar_baseline(ranking, top_k)

    documentos_ancla: list[str] = []
    vistos: set[str] = set()
    for resultado in ranking:
        documento = documento_de(resultado.get("chunk_id", ""))
        if documento and documento not in vistos:
            documentos_ancla.append(documento)
            vistos.add(documento)
            if len(documentos_ancla) == 5:
                break

    documentos_ancla_set = set(documentos_ancla)
    promovidos = [
        resultado
        for resultado in ranking
        if documento_de(resultado.get("chunk_id", "")) in documentos_ancla_set
        and normalizar_seccion(resultado.get("seccion")) in preferidas
    ]

    ids_promovidos = {resultado.get("chunk_id") for resultado in promovidos}
    ordenados = promovidos + [
        resultado
        for resultado in ranking
        if resultado.get("chunk_id") not in ids_promovidos
    ]
    return limitar_por_documento(ordenados, top_k, limite=2)


def seleccionar_componentes(
    consulta: str,
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Promueve las fichas exactas de todos los CMP explícitos en la consulta."""
    componentes = sorted(codigos_componente(consulta))
    if len(componentes) < 2:
        return seleccionar_baseline(ranking, top_k)

    promovidos: list[dict[str, Any]] = []
    ids_promovidos: set[str] = set()

    # Una sección de catálogo se considera coincidencia solo si su etiqueta
    # identifica exactamente el CMP. No basta con que el código aparezca citado
    # dentro del texto de otro apartado.
    for componente in componentes:
        numero = componente.split("-")[-1]
        for resultado in ranking:
            seccion = str(resultado.get("seccion") or "").strip()
            coincidencia = _PATRON_CODIGO_CMP_SECCION.fullmatch(seccion)
            if coincidencia and coincidencia.group(1) == numero:
                chunk_id = str(resultado.get("chunk_id") or "")
                if chunk_id not in ids_promovidos:
                    promovidos.append(resultado)
                    ids_promovidos.add(chunk_id)
                break

    ordenados = promovidos + [
        resultado
        for resultado in ranking
        if resultado.get("chunk_id") not in ids_promovidos
    ]
    return limitar_por_documento(ordenados, top_k, limite=2)


def seleccionar_intencion_intercalada(
    consulta: str,
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Prioriza secciones del documento principal e intercala otros documentos.

    Orden:
      1. Primera sección preferida del documento principal.
      2. Primer resultado de hasta dos documentos distintos.
      3. Resto de secciones preferidas del documento principal.
      4. Resto del ranking original.

    Se permiten hasta tres fragmentos del documento principal cuando se han
    detectado tres tipos de sección preferidos; los demás documentos conservan
    el máximo de dos fragmentos.
    """
    if not ranking or es_dtc_exacto(consulta):
        return seleccionar_baseline(ranking, top_k)

    secciones_preferidas = extraer_secciones_preferidas(consulta)
    if not secciones_preferidas:
        return seleccionar_baseline(ranking, top_k)

    documento_principal = documento_de(ranking[0].get("chunk_id", ""))
    if not documento_principal:
        return seleccionar_baseline(ranking, top_k)

    candidatos_preferidos: list[dict[str, Any]] = []
    for seccion_preferida in secciones_preferidas:
        seccion_normalizada = normalizar_seccion(seccion_preferida)
        for resultado in ranking:
            if (
                documento_de(resultado.get("chunk_id", "")) == documento_principal
                and normalizar_seccion(resultado.get("seccion")) == seccion_normalizada
            ):
                candidatos_preferidos.append(resultado)
                break

    if not candidatos_preferidos:
        return seleccionar_baseline(ranking, top_k)

    candidatos_otros_documentos: list[dict[str, Any]] = []
    documentos_ya_seleccionados: set[str] = set()
    for resultado in ranking:
        documento = documento_de(resultado.get("chunk_id", ""))
        if (
            documento
            and documento != documento_principal
            and documento not in documentos_ya_seleccionados
        ):
            candidatos_otros_documentos.append(resultado)
            documentos_ya_seleccionados.add(documento)
            if len(candidatos_otros_documentos) >= 2:
                break

    ordenados: list[dict[str, Any]] = []
    ids_anadidos: set[str] = set()

    def anadir(resultado: dict[str, Any]) -> None:
        chunk_id = resultado.get("chunk_id")
        if chunk_id not in ids_anadidos:
            ordenados.append(resultado)
            ids_anadidos.add(chunk_id)

    anadir(candidatos_preferidos[0])
    for resultado in candidatos_otros_documentos:
        anadir(resultado)
    for resultado in candidatos_preferidos[1:]:
        anadir(resultado)
    for resultado in ranking:
        anadir(resultado)

    resultados_finales: list[dict[str, Any]] = []
    contador_por_documento: dict[str, int] = defaultdict(int)
    limite_principal = 3 if len(secciones_preferidas) >= 3 else 2

    for resultado in ordenados:
        documento = documento_de(resultado.get("chunk_id", ""))
        limite = limite_principal if documento == documento_principal else 2
        if contador_por_documento[documento] >= limite:
            continue

        resultados_finales.append(resultado)
        contador_por_documento[documento] += 1
        if len(resultados_finales) >= top_k:
            break

    return resultados_finales


def seleccionar_combinada(
    consulta: str,
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Combina cobertura explícita CMP y reranking por intención.

    - Sin dos o más códigos CMP: aplica INTENCION_INTERCALADA.
    - Con varios CMP: recupera primero la mejor ficha exacta de catálogo
      para cada CMP solicitado y completa las posiciones restantes con
      INTENCION_INTERCALADA sobre el ranking que queda.

    Al final se aplica un límite global por documento. Las fichas CMP ya
    seleccionadas se conservan siempre, aunque pertenezcan al mismo PDF.
    Las demás posiciones respetan un máximo de dos fragmentos por documento;
    el documento principal puede aportar tres si la consulta detecta tres
    tipos de sección preferidos.
    """
    if not ranking or es_dtc_exacto(consulta):
        return seleccionar_baseline(ranking, top_k)

    componentes = sorted(codigos_componente(consulta))
    if len(componentes) < 2:
        return seleccionar_intencion_intercalada(consulta, ranking, top_k)

    # Primero, una coincidencia de sección exacta para cada CMP solicitado.
    fichas_componentes: list[dict[str, Any]] = []
    ids_componentes: set[str] = set()

    for componente in componentes:
        numero = componente.split("-")[-1]
        for resultado in ranking:
            seccion = str(resultado.get("seccion") or "").strip()
            coincidencia = _PATRON_CODIGO_CMP_SECCION.fullmatch(seccion)
            if coincidencia and coincidencia.group(1) == numero:
                chunk_id = str(resultado.get("chunk_id") or "")
                if chunk_id and chunk_id not in ids_componentes:
                    fichas_componentes.append(resultado)
                    ids_componentes.add(chunk_id)
                break

    # Si no se ha encontrado ninguna ficha exacta, no forzamos un orden
    # artificial: se conserva el comportamiento intercalado habitual.
    if not fichas_componentes:
        return seleccionar_intencion_intercalada(consulta, ranking, top_k)

    ranking_restante = [
        resultado
        for resultado in ranking
        if str(resultado.get("chunk_id") or "") not in ids_componentes
    ]
    plazas_restantes = max(0, top_k - len(fichas_componentes))

    complemento = (
        seleccionar_intencion_intercalada(
            consulta, ranking_restante, plazas_restantes
        )
        if plazas_restantes and ranking_restante
        else []
    )

    # Mantener todos los CMP encontrados y aplicar los límites al complemento.
    seleccionados = list(fichas_componentes)
    ids_seleccionados = set(ids_componentes)
    cantidades_por_documento: dict[str, int] = defaultdict(int)
    for resultado in fichas_componentes:
        cantidades_por_documento[documento_de(resultado.get("chunk_id", ""))] += 1

    documento_principal = documento_de(ranking[0].get("chunk_id", ""))
    limite_principal = (
        3 if len(extraer_secciones_preferidas(consulta)) >= 3 else 2
    )

    for resultado in complemento:
        chunk_id = str(resultado.get("chunk_id") or "")
        if not chunk_id or chunk_id in ids_seleccionados:
            continue

        documento = documento_de(chunk_id)
        limite = limite_principal if documento == documento_principal else 2
        if cantidades_por_documento[documento] >= limite:
            continue

        seleccionados.append(resultado)
        ids_seleccionados.add(chunk_id)
        cantidades_por_documento[documento] += 1

        if len(seleccionados) >= top_k:
            break

    # Por si el complemento intercalado no alcanza el top_k, completar en
    # orden original respetando los mismos límites documentales.
    if len(seleccionados) < top_k:
        for resultado in ranking_restante:
            chunk_id = str(resultado.get("chunk_id") or "")
            if not chunk_id or chunk_id in ids_seleccionados:
                continue

            documento = documento_de(chunk_id)
            limite = limite_principal if documento == documento_principal else 2
            if cantidades_por_documento[documento] >= limite:
                continue

            seleccionados.append(resultado)
            ids_seleccionados.add(chunk_id)
            cantidades_por_documento[documento] += 1

            if len(seleccionados) >= top_k:
                break

    return seleccionados[:top_k]


def calcular_metricas(
    casos: list[dict[str, Any]],
    resultados_por_caso: dict[str, list[dict[str, Any]]],
    top_k: int,
) -> dict[str, Any]:
    """Calcula recuperación, MRR, cobertura estricta de secciones y CMP."""
    total = len(casos)
    aciertos_documento = {k: 0 for k in (1, 3, 5)}
    aciertos_seccion = {k: 0 for k in (1, 3, 5)}
    suma_reciproca = 0.0
    consultas_sin_resultados = 0
    fugas_version = 0
    secciones_objetivo_total = 0
    secciones_encontradas_total = 0
    casos_cobertura_completa = 0
    componentes_exigidos_total = 0
    componentes_encontrados_total = 0
    consultas_multi_cmp = 0
    consultas_multi_cmp_completas = 0

    for caso in casos:
        caso_id = caso["id"]
        resultados = resultados_por_caso.get(caso_id, [])[:top_k]
        relevantes = caso.get("relevantes", [])

        if not resultados:
            consultas_sin_resultados += 1

        for resultado in resultados:
            if caso["version"] not in (resultado.get("versiones") or []):
                fugas_version += 1

        rango_seccion = next(
            (
                posicion
                for posicion, resultado in enumerate(resultados, start=1)
                if coincide_seccion(resultado, relevantes)
            ),
            None,
        )
        rango_documento = next(
            (
                posicion
                for posicion, resultado in enumerate(resultados, start=1)
                if coincide_documento(resultado, relevantes)
            ),
            None,
        )

        if rango_seccion is not None:
            suma_reciproca += 1.0 / rango_seccion

        for k in (1, 3, 5):
            if rango_documento is not None and rango_documento <= k:
                aciertos_documento[k] += 1
            if rango_seccion is not None and rango_seccion <= k:
                aciertos_seccion[k] += 1

        # Cobertura estricta: una consulta solo está completa si aparecen
        # todas las parejas (documento, sección) anotadas como objetivo.
        objetivos_seccion = {
            (objetivo["documento"], normalizar_seccion(seccion))
            for objetivo in relevantes
            for seccion in objetivo.get("secciones", [])
        }
        secciones_encontradas = {
            (
                documento_de(resultado.get("chunk_id", "")),
                normalizar_seccion(resultado.get("seccion")),
            )
            for resultado in resultados
        }
        secciones_cubiertas = objetivos_seccion.intersection(secciones_encontradas)
        secciones_objetivo_total += len(objetivos_seccion)
        secciones_encontradas_total += len(secciones_cubiertas)
        if objetivos_seccion and len(secciones_cubiertas) == len(objetivos_seccion):
            casos_cobertura_completa += 1

        # Cobertura exacta de consultas que exigen dos o más códigos CMP.
        componentes = sorted(codigos_componente(caso.get("consulta", "")))
        if len(componentes) >= 2:
            consultas_multi_cmp += 1
            encontrados: set[str] = set()
            for resultado in resultados:
                seccion = str(resultado.get("seccion") or "").strip()
                coincidencia = _PATRON_CODIGO_CMP_SECCION.fullmatch(seccion)
                if coincidencia:
                    encontrados.add(f"CMP-{coincidencia.group(1)}")

            exigidos_caso = set(componentes)
            cubiertos_caso = exigidos_caso.intersection(encontrados)
            componentes_exigidos_total += len(exigidos_caso)
            componentes_encontrados_total += len(cubiertos_caso)
            if len(cubiertos_caso) == len(exigidos_caso):
                consultas_multi_cmp_completas += 1

    return {
        "total": total,
        "documento": aciertos_documento,
        "seccion": aciertos_seccion,
        "mrr": suma_reciproca / total if total else 0.0,
        "sin_resultados": consultas_sin_resultados,
        "fugas_version": fugas_version,
        "secciones_objetivo": secciones_objetivo_total,
        "secciones_encontradas": secciones_encontradas_total,
        "casos_cobertura_completa": casos_cobertura_completa,
        "componentes_exigidos": componentes_exigidos_total,
        "componentes_encontrados": componentes_encontrados_total,
        "consultas_multi_cmp": consultas_multi_cmp,
        "consultas_multi_cmp_completas": consultas_multi_cmp_completas,
    }


def porcentaje(aciertos: int, total: int) -> str:
    return f"{100 * aciertos / total:.1f}% ({aciertos}/{total})" if total else "n/d"


def imprimir_metricas(nombre: str, metricas: dict[str, Any]) -> None:
    """Imprime el cuadro de métricas de una variante."""
    total = metricas["total"]
    print("\n" + "=" * 78)
    print(nombre)
    print("=" * 78)
    for k in (1, 3, 5):
        print(f"Documento@{k}: {porcentaje(metricas['documento'][k], total)}")
    for k in (1, 3, 5):
        print(f"Sección@{k}:   {porcentaje(metricas['seccion'][k], total)}")
    print(f"MRR sección@5: {metricas['mrr']:.3f}")
    print(f"Consultas sin resultados: {metricas['sin_resultados']}/{total}")
    print(f"Fugas de versión: {metricas['fugas_version']}")
    print(
        "Cobertura de secciones: "
        f"{metricas['secciones_encontradas']}/{metricas['secciones_objetivo']}"
    )
    print(
        "Consultas con cobertura completa: "
        f"{metricas['casos_cobertura_completa']}/{total}"
    )
    print(
        "Cobertura obligatoria CMP explícitos: "
        f"{metricas['componentes_encontrados']}/"
        f"{metricas['componentes_exigidos']}"
    )
    print(
        "Consultas multi-CMP completamente cubiertas: "
        f"{metricas['consultas_multi_cmp_completas']}/"
        f"{metricas['consultas_multi_cmp']}"
    )


def imprimir_diagnostico_casos(
    casos: list[dict[str, Any]],
    resultados_por_caso: dict[str, list[dict[str, Any]]],
    top_k: int,
) -> None:
    """Muestra el top_k por consulta y marca las secciones objetivo."""
    print("\n" + "-" * 78)
    print("DETALLE DE CASOS")
    print("-" * 78)

    for caso in casos:
        resultados = resultados_por_caso.get(caso["id"], [])[:top_k]
        relevantes = caso.get("relevantes", [])
        print(f"\n{caso['id']}")
        print(f"Consulta: {caso['consulta']}")

        for posicion, resultado in enumerate(resultados, start=1):
            documento = documento_de(resultado.get("chunk_id", ""))
            seccion = resultado.get("seccion") or "(sin sección)"
            marca = "OBJETIVO" if coincide_seccion(resultado, relevantes) else ""
            score = float(resultado.get("score", 0.0))
            rrf_score = resultado.get("rrf_score")
            rrf_texto = (
                f" | RRF={float(rrf_score):.6f}" if rrf_score is not None else ""
            )
            print(
                f" {posicion:>2}. {marca:<8} {documento} | {seccion} "
                f"| score={score:.3f}{rrf_texto}"
            )


def recuperar_ranking_completo(
    consulta: str,
    version: str,
    top_k_maximo: int,
) -> list[dict[str, Any]]:
    """Recupera candidatos sin que el límite de diversidad los recorte.

    Se cambia temporalmente el límite interno del recuperador para obtener el
    ranking completo de candidatos aplicables. La constante se restaura siempre,
    incluso si se produce una excepción. Después cada variante aplica su propia
    política de selección sobre la misma lista de candidatos.
    """
    limite_original = retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO
    try:
        retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = top_k_maximo
        return retrieval.buscar_fragmentos(
            consulta,
            version,
            top_k=top_k_maximo,
        )
    finally:
        retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = limite_original


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara variantes experimentales de reranking R03."
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=BENCHMARK_DEFAULT,
        help="JSON del benchmark (por defecto: benchmark_rag_v2.json).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de fragmentos que se comparan por consulta (por defecto: 5).",
    )
    args = parser.parse_args()

    if args.top_k < 5:
        parser.error("--top-k debe ser al menos 5 para calcular métricas hasta @5")
    if not args.benchmark.exists():
        parser.error(f"No se encuentra el benchmark: {args.benchmark}")

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    casos = benchmark.get("casos", [])
    if not casos:
        parser.error("El benchmark no contiene una lista 'casos'")

    validar_benchmark(casos)

    resultados_variantes: dict[str, dict[str, list[dict[str, Any]]]] = {
        "BASELINE": {},
        "INTENCION": {},
        "COMPONENTES": {},
        "INTENCION_INTERCALADA": {},
        "COMBINADA": {},
    }
    tiempos: list[float] = []

    print("=" * 78)
    print("EXPERIMENTO DE RERANKING R03 — THERMODRIVE")
    print("=" * 78)
    print(f"Base de datos: {retrieval.settings.db_path}")
    print(
        f"Chunk configurado: {retrieval.settings.rag_chunk_size}/"
        f"{retrieval.settings.rag_chunk_overlap}"
    )
    print(f"Fragmentos en BD: {len(RagChunkRepository().list_all())}")
    print(f"BM25 + RRF: {retrieval.settings.rag_hybrid_retrieval_enabled}")
    print(f"Anclaje CMP actual: {retrieval.settings.rag_component_anchor_enabled}")
    print(f"Consultas: {len(casos)} | top_k: {args.top_k}")
    print("No modifica retrieval.py, la configuración ni la base de datos.")
    print("=" * 78)

    # Se recupera una sola lista por consulta. Todas las variantes reciben los
    # mismos candidatos y así la comparación mide únicamente la selección.
    for indice, caso in enumerate(casos, start=1):
        caso_id = caso["id"]
        inicio = time.perf_counter()
        ranking = recuperar_ranking_completo(
            caso["consulta"],
            caso["version"],
            top_k_maximo=100_000,
        )
        tiempos.append(time.perf_counter() - inicio)
        print(f"Recuperando {indice}/{len(casos)}: {caso_id}")

        resultados_variantes["BASELINE"][caso_id] = seleccionar_baseline(
            ranking, args.top_k
        )
        resultados_variantes["INTENCION"][caso_id] = seleccionar_intencion(
            caso["consulta"], ranking, args.top_k
        )
        resultados_variantes["COMPONENTES"][caso_id] = seleccionar_componentes(
            caso["consulta"], ranking, args.top_k
        )
        resultados_variantes["INTENCION_INTERCALADA"][caso_id] = (
            seleccionar_intencion_intercalada(
                caso["consulta"],
                ranking,
                args.top_k,
            )
        )
        resultados_variantes["COMBINADA"][caso_id] = seleccionar_combinada(
            caso["consulta"],
            ranking,
            args.top_k,
        )

    metricas_variantes: dict[str, dict[str, Any]] = {}
    for nombre, resultados in resultados_variantes.items():
        metricas = calcular_metricas(casos, resultados, args.top_k)
        metricas_variantes[nombre] = metricas
        imprimir_metricas(nombre, metricas)

    print("\n" + "=" * 78)
    print("COMPARACIÓN FINAL")
    print("=" * 78)
    print(
        f"{'VARIANTE':<24} | {'Doc@5':<10} | {'Sección@5':<12} "
        f"| {'MRR':<7} | {'CMP cubiertos':<12}"
    )
    print("-" * 78)
    for nombre, metricas in metricas_variantes.items():
        print(
            f"{nombre:<24} | "
            f"{metricas['documento'][5]:>2}/{metricas['total']:<7} | "
            f"{metricas['seccion'][5]:>2}/{metricas['total']:<9} | "
            f"{metricas['mrr']:.3f}   | "
            f"{metricas['componentes_encontrados']}/"
            f"{metricas['componentes_exigidos']}"
        )

    for nombre, resultados in resultados_variantes.items():
        imprimir_diagnostico_casos(casos, resultados, args.top_k)
        if nombre != list(resultados_variantes)[-1]:
            print("\n" + "=" * 78)
            print(f"FIN DEL DETALLE: {nombre}")
            print("=" * 78)

    tiempo_medio = sum(tiempos) / len(tiempos) if tiempos else 0.0
    print("\n" + "=" * 78)
    print("RESUMEN DE EJECUCIÓN")
    print(f"Tiempo medio de recuperación: {tiempo_medio:.3f} s")
    print("Experimento terminado. No se ha modificado ningún archivo ni la BD.")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
