"""Materializa agregados y resultados del Dash en SQL Server op_sales.

Uso:
    .\carac_clients\Scripts\python.exe materializar_op_sales_resultados_sql.py
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.lgf_operativo.op_sales_sql import get_connection


DESCRIPTIVE_RESULTS = {
    "perfil_cliente": "perfil_cliente.csv",
    "serie_cliente_semana": "serie_cliente_semana.csv",
    "mix_producto": "mix_producto.csv",
    "mix_color": "mix_color.csv",
    "mix_tipo_pedido": "mix_tipo_pedido.csv",
    "mix_sku_terminado": "mix_sku_terminado.csv",
    "mix_analisis_operativo": "mix_analisis_operativo.csv",
    "mix_color_rol": "mix_color_rol.csv",
    "estado_resumen": "estado_resumen.csv",
    "cliente_estructuras_repetidas": "cliente_estructuras_repetidas.csv",
    "cliente_semana_tipica": "cliente_semana_tipica.csv",
    "cliente_sku_operativo_resumen": "cliente_sku_operativo_resumen.csv",
    "cliente_sku_operativo_composicion": "cliente_sku_operativo_composicion.csv",
    "cliente_semana_sku_operativo": "cliente_semana_sku_operativo.csv",
    "ventas_producto_periodo": "ventas_producto_periodo.csv",
    "ventas_cliente_periodo": "ventas_cliente_periodo.csv",
    "ventas_caja_periodo": "ventas_caja_periodo.csv",
    "estructura_caja": "estructura_caja.csv",
    "estructura_componentes": "estructura_componentes.csv",
    "catalogo_estructura_version": "catalogo_estructura_version.csv",
}

FORECAST_RESULTS = {
    "solid_forecast_fuente_datos": "solid_forecast_fuente_datos.csv",
    "solid_forecast_model_evaluation": "solid_forecast_model_evaluation.csv",
    "solid_forecast_feature_importance": "solid_forecast_feature_importance.csv",
    "solid_forecast_market_feature_importance": "solid_forecast_market_feature_importance.csv",
    "solid_forecast_market_calibration": "solid_forecast_market_calibration.csv",
    "solid_forecast_predictors": "solid_forecast_predictors.csv",
    "solid_forecast_weekly_demand": "solid_forecast_weekly_demand.csv",
    "solid_forecast_test_predictions": "solid_forecast_test_predictions.csv",
    "solid_forecast_historical_validation": "solid_forecast_historical_validation.csv",
    "solid_forecast_future": "solid_forecast_future.csv",
    "solid_forecast_error_by_market": "solid_forecast_error_by_market.csv",
}


def quote_name(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def sql_type_for(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT NULL"
    if pd.api.types.is_float_dtype(series):
        return "FLOAT NULL"
    if pd.api.types.is_bool_dtype(series):
        return "BIT NULL"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "DATETIME2(0) NULL"
    sample = series.dropna().astype(str)
    max_len = int(sample.str.len().max()) if not sample.empty else 100
    if max_len <= 0:
        max_len = 100
    if max_len <= 4000:
        return f"NVARCHAR({min(max_len * 2, 4000)}) NULL"
    return "NVARCHAR(MAX) NULL"


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out = out.replace([np.inf, -np.inf], np.nan)
    for col in out.columns:
        if re.search(r"(fecha|date|week_start|started_at|finished_at)$", col, re.IGNORECASE):
            converted = pd.to_datetime(out[col], errors="coerce")
            if converted.notna().mean() > 0.7:
                out[col] = converted
    return out.astype(object).where(pd.notna(out), None)


def replace_table_from_csv(conn, table_name: str, path: Path, chunk_size: int = 5000) -> int:
    if not path.exists():
        print(f"- {table_name}: no existe {path}; se omite", flush=True)
        return 0
    print(f"- {table_name}: leyendo {path}", flush=True)
    frame = clean_frame(pd.read_csv(path, low_memory=False))
    cursor = conn.cursor()
    cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name};")
    cols = ", ".join(f"{quote_name(col)} {sql_type_for(frame[col])}" for col in frame.columns)
    cursor.execute(f"CREATE TABLE {table_name} ({cols});")
    if frame.empty:
        conn.commit()
        return 0
    col_sql = ", ".join(quote_name(col) for col in frame.columns)
    placeholders = ", ".join("?" for _ in frame.columns)
    insert_sql = f"INSERT INTO {table_name} ({col_sql}) VALUES ({placeholders})"
    cursor.fast_executemany = True
    rows = 0
    total = len(frame)
    batches = math.ceil(total / chunk_size)
    for batch_index, start in enumerate(range(0, total, chunk_size), start=1):
        batch = frame.iloc[start : start + chunk_size]
        cursor.executemany(insert_sql, list(batch.itertuples(index=False, name=None)))
        rows += len(batch)
        if batch_index == 1 or batch_index == batches or batch_index % 20 == 0:
            print(f"  {rows:,}/{total:,} filas", flush=True)
    conn.commit()
    return rows


def validate_date_text(value: str | None, label: str) -> str | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"{label} invalida: {value}. Usa formato YYYY-MM-DD.")
    return parsed.strftime("%Y-%m-%d")


def aggregate_tables_exist(conn) -> bool:
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT COUNT(*)
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE s.name = 'op_sales'
          AND t.name IN ('agg_sales_week_client_product', 'agg_client_sku_week')
        """
    ).fetchone()
    return bool(row and int(row[0]) == 2)


def create_aggregate_indexes(conn) -> None:
    cursor = conn.cursor()
    index_sql = [
        (
            "op_sales.agg_sales_week_client_product",
            "IX_agg_sales_week",
            "CREATE INDEX IX_agg_sales_week ON op_sales.agg_sales_week_client_product (anio, semana_iso);",
        ),
        (
            "op_sales.agg_sales_week_client_product",
            "IX_agg_sales_client_week",
            "CREATE INDEX IX_agg_sales_client_week ON op_sales.agg_sales_week_client_product (cod_cliente, anio, semana_iso);",
        ),
        (
            "op_sales.agg_sales_week_client_product",
            "IX_agg_sales_product_week",
            "CREATE INDEX IX_agg_sales_product_week ON op_sales.agg_sales_week_client_product (producto, anio, semana_iso);",
        ),
        (
            "op_sales.agg_sales_week_client_product",
            "IX_agg_sales_color_week",
            "CREATE INDEX IX_agg_sales_color_week ON op_sales.agg_sales_week_client_product (color, anio, semana_iso);",
        ),
        (
            "op_sales.agg_client_sku_week",
            "IX_agg_client_sku_client_week",
            "CREATE INDEX IX_agg_client_sku_client_week ON op_sales.agg_client_sku_week (cod_cliente, anio, semana_iso);",
        ),
        (
            "op_sales.agg_client_sku_week",
            "IX_agg_client_sku_client_sku",
            "CREATE INDEX IX_agg_client_sku_client_sku ON op_sales.agg_client_sku_week (cod_cliente, sku_operativo);",
        ),
        (
            "op_sales.agg_client_sku_week",
            "IX_agg_client_sku_product_color",
            "CREATE INDEX IX_agg_client_sku_product_color ON op_sales.agg_client_sku_week (producto, color, anio, semana_iso);",
        ),
    ]
    for table_name, index_name, create_sql in index_sql:
        cursor.execute(
            f"""
            IF OBJECT_ID('{table_name}', 'U') IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1
                    FROM sys.indexes
                    WHERE object_id = OBJECT_ID('{table_name}')
                      AND name = '{index_name}'
               )
            BEGIN
                {create_sql}
            END
            """
        )
    conn.commit()


def prepare_affected_weeks(conn, start_date: str | None, end_date: str | None) -> int:
    cursor = conn.cursor()
    cursor.execute("IF OBJECT_ID('tempdb..#affected_weeks') IS NOT NULL DROP TABLE #affected_weeks;")
    cursor.execute("CREATE TABLE #affected_weeks (anio INT NOT NULL, semana_iso INT NOT NULL);")
    filters = []
    params = []
    if start_date:
        filters.append("fecha >= ?")
        params.append(start_date)
    if end_date:
        filters.append("fecha <= ?")
        params.append(end_date)
    where = " WHERE " + " AND ".join(filters) if filters else ""
    cursor.execute(
        f"""
        INSERT INTO #affected_weeks (anio, semana_iso)
        SELECT DISTINCT anio, semana_iso
        FROM op_sales.fact_sales_line
        {where};
        """,
        *params,
    )
    row = cursor.execute("SELECT COUNT(*) FROM #affected_weeks;").fetchone()
    return int(row[0] or 0) if row else 0


def materialize_aggregates_full(conn, scoped_to_affected_weeks: bool = False) -> None:
    cursor = conn.cursor()
    scope_where = (
        "WHERE EXISTS (SELECT 1 FROM #affected_weeks w WHERE w.anio = f.anio AND w.semana_iso = f.semana_iso)"
        if scoped_to_affected_weeks
        else ""
    )
    print("Materializando op_sales.agg_sales_week_client_product", flush=True)
    cursor.execute(
        f"""
        IF OBJECT_ID('op_sales.agg_sales_week_client_product', 'U') IS NOT NULL
            DROP TABLE op_sales.agg_sales_week_client_product;

        SELECT
            anio,
            semana_iso,
            anio_semana,
            cod_cliente,
            MAX(cliente) AS cliente,
            MAX(NomCompania) AS NomCompania,
            MAX(pais) AS pais,
            tipo_pedido_operativo,
            COALESCE(
                NULLIF(MAX(tipo_orden_empaque), 'sin_info'),
                NULLIF(MAX(tipo_empaque), 'sin_info'),
                NULLIF(MAX(bulkbouquet), 'sin_info'),
                NULLIF(MAX(codempaque), 'sin_info'),
                tipo_pedido_operativo
            ) AS tipo_pedido_original,
            producto,
            color,
            MAX(moneda_original) AS moneda_original,
            CAST(SUM(COALESCE(tallos_confirmados, 0)) AS DECIMAL(20,4)) AS tallos_confirmados,
            CAST(SUM(COALESCE(tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_analisis,
            CAST(SUM(COALESCE(ventas_usd, 0)) AS DECIMAL(20,4)) AS ventas_usd,
            CAST(SUM(COALESCE(valor_total_original, 0)) AS DECIMAL(20,4)) AS valor_total_original,
            COUNT_BIG(*) AS lineas,
            COUNT(DISTINCT pedido) AS pedidos,
            COUNT(DISTINCT caja_operativa) AS cajas_ids,
            CAST(SUM(COALESCE(ventas_usd, 0)) / NULLIF(SUM(COALESCE(tallos_confirmados, 0)), 0) AS DECIMAL(18,6)) AS precio_usd_tallo
        INTO op_sales.agg_sales_week_client_product
        FROM op_sales.fact_sales_line AS f
        {scope_where}
        GROUP BY anio, semana_iso, anio_semana, cod_cliente, tipo_pedido_operativo, producto, color;
        """
    )
    print("Materializando op_sales.agg_client_sku_week", flush=True)
    cursor.execute(
        f"""
        IF OBJECT_ID('op_sales.agg_client_sku_week', 'U') IS NOT NULL
            DROP TABLE op_sales.agg_client_sku_week;

        SELECT
            MIN(fecha) AS fecha,
            anio,
            anio AS anio_iso,
            semana_iso,
            anio_semana,
            cod_cliente,
            MAX(cliente) AS cliente,
            MAX(NomCompania) AS NomCompania,
            MAX(pais) AS pais,
            tipo_pedido_operativo,
            MAX(familia_analisis_operativa) AS familia_analisis_operativa,
            CASE
                WHEN tipo_pedido_operativo = 'SOLIDO' AND TRY_CONVERT(DECIMAL(18,4), tallos_x_ramo) IS NOT NULL
                    THEN CONCAT(producto_color, '|', FORMAT(TRY_CONVERT(DECIMAL(18,4), tallos_x_ramo), '0.####'), '_tallos_ramo')
                ELSE sku_operativo
            END AS sku_operativo,
            producto,
            variedad,
            color,
            MAX(tipo_caja) AS tipo_caja,
            MAX(FORMAT(TRY_CONVERT(DECIMAL(18,4), tallos_x_ramo), '0.####')) AS tallos_x_ramo,
            MAX(capuchon) AS capuchon,
            MAX(comida) AS comida,
            MAX(empaque) AS empaque,
            MAX(caja_operativa) AS caja_operativa,
            MAX(subtipo_pedido_operativo) AS subtipo_pedido_operativo,
            MAX(tipo_orden_empaque) AS tipo_orden_empaque,
            MAX(tipo_empaque) AS tipo_empaque,
            MAX(receta) AS receta,
            MAX(codempaque) AS codempaque,
            MAX(bulkbouquet) AS bulkbouquet,
            MAX(moneda_original) AS moneda_original,
            MAX(sku_terminado) AS sku_terminado,
            MAX(sku_composicion) AS sku_composicion,
            MAX(receta_estructura_key) AS receta_estructura_key,
            MAX(receta_programa_key) AS receta_programa_key,
            MAX(receta_programa_tamano_key) AS receta_programa_tamano_key,
            MAX(producto_color) AS producto_color,
            CAST(SUM(COALESCE(tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_analisis,
            CAST(SUM(COALESCE(tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_pedidos,
            CAST(SUM(COALESCE(tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_historicos,
            CAST(SUM(COALESCE(tallos_confirmados, 0)) AS DECIMAL(20,4)) AS tallos_confirmados,
            CAST(SUM(COALESCE(ventas_usd, 0)) AS DECIMAL(20,4)) AS ventas_usd,
            CAST(SUM(COALESCE(valor_total_original, 0)) AS DECIMAL(20,4)) AS valor_total_original,
            COUNT(DISTINCT pedido) AS pedidos,
            COUNT(DISTINCT caja_operativa) AS cajas
        INTO op_sales.agg_client_sku_week
        FROM op_sales.fact_sales_line AS f
        {scope_where}
        GROUP BY
            anio,
            semana_iso,
            anio_semana,
            cod_cliente,
            tipo_pedido_operativo,
            CASE
                WHEN tipo_pedido_operativo = 'SOLIDO' AND TRY_CONVERT(DECIMAL(18,4), tallos_x_ramo) IS NOT NULL
                    THEN CONCAT(producto_color, '|', FORMAT(TRY_CONVERT(DECIMAL(18,4), tallos_x_ramo), '0.####'), '_tallos_ramo')
                ELSE sku_operativo
            END,
            producto,
            variedad,
            color;
        """
    )
    conn.commit()
    create_aggregate_indexes(conn)


def materialize_aggregates_incremental(conn, start_date: str, end_date: str) -> None:
    cursor = conn.cursor()
    affected_weeks = prepare_affected_weeks(conn, start_date, end_date)
    if affected_weeks <= 0:
        print(f"No hay semanas afectadas entre {start_date} y {end_date}; se omiten agregados.", flush=True)
        return
    print(f"Materializando agregados solo para {affected_weeks:,} semanas afectadas ({start_date} a {end_date})", flush=True)
    if not aggregate_tables_exist(conn):
        print("No existen ambos agregados; se crean solo con las semanas afectadas.", flush=True)
        materialize_aggregates_full(conn, scoped_to_affected_weeks=True)
        return

    print("Borrando semanas afectadas en op_sales.agg_sales_week_client_product", flush=True)
    cursor.execute(
        """
        DELETE target
        FROM op_sales.agg_sales_week_client_product AS target
        WHERE EXISTS (
            SELECT 1
            FROM #affected_weeks AS w
            WHERE w.anio = target.anio
              AND w.semana_iso = target.semana_iso
        );
        """
    )
    print(f"  filas eliminadas: {cursor.rowcount if cursor.rowcount != -1 else 'N/D'}", flush=True)
    print("Reinsertando semanas afectadas en op_sales.agg_sales_week_client_product", flush=True)
    cursor.execute(
        """
        INSERT INTO op_sales.agg_sales_week_client_product (
            anio, semana_iso, anio_semana, cod_cliente, cliente, NomCompania, pais,
            tipo_pedido_operativo, tipo_pedido_original, producto, color, moneda_original,
            tallos_confirmados, tallos_analisis, ventas_usd, valor_total_original,
            lineas, pedidos, cajas_ids, precio_usd_tallo
        )
        SELECT
            f.anio,
            f.semana_iso,
            f.anio_semana,
            f.cod_cliente,
            MAX(f.cliente) AS cliente,
            MAX(f.NomCompania) AS NomCompania,
            MAX(f.pais) AS pais,
            f.tipo_pedido_operativo,
            COALESCE(
                NULLIF(MAX(f.tipo_orden_empaque), 'sin_info'),
                NULLIF(MAX(f.tipo_empaque), 'sin_info'),
                NULLIF(MAX(f.bulkbouquet), 'sin_info'),
                NULLIF(MAX(f.codempaque), 'sin_info'),
                f.tipo_pedido_operativo
            ) AS tipo_pedido_original,
            f.producto,
            f.color,
            MAX(f.moneda_original) AS moneda_original,
            CAST(SUM(COALESCE(f.tallos_confirmados, 0)) AS DECIMAL(20,4)) AS tallos_confirmados,
            CAST(SUM(COALESCE(f.tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_analisis,
            CAST(SUM(COALESCE(f.ventas_usd, 0)) AS DECIMAL(20,4)) AS ventas_usd,
            CAST(SUM(COALESCE(f.valor_total_original, 0)) AS DECIMAL(20,4)) AS valor_total_original,
            COUNT_BIG(*) AS lineas,
            COUNT(DISTINCT f.pedido) AS pedidos,
            COUNT(DISTINCT f.caja_operativa) AS cajas_ids,
            CAST(SUM(COALESCE(f.ventas_usd, 0)) / NULLIF(SUM(COALESCE(f.tallos_confirmados, 0)), 0) AS DECIMAL(18,6)) AS precio_usd_tallo
        FROM op_sales.fact_sales_line AS f
        WHERE EXISTS (
            SELECT 1
            FROM #affected_weeks AS w
            WHERE w.anio = f.anio
              AND w.semana_iso = f.semana_iso
        )
        GROUP BY f.anio, f.semana_iso, f.anio_semana, f.cod_cliente, f.tipo_pedido_operativo, f.producto, f.color;
        """
    )
    print(f"  filas insertadas: {cursor.rowcount if cursor.rowcount != -1 else 'N/D'}", flush=True)

    print("Borrando semanas afectadas en op_sales.agg_client_sku_week", flush=True)
    cursor.execute(
        """
        DELETE target
        FROM op_sales.agg_client_sku_week AS target
        WHERE EXISTS (
            SELECT 1
            FROM #affected_weeks AS w
            WHERE w.anio = target.anio
              AND w.semana_iso = target.semana_iso
        );
        """
    )
    print(f"  filas eliminadas: {cursor.rowcount if cursor.rowcount != -1 else 'N/D'}", flush=True)
    print("Reinsertando semanas afectadas en op_sales.agg_client_sku_week", flush=True)
    cursor.execute(
        """
        INSERT INTO op_sales.agg_client_sku_week (
            fecha, anio, anio_iso, semana_iso, anio_semana, cod_cliente, cliente,
            NomCompania, pais, tipo_pedido_operativo, familia_analisis_operativa,
            sku_operativo, producto, variedad, color, tipo_caja, tallos_x_ramo,
            capuchon, comida, empaque, caja_operativa, subtipo_pedido_operativo,
            tipo_orden_empaque, tipo_empaque, receta, codempaque, bulkbouquet,
            moneda_original, sku_terminado, sku_composicion, receta_estructura_key,
            receta_programa_key, receta_programa_tamano_key, producto_color,
            tallos_analisis, tallos_pedidos, tallos_historicos, tallos_confirmados,
            ventas_usd, valor_total_original, pedidos, cajas
        )
        SELECT
            MIN(f.fecha) AS fecha,
            f.anio,
            f.anio AS anio_iso,
            f.semana_iso,
            f.anio_semana,
            f.cod_cliente,
            MAX(f.cliente) AS cliente,
            MAX(f.NomCompania) AS NomCompania,
            MAX(f.pais) AS pais,
            f.tipo_pedido_operativo,
            MAX(f.familia_analisis_operativa) AS familia_analisis_operativa,
            CASE
                WHEN f.tipo_pedido_operativo = 'SOLIDO' AND TRY_CONVERT(DECIMAL(18,4), f.tallos_x_ramo) IS NOT NULL
                    THEN CONCAT(f.producto_color, '|', FORMAT(TRY_CONVERT(DECIMAL(18,4), f.tallos_x_ramo), '0.####'), '_tallos_ramo')
                ELSE f.sku_operativo
            END AS sku_operativo,
            f.producto,
            f.variedad,
            f.color,
            MAX(f.tipo_caja) AS tipo_caja,
            MAX(FORMAT(TRY_CONVERT(DECIMAL(18,4), f.tallos_x_ramo), '0.####')) AS tallos_x_ramo,
            MAX(f.capuchon) AS capuchon,
            MAX(f.comida) AS comida,
            MAX(f.empaque) AS empaque,
            MAX(f.caja_operativa) AS caja_operativa,
            MAX(f.subtipo_pedido_operativo) AS subtipo_pedido_operativo,
            MAX(f.tipo_orden_empaque) AS tipo_orden_empaque,
            MAX(f.tipo_empaque) AS tipo_empaque,
            MAX(f.receta) AS receta,
            MAX(f.codempaque) AS codempaque,
            MAX(f.bulkbouquet) AS bulkbouquet,
            MAX(f.moneda_original) AS moneda_original,
            MAX(f.sku_terminado) AS sku_terminado,
            MAX(f.sku_composicion) AS sku_composicion,
            MAX(f.receta_estructura_key) AS receta_estructura_key,
            MAX(f.receta_programa_key) AS receta_programa_key,
            MAX(f.receta_programa_tamano_key) AS receta_programa_tamano_key,
            MAX(f.producto_color) AS producto_color,
            CAST(SUM(COALESCE(f.tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_analisis,
            CAST(SUM(COALESCE(f.tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_pedidos,
            CAST(SUM(COALESCE(f.tallos_analisis, 0)) AS DECIMAL(20,4)) AS tallos_historicos,
            CAST(SUM(COALESCE(f.tallos_confirmados, 0)) AS DECIMAL(20,4)) AS tallos_confirmados,
            CAST(SUM(COALESCE(f.ventas_usd, 0)) AS DECIMAL(20,4)) AS ventas_usd,
            CAST(SUM(COALESCE(f.valor_total_original, 0)) AS DECIMAL(20,4)) AS valor_total_original,
            COUNT(DISTINCT f.pedido) AS pedidos,
            COUNT(DISTINCT f.caja_operativa) AS cajas
        FROM op_sales.fact_sales_line AS f
        WHERE EXISTS (
            SELECT 1
            FROM #affected_weeks AS w
            WHERE w.anio = f.anio
              AND w.semana_iso = f.semana_iso
        )
        GROUP BY
            f.anio,
            f.semana_iso,
            f.anio_semana,
            f.cod_cliente,
            f.tipo_pedido_operativo,
            CASE
                WHEN f.tipo_pedido_operativo = 'SOLIDO' AND TRY_CONVERT(DECIMAL(18,4), f.tallos_x_ramo) IS NOT NULL
                    THEN CONCAT(f.producto_color, '|', FORMAT(TRY_CONVERT(DECIMAL(18,4), f.tallos_x_ramo), '0.####'), '_tallos_ramo')
                ELSE f.sku_operativo
            END,
            f.producto,
            f.variedad,
            f.color;
        """
    )
    print(f"  filas insertadas: {cursor.rowcount if cursor.rowcount != -1 else 'N/D'}", flush=True)
    conn.commit()
    create_aggregate_indexes(conn)


def materialize_aggregates(conn, start_date: str | None = None, end_date: str | None = None) -> None:
    start_date = validate_date_text(start_date, "--start-date")
    end_date = validate_date_text(end_date, "--end-date")
    if start_date and end_date and pd.to_datetime(start_date) > pd.to_datetime(end_date):
        raise ValueError("--start-date no puede ser mayor que --end-date.")
    if start_date or end_date:
        materialize_aggregates_incremental(conn, start_date or "1900-01-01", end_date or "9999-12-31")
    else:
        print("Sin rango recibido: materializando agregados con toda la historia.", flush=True)
        materialize_aggregates_full(conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materializa agregados y resultados Dash en SQL Server.")
    parser.add_argument("--start-date", default=None, help="Fecha inicial para actualizar solo semanas impactadas, formato YYYY-MM-DD.")
    parser.add_argument("--end-date", default=None, help="Fecha final para actualizar solo semanas impactadas, formato YYYY-MM-DD.")
    parser.add_argument("--descriptivos-dir", default="resultados/descriptivos")
    parser.add_argument("--forecast-dir", default="resultados/forecast_solidos")
    parser.add_argument("--skip-results", action="store_true")
    args = parser.parse_args()

    conn = get_connection()
    try:
        materialize_aggregates(conn, args.start_date, args.end_date)
        if args.skip_results:
            return
        descriptivos_dir = Path(args.descriptivos_dir)
        forecast_dir = Path(args.forecast_dir)
        for name, filename in DESCRIPTIVE_RESULTS.items():
            replace_table_from_csv(conn, f"op_sales.result_descriptivo_{name}", descriptivos_dir / filename)
        for name, filename in FORECAST_RESULTS.items():
            replace_table_from_csv(conn, f"op_sales.result_forecast_{name}", forecast_dir / filename)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
