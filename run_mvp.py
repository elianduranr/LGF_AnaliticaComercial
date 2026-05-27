"""Ejecutor legado del MVP con inventario.

Se conserva para referencia y futuras fases de inventario. El flujo activo
actual usa ``run_descriptivos.py``, ``run_clusters.py`` y
``run_forecast_solidos.py`` por separado.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.lgf_operativo.pipeline import run_mvp_pipeline

DEFAULT_HISTORICO = str(Path("bases de datos historicas") / "historic_sales_acum.csv")
DEFAULT_INVENTARIO = r"C:\Users\elian\OneDrive - LA GAITANA FARMS SAS\Sincronizacion_PDA\basesBI\df_inventory_final.csv"


def parse_args():
    parser = argparse.ArgumentParser(
        description="MVP LGF: caracterización de clientes, demanda futura operativa y cruce con inventario."
    )
    parser.add_argument("--historico", default=DEFAULT_HISTORICO, help="Ruta del historico/ordenes CSV/TXT/XLSX.")
    parser.add_argument("--inventario", default=None, help="Ruta de df_inventory_final.csv o carpeta que lo contiene. Omitelo para regenerar solo caracterizacion/360 mas rapido.")
    parser.add_argument(
        "--output",
        default=str(Path("pruebas antiguas") / "outputs_baseline"),
        help="Carpeta de resultados del MVP legado, fuera del flujo analitico oficial.",
    )
    parser.add_argument("--historico-sheet", default=None, help="Hoja Excel del histórico, si aplica.")
    parser.add_argument("--inventario-sheet", default=None, help="Hoja Excel del inventario, si aplica.")
    parser.add_argument("--target-start", default=None, help="Fecha inicial forecast YYYY-MM-DD. Si se omite, usa día posterior al último histórico confirmado.")
    parser.add_argument("--target-end", default=None, help="Fecha final forecast YYYY-MM-DD.")
    parser.add_argument("--horizon-days", type=int, default=7, help="Días de forecast si no se indica target-end.")
    parser.add_argument("--lookback-weeks", type=int, default=8, help="Semanas recientes para baseline histórico.")
    parser.add_argument("--min-forecast-score", type=float, default=0, help="Score mínimo de cliente para incluir en forecast histórico.")
    parser.add_argument("--max-client-inactive-weeks", type=int, default=16, help="No proyecta clientes sin confirmados recientes en esta cantidad de semanas.")
    parser.add_argument("--min-recent-active-weeks", type=int, default=2, help="Semanas activas minimas dentro del lookback para proyectar forecast.")
    parser.add_argument(
        "--forecast-model",
        choices=["seasonal_boosting", "baseline"],
        default="baseline",
        help="Modelo para demanda operativa: baseline es rapido; seasonal_boosting corre el modelo estacional completo.",
    )
    parser.add_argument(
        "--no-use-pending-as-demand",
        action="store_true",
        help="Si lo activas, NO usa Pendiente como demanda futura oficial y deja solo el forecast histórico.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Oculta el progreso detallado por etapa en consola.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print("Iniciando pipeline LGF...", flush=True)
    print(f"- Historico: {args.historico}", flush=True)
    print(f"- Inventario: {args.inventario or 'sin inventario'}", flush=True)
    print(f"- Output: {args.output}", flush=True)
    print(
        f"- Forecast: {args.forecast_model}, lookback={args.lookback_weeks}w, "
        f"clientes activos <= {args.max_client_inactive_weeks}w",
        flush=True,
    )
    outputs = run_mvp_pipeline(
        historical_path=args.historico,
        inventory_path=args.inventario,
        output_dir=args.output,
        historical_sheet=args.historico_sheet,
        inventory_sheet=args.inventario_sheet,
        target_start=args.target_start,
        target_end=args.target_end,
        horizon_days=args.horizon_days,
        lookback_weeks=args.lookback_weeks,
        min_forecast_score=args.min_forecast_score,
        max_client_inactive_weeks=args.max_client_inactive_weeks,
        min_recent_active_weeks=args.min_recent_active_weeks,
        use_pending_as_demand=not args.no_use_pending_as_demand,
        forecast_model=args.forecast_model,
        show_progress=not args.no_progress,
    )
    print("\nProceso terminado. Archivos generados en:", Path(args.output).resolve())
    print("\nRegla de estados aplicada:")
    print("- Confirmado: histórico real despachado, usado para caracterización y forecast histórico.")
    print("- Pendiente: orden real futura del cliente, usada primero como demanda operativa futura.")
    print("- En proceso: estimado comercial, exportado aparte; no se mezcla con histórico real.")
    print("- Por verificar/Reproceso: cambios sobre confirmado, exportados aparte para control.")
    print(f"- Modelo de forecast para demanda: {args.forecast_model}. El baseline de mediana se conserva para comparación.")
    print("\nTablas generadas:")
    for name, df in outputs.items():
        print(f"- {name}: {df.shape[0]:,} filas x {df.shape[1]:,} columnas")
