"""Ejecutor del modulo descriptivo de clientes y SKUs operativos.

Lee el historico crudo local del proyecto y genera las tablas que consumen el
visualizador general y la vista resumida de estructuras. Los filtros
``--year`` y ``--years`` permiten analizar una ventana seleccionada sin
cambiar la fuente consolidada.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.lgf_operativo.descriptive import run_descriptive_pipeline


DEFAULT_HISTORICO = str(Path("bases de datos historicas") / "historic_sales_acum.csv")
DEFAULT_OUTPUT = str(Path("resultados") / "descriptivos")


def parse_args():
    parser = argparse.ArgumentParser(
        description="LGF: pipeline solo descriptivo para clientes, productos, historicos y SKUs operativos."
    )
    parser.add_argument("--historico", default=DEFAULT_HISTORICO, help="Ruta del historico/ordenes CSV/TXT/XLSX.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Carpeta donde se guardan descriptivos.")
    parser.add_argument(
        "--tipo-reference",
        default=None,
        help="Respaldo opcional para extractos incompletos sin campos de receta; no usar con la base completa.",
    )
    parser.add_argument("--historico-sheet", default=None, help="Hoja Excel del historico, si aplica.")
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument("--year", type=int, default=None, help="Filtra a un unico ano calendario, por ejemplo 2026.")
    time_group.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=None,
        help="Filtra a varios anos calendario, por ejemplo --years 2023 2024 2025 2026.",
    )
    parser.add_argument("--no-progress", action="store_true", help="Oculta progreso por etapa en consola.")
    parser.add_argument("--no-cache", action="store_true", help="Fuerza limpiar desde cero e ignora el cache local.")
    parser.add_argument(
        "--full-clean-csv",
        action="store_true",
        help="Escribe pedidos_limpios_todos_estados.csv completo. Es pesado; el Dash no lo necesita por defecto.",
    )
    parser.add_argument("--no-excel", action="store_true", help="No genera el Excel resumen; escribe solo CSVs.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print("Iniciando pipeline descriptivo LGF...", flush=True)
    print(f"- Historico: {args.historico}", flush=True)
    print(f"- Output: {args.output}", flush=True)
    if args.year is not None:
        print(f"- Ano analisis: {args.year}", flush=True)
    elif args.years:
        print(f"- Anos analisis: {', '.join(map(str, sorted(set(args.years))))}", flush=True)
    else:
        print("- Anos analisis: toda la historia disponible", flush=True)
    outputs = run_descriptive_pipeline(
        historical_path=args.historico,
        output_dir=args.output,
        historical_sheet=args.historico_sheet,
        show_progress=not args.no_progress,
        use_cache=not args.no_cache,
        write_full_clean_csv=args.full_clean_csv,
        write_excel=not args.no_excel,
        analysis_year=args.year,
        analysis_years=args.years,
        tipo_reference_path=args.tipo_reference,
    )
    print("\nProceso descriptivo terminado. Archivos generados en:", Path(args.output).resolve())
    print("\nTablas generadas:")
    for name, df in outputs.items():
        print(f"- {name}: {df.shape[0]:,} filas x {df.shape[1]:,} columnas")
