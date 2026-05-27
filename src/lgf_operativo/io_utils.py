"""Utilidades de lectura y exportacion para los modulos analiticos LGF.

Centraliza la resolucion de archivos y la escritura consistente de CSV/Excel
en carpetas generadas; dichas salidas no se deben editar manualmente.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

EXCEL_SHEETS_PRIORITY = [
    "estado_resumen",
    "perfil_cliente",
    "cliente_sku_operativo_resumen",
    "cliente_sku_operativo_composicion",
    "estructura_caja",
    "estructura_componentes",
    "catalogo_estructura_version",
    "cliente_semana_sku_operativo",
    "cliente_estructuras_repetidas",
    "cliente_semana_tipica",
    "clientes_similares",
    "clusters_clientes",
    "demanda_operativa_futura",
    "cruce_forecast_inventario",
    "ordenes_pendientes_reales",
    "estimados_comerciales_estructura",
    "forecast_modelo_estacional",
    "forecast_historico_confirmado",
    "solid_forecast_fuente_datos",
    "solid_forecast_model_evaluation",
    "solid_forecast_feature_importance",
    "solid_forecast_market_feature_importance",
    "solid_forecast_market_calibration",
    "solid_forecast_predictors",
    "solid_forecast_future_week",
    "solid_forecast_error_by_market",
    "solid_forecast_future_market_color",
    "solid_forecast_future",
    "mix_tipo_pedido",
    "mix_color",
    "mix_sku_terminado",
    "inventario_fecha_color",
    "inventario_fecha_item",
]


def resolve_path(path: str | Path | None, default_filename: str | None = None) -> Path | None:
    if path is None or str(path).strip() == "":
        return None
    p = Path(path)
    if p.is_dir():
        if default_filename and (p / default_filename).exists():
            return p / default_filename
        candidates = sorted(list(p.glob("*.csv")) + list(p.glob("*.txt")) + list(p.glob("*.xlsx")) + list(p.glob("*.xls")))
        if candidates:
            return candidates[0]
    return p


def read_table(path: str | Path, sheet: str | None = None) -> pd.DataFrame:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(p, sheet_name=sheet or 0)
    try:
        return pd.read_csv(p, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(p, encoding="latin-1", low_memory=False)
    except pd.errors.ParserError:
        return pd.read_csv(p, sep=None, engine="python", encoding="utf-8-sig")


def _safe_sheet_name(name: str, used: set[str]) -> str:
    base = name[:31]
    candidate = base
    i = 1
    while candidate in used:
        suffix = f"_{i}"
        candidate = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(candidate)
    return candidate


def write_outputs(
    outputs: dict[str, pd.DataFrame],
    output_dir: str | Path,
    excel_name: str = "LGF_MVP_Caracterizacion_Forecast.xlsx",
    csv_columns: dict[str, list[str]] | None = None,
    skip_csv: set[str] | None = None,
    write_excel: bool = True,
) -> Path:
    """Write complete CSV outputs and a light Excel workbook with key sheets.

    CSVs are the official complete outputs. The Excel workbook is capped for speed.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Complete CSV outputs.
    skip_csv = skip_csv or set()
    csv_columns = csv_columns or {}
    for name, df in outputs.items():
        if df is None or not isinstance(df, pd.DataFrame):
            continue
        if name in skip_csv:
            continue
        write_df = df
        if name in csv_columns:
            cols = [col for col in csv_columns[name] if col in df.columns]
            write_df = df[cols].copy() if cols else df
        write_df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")

    excel_path = out / excel_name
    if not write_excel:
        return excel_path
    used_sheet_names: set[str] = set()
    # xlsxwriter is much faster than openpyxl for writing large outputs.
    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        for name in EXCEL_SHEETS_PRIORITY:
            df = outputs.get(name)
            if df is None or not isinstance(df, pd.DataFrame):
                continue
            df_excel = df.head(50_000).copy()
            df_excel.to_excel(writer, sheet_name=_safe_sheet_name(name, used_sheet_names), index=False)
    return excel_path
