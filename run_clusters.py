"""Ejecutor del modulo de clusters de clientes dentro de mercados definidos.

El modulo consume un historico confirmado ya preparado por descriptivos y
exige ``--year``. Asi los clusters siempre se estiman con el ano elegido,
aunque el descriptivo disponible contenga varios anos.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.lgf_operativo.clustering import ClusterConfig, run_cluster_pipeline
from src.lgf_operativo.metrics import build_client_profile


DEFAULT_DESCRIPTIVE_DIR = str(Path("resultados") / "descriptivos")
DEFAULT_OUTPUT_ROOT = Path("resultados") / "clusters"

HIST_CLUSTER_COLS = [
    "fecha",
    "cod_cliente",
    "cliente",
    "pais",
    "pedido",
    "caja_id",
    "tipo_caja",
    "producto",
    "variedad",
    "color",
    "tipo_pedido_operativo",
    "empaque_operativo",
    "empaque",
    "sku_operativo",
    "sku_terminado",
    "sku_flexible",
    "estructura_pedido",
    "llave_analisis_operativo",
    "producto_color",
    "tallos_x_ramo",
    "ramos_x_caja",
    "tallos_analisis",
    "tallos_confirmados",
    "faltante_tallos",
    "ventas_usd",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LGF: modulo separado para clustering de clientes por mercado."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_DESCRIPTIVE_DIR,
        help="Carpeta con outputs descriptivos o historico_confirmado ya limpio.",
    )
    parser.add_argument(
        "--historico",
        default=None,
        help="CSV limpio confirmado. Si se omite, se busca historico_confirmado.csv o historico_confirmado_2026.csv en input-dir.",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Ano calendario obligatorio que se clusteriza, por ejemplo --year 2026.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Carpeta de salida anual. Si se omite, escribe automaticamente en resultados/clusters/<year>/.",
    )
    parser.add_argument("--max-k", type=int, default=6, help="K maximo probado por mercado.")
    parser.add_argument("--min-clients-market", type=int, default=4, help="Minimo de clientes para clusterizar un mercado.")
    parser.add_argument("--top-similar", type=int, default=10, help="Clientes similares exportados por cliente.")
    parser.add_argument("--no-excel", action="store_true", help="Solo escribe CSV; omite Excel.")
    return parser.parse_args()


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _resolve_historico(input_dir: Path, historico_arg: str | None) -> Path:
    hist_path = Path(historico_arg) if historico_arg else _first_existing(
        [
            input_dir / "historico_confirmado.csv",
            input_dir / "historico_confirmado_2026.csv",
            input_dir / "05_base_reporte_2026.csv",
            input_dir / "04_pedidos_limpios_2026.csv",
        ]
    )
    if hist_path is None or not hist_path.exists():
        raise FileNotFoundError(
            "No encontre historico confirmado. Usa --historico o pon historico_confirmado.csv en --input-dir."
        )
    return hist_path


def read_cluster_csv(path: Path, usecols: list[str] | None = None, parse_dates: list[str] | None = None) -> pd.DataFrame:
    """Lee un output descriptivo limitando columnas requeridas para clusters."""
    return pd.read_csv(
        path,
        usecols=lambda col: usecols is None or col in usecols,
        parse_dates=parse_dates,
        encoding="utf-8-sig",
        low_memory=False,
    )


if __name__ == "__main__":
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_ROOT / str(args.year)
    hist_path = _resolve_historico(input_dir, args.historico)
    print("Iniciando modulo de clusters LGF...", flush=True)
    print(f"- Historico limpio: {hist_path}", flush=True)
    print(f"- Ano clusterizado: {args.year}", flush=True)
    print("- Perfil cliente: recalculado exclusivamente con el ano seleccionado", flush=True)
    print(f"- Output: {output_dir}", flush=True)
    print("- Mercados: Estados Unidos/Canada, The Netherlands, Polonia, Asia, Otros", flush=True)
    print("- Metodos evaluados: K-medias, K-modas y jerarquico", flush=True)

    historico = read_cluster_csv(hist_path, HIST_CLUSTER_COLS, ["fecha"])
    historico = historico[historico["fecha"].dt.year.eq(int(args.year))].copy()
    if historico.empty:
        raise ValueError(f"No hay registros confirmados para clusterizar el ano {args.year}.")
    if "empaque_operativo" not in historico.columns:
        historico["empaque_operativo"] = historico.get("empaque", "sin_info")
    if "estructura_pedido" not in historico.columns:
        historico["estructura_pedido"] = historico["tipo_pedido_operativo"]
    if "sku_flexible" not in historico.columns:
        historico["sku_flexible"] = historico["sku_terminado"]
    if "producto_color" not in historico.columns:
        historico["producto_color"] = (
            historico["producto"].fillna("sin_producto").astype(str)
            + " | "
            + historico["color"].fillna("sin_color").astype(str)
        )
    iso = historico["fecha"].dt.isocalendar()
    historico["anio_semana"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    perfil = build_client_profile(historico)
    config = ClusterConfig(max_k=args.max_k, min_clients_market=args.min_clients_market)
    outputs = run_cluster_pipeline(
        historico_confirmado=historico,
        perfil_cliente=perfil,
        output_dir=None if args.no_excel else output_dir,
        config=config,
        top_similar=args.top_similar,
    )
    periodo = pd.DataFrame(
        [
            {
                "anio_cluster": int(args.year),
                "fecha_min": historico["fecha"].min(),
                "fecha_max": historico["fecha"].max(),
                "filas_confirmadas": int(len(historico)),
                "clientes": int(historico["cod_cliente"].nunique()),
            }
        ]
    )
    outputs["cluster_periodo_analisis"] = periodo
    out = output_dir
    out.mkdir(parents=True, exist_ok=True)
    periodo.to_csv(out / "cluster_periodo_analisis.csv", index=False, encoding="utf-8-sig")
    if args.no_excel:
        for name, df in outputs.items():
            df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")

    print("\nProceso de clusters terminado. Archivos generados en:", output_dir.resolve())
    print("\nTablas generadas:")
    for name, df in outputs.items():
        print(f"- {name}: {df.shape[0]:,} filas x {df.shape[1]:,} columnas")
