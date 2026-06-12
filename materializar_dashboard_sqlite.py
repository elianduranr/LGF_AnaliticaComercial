r"""Materializa una base SQLite ligera para Ventas Generales y Visualizador clientes.

Uso:
    .\carac_clients\Scripts\python.exe materializar_dashboard_sqlite.py

La base queda en resultados/dashboard_operativo.sqlite. No toca forecast.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path("resultados") / "descriptivos" / "historico_visualizador_comercial.csv"
DEFAULT_OUTPUT = Path("resultados") / "dashboard_operativo.sqlite"
DEFAULT_HISTORICAL = Path("bases de datos historicas") / "historic_sales_acum.csv"

USECOLS = [
    "fecha",
    "cod_cliente",
    "cliente",
    "NomCompania",
    "pais",
    "pedido",
    "anio",
    "semana_iso",
    "anio_semana",
    "tipo_pedido_operativo",
    "producto",
    "variedad",
    "color",
    "tipo_caja",
    "tallos_x_ramo",
    "capuchon",
    "comida",
    "empaque",
    "subtipo_pedido_operativo",
    "tipo_orden_empaque",
    "tipo_empaque",
    "receta",
    "codempaque",
    "bulkbouquet",
    "caja_operativa",
    "tallos_analisis",
    "tallos_confirmados",
    "ventas_usd",
    "valor_total_original",
    "moneda_original",
    "sku_operativo",
    "sku_terminado",
    "sku_composicion",
    "receta_estructura_key",
    "receta_programa_key",
    "receta_programa_tamano_key",
    "producto_color",
]


def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def load_company_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        mapping = pd.read_csv(path, usecols=["cod_cliente", "NomCompania"], low_memory=False)
    except ValueError:
        return {}
    mapping["cod_cliente"] = normalize_code(mapping["cod_cliente"])
    mapping["NomCompania"] = mapping["NomCompania"].fillna("").astype(str).str.strip()
    mapping = mapping[mapping["NomCompania"].ne("")]
    mapping = mapping.drop_duplicates("cod_cliente", keep="last")
    return dict(zip(mapping["cod_cliente"], mapping["NomCompania"]))


def prepare_chunk(chunk: pd.DataFrame, company_map: dict[str, str] | None = None) -> pd.DataFrame:
    out = chunk.copy()
    out["cod_cliente"] = normalize_code(out["cod_cliente"])
    for col in [
        "NomCompania", "pais", "variedad", "tipo_caja", "tallos_x_ramo", "capuchon", "comida",
        "empaque", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta",
        "codempaque", "bulkbouquet", "sku_terminado", "sku_composicion", "receta_estructura_key",
        "receta_programa_key", "receta_programa_tamano_key", "producto_color",
    ]:
        if col not in out.columns:
            out[col] = ""
    out["NomCompania"] = out["NomCompania"].fillna("").astype(str).str.strip()
    missing_company = out["NomCompania"].isin(["", "nan", "None", "none", "sin_info"])
    if company_map:
        mapped = out.loc[missing_company, "cod_cliente"].map(company_map)
        out.loc[missing_company, "NomCompania"] = mapped.fillna("").astype(str)
        missing_company = out["NomCompania"].isin(["", "nan", "None", "none", "sin_info"])
    out.loc[missing_company, "NomCompania"] = out.loc[missing_company, "cliente"].astype(str)
    for col in ["anio", "semana_iso", "tallos_analisis", "tallos_confirmados", "ventas_usd", "valor_total_original"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    if "anio" not in out.columns or out["anio"].eq(0).all():
        dates = pd.to_datetime(out["fecha"], errors="coerce")
        iso = dates.dt.isocalendar()
        out["anio"] = iso.year.astype("Int64").fillna(0).astype(int)
        out["semana_iso"] = iso.week.astype("Int64").fillna(0).astype(int)
    if "anio_semana" not in out.columns:
        out["anio_semana"] = out["anio"].astype(int).astype(str) + "-W" + out["semana_iso"].astype(int).astype(str).str.zfill(2)
    out["tallos_pedidos"] = out.get("tallos_analisis", out.get("tallos_confirmados", 0))
    return out.rename(columns={"tallos_analisis": "tallos_historicos"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--chunksize", type=int, default=250_000)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()

    con = sqlite3.connect(args.output)
    available_cols = pd.read_csv(args.input, nrows=0).columns.tolist()
    usecols = [col for col in USECOLS if col in available_cols]
    company_map = load_company_map(args.historical)
    if company_map:
        print(f"mapa NomCompania cargado: {len(company_map):,} clientes")

    total = 0
    for chunk in pd.read_csv(args.input, usecols=usecols, chunksize=args.chunksize, low_memory=False):
        prepared = prepare_chunk(chunk, company_map)
        prepared.to_sql("fact_ventas_dashboard", con, if_exists="append", index=False)
        total += len(prepared)
        print(f"filas cargadas: {total:,}")

    con.executescript(
        """
        CREATE INDEX idx_fact_semana ON fact_ventas_dashboard(anio, semana_iso);
        CREATE INDEX idx_fact_cliente ON fact_ventas_dashboard(cod_cliente, anio, semana_iso);
        CREATE INDEX idx_fact_pais ON fact_ventas_dashboard(pais, anio, semana_iso);
        CREATE INDEX idx_fact_producto ON fact_ventas_dashboard(producto, anio, semana_iso);
        CREATE INDEX idx_fact_sku ON fact_ventas_dashboard(sku_operativo, anio, semana_iso);

        CREATE VIEW vw_ventas_generales_semana_cliente_producto AS
        SELECT
            anio,
            semana_iso,
            anio_semana,
            cod_cliente,
            MAX(cliente) AS cliente,
            MAX(NomCompania) AS NomCompania,
            MAX(pais) AS pais,
            producto,
            MAX(moneda_original) AS moneda_original,
            SUM(tallos_confirmados) AS tallos_confirmados,
            SUM(ventas_usd) AS ventas_usd,
            SUM(valor_total_original) AS valor_total_original,
            COUNT(DISTINCT pedido) AS pedidos,
            COUNT(DISTINCT caja_operativa) AS cajas_ids,
            SUM(ventas_usd) / NULLIF(SUM(tallos_confirmados), 0) AS precio_usd_tallo,
            SUM(valor_total_original) / NULLIF(SUM(tallos_confirmados), 0) AS precio_moneda_original_tallo
        FROM fact_ventas_dashboard
        GROUP BY anio, semana_iso, anio_semana, cod_cliente, producto;

        CREATE VIEW vw_visualizador_cliente_sku_semana AS
        SELECT
            anio,
            semana_iso,
            anio_semana,
            cod_cliente,
            MAX(cliente) AS cliente,
            MAX(NomCompania) AS NomCompania,
            MAX(pais) AS pais,
            tipo_pedido_operativo,
            sku_operativo,
            producto,
            MAX(variedad) AS variedad,
            color,
            MAX(tipo_caja) AS tipo_caja,
            MAX(tallos_x_ramo) AS tallos_x_ramo,
            MAX(capuchon) AS capuchon,
            MAX(comida) AS comida,
            MAX(empaque) AS empaque,
            MAX(subtipo_pedido_operativo) AS subtipo_pedido_operativo,
            MAX(tipo_orden_empaque) AS tipo_orden_empaque,
            MAX(tipo_empaque) AS tipo_empaque,
            MAX(receta) AS receta,
            MAX(codempaque) AS codempaque,
            MAX(bulkbouquet) AS bulkbouquet,
            MAX(caja_operativa) AS caja_operativa,
            MAX(sku_terminado) AS sku_terminado,
            MAX(sku_composicion) AS sku_composicion,
            MAX(receta_estructura_key) AS receta_estructura_key,
            MAX(receta_programa_key) AS receta_programa_key,
            MAX(receta_programa_tamano_key) AS receta_programa_tamano_key,
            MAX(producto_color) AS producto_color,
            SUM(tallos_confirmados) AS tallos_confirmados,
            SUM(tallos_pedidos) AS tallos_pedidos,
            SUM(ventas_usd) AS ventas_usd,
            COUNT(DISTINCT pedido) AS pedidos,
            COUNT(DISTINCT caja_operativa) AS cajas,
            SUM(ventas_usd) / NULLIF(SUM(tallos_confirmados), 0) AS precio_usd_tallo,
            SUM(tallos_confirmados) / NULLIF(SUM(tallos_pedidos), 0) AS cumplimiento
        FROM fact_ventas_dashboard
        GROUP BY anio, semana_iso, anio_semana, cod_cliente, tipo_pedido_operativo, sku_operativo, producto, color;
        """
    )
    con.close()
    print(f"base creada: {args.output}")


if __name__ == "__main__":
    main()
