"""Audita cuatro consultas con problemas sin modificar la BD ni el recuperador.

Ejecutar desde la raíz del proyecto:
    python backend/evaluation/auditar_cuatro_consultas.py
    python backend/evaluation/auditar_cuatro_consultas.py --top-k 50

La auditoría desactiva temporalmente, solo en este proceso, el límite de dos
fragmentos por documento para mostrar el ranking bruto. No cambia retrieval.py,
la base de datos ni la configuración persistente.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import retrieval  # noqa: E402

CASOS: list[dict[str, Any]] = [
    {
        "id": "BOL-001-INTERVALO-BOMBA",
        "version": "V1.0",
        "consulta": "Para un ThermoDrive V1.0, ¿cada cuánto hay que verificar el caudal de la bomba auxiliar A?",
        "objetivos": {
            "HTM240-BOL-001.pdf": ["Contenido"],
        },
    },
    {
        "id": "TES-05-ALTA-TENSION",
        "version": "V2.0",
        "consulta": "Se ha encendido el testigo rojo TES-05. ¿Qué significa y qué precaución debe tomarse?",
        "objetivos": {
            "HTM240-ADV-001_Testigos_y_mensajes.pdf": [
                "1. Testigos del sistema ThermoDrive",
                "3. Posibles combinaciones de testigos",
                "4. Acciones inmediatas recomendadas por nivel de urgencia",
            ],
            "HTM240-SEG-001_Manual_seguridad.pdf": ["5. Alta tensión"],
        },
    },
    {
        "id": "PRC-003-FLUJO-BAJO",
        "version": "V2.0",
        "consulta": "La bomba auxiliar A funciona, pero el caudal del circuito de batería es bajo. ¿Qué comprobación permite detectar si el filtro está obstruido?",
        "objetivos": {
            "HTM240-PRC-003_Verificacion_de_la_bomba_electrica_auxiliar_A_(circuito_de_bateria).pdf": [
                "Pasos",
                "Acción si el resultado no es correcto",
            ],
            "HTM240-PRC-011_Sustitucion_del_filtro_del_circuito_de_bateria.pdf": [
                "Pasos",
                "Valores esperados",
            ],
        },
    },
    {
        "id": "ESQ-ARQUITECTURA",
        "version": "V2.0",
        "consulta": "¿Cómo se organiza el sistema ThermoDrive en sus tres circuitos térmicos y qué papel tiene la TCU?",
        "objetivos": {
            "HTM240-ESQ-001_Esquemas_tecnicos.pdf": [
                "1. Diagrama de arquitectura general",
                "5. Relación entre sensores, actuadores y TCU",
            ],
            "HTM240-MAN-001_Manual_general.pdf": [
                "1. Objetivo del sistema",
                "2. Arquitectura funcional",
                "7. Interacción con la Unidad de Control Térmico",
            ],
        },
    },
]


def documento_de(chunk_id: str) -> str:
    return chunk_id.rsplit("_", 1)[0]


def es_objetivo(resultado: dict[str, Any], objetivos: dict[str, list[str]]) -> bool:
    documento = documento_de(resultado["chunk_id"])
    return documento in objetivos and resultado.get("seccion") in objetivos[documento]


def imprimir_resultado(posicion: int, resultado: dict[str, Any], objetivo: bool) -> None:
    marca = "OBJETIVO" if objetivo else "       "
    texto = " ".join((resultado.get("texto") or "").split())
    if len(texto) > 210:
        texto = texto[:207] + "..."
    print(
        f"  {posicion:02d}. [{marca}] {documento_de(resultado['chunk_id'])}"
        f" | {resultado.get('seccion')} | pág. {resultado.get('pagina')}"
        f" | score={float(resultado['score']):.3f}"
        f" | ranking={float(resultado['ranking_score']):.3f}"
    )
    if objetivo:
        print(f"      TEXTO: {texto}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita cuatro consultas del benchmark ThermoDrive.")
    parser.add_argument("--top-k", type=int, default=50, help="Número de resultados brutos (por defecto: 50).")
    args = parser.parse_args()
    if args.top_k < 5:
        parser.error("--top-k debe ser al menos 5")

    limite_original = retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO
    retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = args.top_k + 1
    try:
        print("=" * 92)
        print("AUDITORÍA DE CUATRO CONSULTAS — RANKING BRUTO SIN LÍMITE POR DOCUMENTO")
        print("La modificación del límite solo vive durante este proceso; no altera archivos ni BD.")
        print("=" * 92)

        for caso in CASOS:
            resultados = retrieval.buscar_fragmentos(
                caso["consulta"], caso["version"], args.top_k
            )
            posiciones_objetivo = [
                (i, resultado)
                for i, resultado in enumerate(resultados, start=1)
                if es_objetivo(resultado, caso["objetivos"])
            ]

            print(f"\n{caso['id']} [{caso['version']}]")
            print(f"Consulta: {caso['consulta']}")
            print(f"Resultados recibidos: {len(resultados)}")
            if posiciones_objetivo:
                print("Posiciones de secciones objetivo:", ", ".join(str(i) for i, _ in posiciones_objetivo))
            else:
                print(f"No aparece ninguna sección objetivo entre los {args.top_k} resultados.")

            print("\nPrimeros 12 resultados:")
            for posicion, resultado in enumerate(resultados[:12], start=1):
                imprimir_resultado(posicion, resultado, es_objetivo(resultado, caso["objetivos"]))

            objetivos_mostrados = {
                resultado["chunk_id"] for _, resultado in posiciones_objetivo
            }
            ya_impresos = {r["chunk_id"] for r in resultados[:12]}
            restantes = [
                (i, r) for i, r in posiciones_objetivo if r["chunk_id"] not in ya_impresos
            ]
            if restantes:
                print("\nSecciones objetivo que aparecen después de la posición 12:")
                for posicion, resultado in restantes:
                    imprimir_resultado(posicion, resultado, True)

    finally:
        retrieval._MAX_FRAGMENTOS_POR_DOCUMENTO = limite_original

    print("\nAuditoría terminada. No se ha modificado la base de datos ni ningún archivo del proyecto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
