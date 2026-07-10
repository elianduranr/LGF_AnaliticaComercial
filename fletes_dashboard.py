"""Vista descriptiva de fletes desde la tabla operativa de Gaitana.

La fuente `Venta.Fletes_Distribuidos` ya trae ventas, tallos y fletes al nivel
distribuido de producto/color. Esta vista no cruza contra otras paginas del
dashboard; resume directamente esa tabla para evitar descuadres.
"""

from __future__ import annotations

import os
import sys
import unicodedata
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table, dcc, html

from src.lgf_operativo.local_env import load_local_credentials
from src.lgf_operativo.op_sales_sql import get_connection


FREIGHT_TABLE_CANDIDATES = [
    ("Venta", "Fletes_Distribuidos"),
    ("Ventas", "Fletes_Distribuidoos"),
    ("Ventas", "Fletes_Distribuidos"),
]


@lru_cache(maxsize=1)
def get_client_negotiation_term_map() -> dict[str, str]:
    """Return the latest visible freight/negotiation term by client."""
    load_local_credentials()
    try:
        with get_connection() as con:
            resolved = _resolve_freight_table(con)
            if resolved is None:
                return {}
            schema, table = resolved
            frame = pd.read_sql_query(
                f"""
                SELECT
                    CAST(CODCUSTOM AS varchar(80)) AS cod_cliente,
                    CAST(Tipo_Flete AS nvarchar(120)) AS termino_negociacion,
                    COUNT_BIG(*) AS frecuencia
                FROM [{schema}].[{table}]
                WHERE NULLIF(LTRIM(RTRIM(CAST(CODCUSTOM AS varchar(80)))), '') IS NOT NULL
                  AND NULLIF(LTRIM(RTRIM(CAST(Tipo_Flete AS nvarchar(120)))), '') IS NOT NULL
                GROUP BY CAST(CODCUSTOM AS varchar(80)), CAST(Tipo_Flete AS nvarchar(120))
                """,
                con,
            )
    except Exception as exc:
        print(f"No se pudieron cargar terminos de negociacion: {exc}", file=sys.stderr, flush=True)
        return {}
    if frame.empty:
        return {}
    frame["cod_cliente"] = frame["cod_cliente"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    frame["termino_negociacion"] = frame["termino_negociacion"].fillna("Sin dato").astype(str).str.strip().str.upper()
    frame["frecuencia"] = pd.to_numeric(frame["frecuencia"], errors="coerce").fillna(0)
    best = frame.sort_values(["cod_cliente", "frecuencia"], ascending=[True, False]).drop_duplicates("cod_cliente")
    return dict(zip(best["cod_cliente"], best["termino_negociacion"]))


def _selected_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _selected_label(value: Any, default: str = "todos") -> str:
    values = _selected_values(value)
    if not values:
        return default
    if len(values) <= 2:
        return ", ".join(values)
    return f"{len(values)} seleccionados"


def _ascii_upper_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .map(lambda value: unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii"))
        .str.upper()
    )


def _fmt(value: Any, decimals: int = 0) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        numeric = 0
    return f"{float(numeric):,.{decimals}f}"


def _usd(value: Any) -> str:
    return f"${_fmt(value, 2)}"


def _usd_unit(value: Any) -> str:
    return _fmt(value, 4)


def _stems(value: Any) -> str:
    return _fmt(value, 0)


def _rate(value: Any) -> str:
    return _fmt(value, 4)


def _pct(value: Any) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return "0.0%"
    return f"{float(numeric) * 100:,.1f}%"


def _card(label: str, value: str, sub: str = ""):
    return html.Div(
        [
            html.Div(label, className="metric-label"),
            html.Div(value, className="metric-value"),
            html.Div(sub, className="metric-subtitle"),
        ],
        className="metric-card",
    )


def _mini_insight(text: str):
    return html.Div(text, className="metric-card")


def _section(title: str, subtitle: str = ""):
    return html.Div(
        [
            html.Div(title, className="executive-kicker"),
            html.Div(subtitle, className="metric-subtitle") if subtitle else None,
        ],
        className="section-gap",
    )


def _table(frame: pd.DataFrame, rows: int = 12):
    if frame.empty:
        return html.Div("Sin datos para mostrar con los filtros actuales.", className="empty-state")
    numeric_cols = {
        col
        for col in frame.columns
        if pd.api.types.is_numeric_dtype(frame[col]) and not str(col).lower().startswith("ano")
    }
    return dash_table.DataTable(
        data=frame.to_dict("records"),
        columns=[
            {"name": col, "id": col, "type": "numeric"} if col in numeric_cols else {"name": col, "id": col}
            for col in frame.columns
        ],
        page_size=rows,
        sort_action="native",
        filter_action="native",
        export_format="csv",
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": "Arial", "fontSize": 12, "padding": "8px", "textAlign": "left"},
        style_header={"fontWeight": "700", "backgroundColor": "#f5f7fa"},
    )


def _empty_figure(title: str):
    fig = px.scatter(title=title)
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": "Sin datos",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 14, "color": "#687385"},
            }
        ],
        height=330,
        margin=dict(l=20, r=20, t=55, b=25),
    )
    return fig


def _resolve_freight_table(con) -> tuple[str, str] | None:
    for schema, table in FREIGHT_TABLE_CANDIDATES:
        found = pd.read_sql_query(
            """
            SELECT 1 AS found
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
            """,
            con,
            params=[schema, table],
        )
        if not found.empty:
            return schema, table
    return None


def _in_clause(column: str, values: list[str], params: list[Any]) -> str:
    selected = _selected_values(values)
    if not selected:
        return ""
    params.extend(selected)
    placeholders = ", ".join("?" for _ in selected)
    return f" AND CAST({column} AS varchar(500)) IN ({placeholders})"


def _append_filter(filters: list[str], params: list[Any], column: str, values: list[str] | None) -> None:
    clause = _in_clause(column, values or [], params)
    if clause:
        filters.append(clause.replace(" AND ", "", 1))


def _first_existing_column(con, schema: str, table: str, candidates: list[str]) -> str | None:
    columns = pd.read_sql_query(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """,
        con,
        params=[schema, table],
    )
    if columns.empty:
        return None
    by_upper = {str(col).upper(): str(col) for col in columns["COLUMN_NAME"]}
    for candidate in candidates:
        found = by_upper.get(candidate.upper())
        if found:
            return found
    return None


def _freight_type_columns(con, schema: str, table: str) -> dict[str, str]:
    candidates = {
        "tipo_pedido_operativo_raw": [
            "PRESENTACION",
            "Presentacion",
            "Presentación",
            "PRESENTACIÓN",
            "presentacion",
            "tipo_pedido_operativo",
            "TIPO_PEDIDO_OPERATIVO",
            "Tipo_Pedido_Operativo",
        ],
        "tipo_orden_empaque_raw": ["TIPORDENEMPAQUE", "TipoOrdenEmpaque", "Tipo_Orden_Empaque", "tipo_orden_empaque"],
        "tipo_empaque_raw": ["TIPOEMPAQUE", "Tipo_Empaque", "tipo_empaque"],
        "empaque_raw": ["EMPAQUE", "empaque"],
        "receta_raw": ["RECETA", "receta"],
        "bulkbouquet_raw": ["BULKBOUQUET", "BulkBouquet", "bulkbouquet"],
        "codempaque_raw": ["CODEMPAQUE", "CodEmpaque", "codempaque"],
    }
    found: dict[str, str] = {}
    for alias, names in candidates.items():
        col = _first_existing_column(con, schema, table, names)
        if col:
            found[alias] = col
    return found


def _normalize_freight_order_type(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="object")
    direct = frame.get("tipo_pedido_operativo_raw", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip()
    direct_upper = _ascii_upper_text(direct)
    usable_direct = ~direct_upper.isin({"", "NAN", "NONE", "SIN DATO", "SIN_DATO"})
    text = pd.Series("", index=frame.index, dtype="object")
    for col in [
        "tipo_orden_empaque_raw",
        "tipo_empaque_raw",
        "empaque_raw",
        "receta_raw",
        "bulkbouquet_raw",
        "codempaque_raw",
    ]:
        if col in frame.columns:
            text = text.str.cat(frame[col].fillna("").astype(str), sep=" ")
    raw = _ascii_upper_text(text)
    out = pd.Series("Sin dato", index=frame.index, dtype="object")
    out = out.mask(raw.str.contains("RAINBOW", regex=False, na=False), "RAINBOW")
    out = out.mask(raw.str.contains("COMBO", regex=False, na=False), "COMBO")
    out = out.mask(raw.str.contains("BOUQUET|\\bBQT\\b", regex=True, na=False), "BOUQUET")
    out = out.mask(raw.str.contains("SURTIDO", regex=False, na=False), "SURTIDO_M")
    out = out.mask(raw.str.contains("BULK", regex=False, na=False), "BULK")
    out = out.mask(raw.str.contains("SOLIDO|SOLID", regex=True, na=False), "SOLIDO")
    direct_clean = direct_upper.str.replace(r"\s+", "_", regex=True)
    direct_clean = direct_clean.mask(direct_upper.str.contains("RAINBOW", regex=False, na=False), "RAINBOW")
    direct_clean = direct_clean.mask(direct_upper.str.contains("COMBO", regex=False, na=False), "COMBO")
    direct_clean = direct_clean.mask(direct_upper.str.contains("BOUQUET|\\bBQT\\b", regex=True, na=False), "BOUQUET")
    direct_clean = direct_clean.mask(direct_upper.str.contains("SURTIDO", regex=False, na=False), "SURTIDO_M")
    direct_clean = direct_clean.mask(direct_upper.str.contains("BULK", regex=False, na=False), "BULK")
    direct_clean = direct_clean.mask(direct_upper.str.contains("SOLIDO|SOLID", regex=True, na=False), "SOLIDO")
    out = out.mask(usable_direct, direct_clean)
    return out


def _read_freight_scope(
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
    order_types: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    load_local_credentials(override=True)
    os.environ["OP_SALES_USE_SQL_SERVER"] = "1"
    with get_connection() as con:
        resolved = _resolve_freight_table(con)
        if resolved is None:
            return pd.DataFrame(), {"error": "No encontre la tabla de fletes en SQL."}
        schema, table = resolved
        type_columns = _freight_type_columns(con, schema, table)
        type_select_expr = ""
        type_group_expr = ""
        if type_columns:
            type_select_expr = "".join(
                f",\n                CAST([{col}] AS nvarchar(500)) AS {alias}"
                for alias, col in type_columns.items()
            )
            type_group_expr = "".join(
                f",\n                CAST([{col}] AS nvarchar(500))"
                for col in type_columns.values()
            )

        filters = ["NULLIF(LTRIM(RTRIM(CAST(INVOICE AS varchar(120)))), '') IS NOT NULL"]
        params: list[Any] = []

        selected_years = [int(year) for year in _selected_values(years) if str(year).strip().isdigit()]
        if selected_years:
            placeholders = ", ".join("?" for _ in selected_years)
            filters.append(f"ANO IN ({placeholders})")
            params.extend(selected_years)
        if week_range and len(week_range) == 2:
            filters.append("SEMANA BETWEEN ? AND ?")
            params.extend([int(week_range[0]), int(week_range[1])])
        _append_filter(filters, params, "CODCUSTOM", clients)
        _append_filter(filters, params, "PAIS", countries)
        _append_filter(filters, params, "NomCompania", companies)
        _append_filter(filters, params, "PRODUCTO", products)
        _append_filter(filters, params, "COLOR", colors)

        where = " AND ".join(filters)
        sql = f"""
            SELECT
                ANO AS anio,
                SEMANA AS semana_iso,
                CAST(INVOICE AS varchar(120)) AS invoice,
                CAST(CODCUSTOM AS varchar(80)) AS cod_cliente,
                CAST(CLIENTE AS nvarchar(500)) AS cliente,
                CAST(NomCompania AS nvarchar(500)) AS NomCompania,
                CAST(PAIS AS nvarchar(250)) AS pais,
                CAST(PRODUCTO AS nvarchar(250)) AS producto,
                CAST(COLOR AS nvarchar(250)) AS color,
                CAST(VARIEDAD AS nvarchar(500)) AS variedad,
                CAST(TIPCAJA AS nvarchar(120)) AS tipo_caja
                {type_select_expr},
                CAST(Tipo_Flete AS nvarchar(120)) AS tipo_flete,
                CAST(Tipo_Transporte_cif AS varchar(120)) AS tipo_transporte_cif,
                CAST(Clase_cif AS varchar(120)) AS clase_cif,
                CAST(Agencia_Carga_cif AS varchar(250)) AS agencia_carga_cif,
                CAST(Tipo_Transporte_del AS varchar(120)) AS tipo_transporte_del,
                CAST(Clase_del AS varchar(120)) AS clase_del,
                CAST(Agencia_Carga_del AS varchar(250)) AS agencia_carga_del,
                SUM(COALESCE(CAST(TallosConfirmados AS float), 0)) AS tallos_confirmados,
                SUM(COALESCE(CAST(VENTAS_USD AS float), 0)) AS ventas_usd,
                SUM(COALESCE(CAST(Total_Factura_cif AS float), 0)) AS total_factura_cif,
                SUM(COALESCE(CAST(Total_Factura_del AS float), 0)) AS total_factura_del,
                SUM(COALESCE(CAST(Total_Flete AS float), 0)) AS total_flete,
                COALESCE(
                    SUM(COALESCE(CAST(Rate_cif AS float), 0) * COALESCE(CAST(Total_Factura_cif AS float), 0))
                    / NULLIF(SUM(COALESCE(CAST(Total_Factura_cif AS float), 0)), 0),
                    0
                ) AS rate_cif,
                COALESCE(
                    SUM(COALESCE(CAST(Rate_del AS float), 0) * COALESCE(CAST(Total_Factura_del AS float), 0))
                    / NULLIF(SUM(COALESCE(CAST(Total_Factura_del AS float), 0)), 0),
                    0
                ) AS rate_del,
                MAX(CAST(Num_Factura_cif AS varchar(120))) AS num_factura_cif,
                MAX(CAST(Num_Factura_del AS varchar(120))) AS num_factura_del,
                COUNT_BIG(*) AS lineas_flete,
                COUNT(DISTINCT CAST(PEDIDO AS varchar(120))) AS pedidos
            FROM [{schema}].[{table}]
            WHERE {where}
            GROUP BY
                ANO,
                SEMANA,
                CAST(INVOICE AS varchar(120)),
                CAST(CODCUSTOM AS varchar(80)),
                CAST(CLIENTE AS nvarchar(500)),
                CAST(NomCompania AS nvarchar(500)),
                CAST(PAIS AS nvarchar(250)),
                CAST(PRODUCTO AS nvarchar(250)),
                CAST(COLOR AS nvarchar(250)),
                CAST(VARIEDAD AS nvarchar(500)),
                CAST(TIPCAJA AS nvarchar(120)){type_group_expr},
                CAST(Tipo_Flete AS nvarchar(120)),
                CAST(Tipo_Transporte_cif AS varchar(120)),
                CAST(Clase_cif AS varchar(120)),
                CAST(Agencia_Carga_cif AS varchar(250)),
                CAST(Tipo_Transporte_del AS varchar(120)),
                CAST(Clase_del AS varchar(120)),
                CAST(Agencia_Carga_del AS varchar(250))
        """
        out = pd.read_sql_query(sql, con, params=params)

    if out.empty:
        return pd.DataFrame(), {"table": f"{schema}.{table}", "error": ""}
    for col in [
        "tallos_confirmados",
        "ventas_usd",
        "total_factura_cif",
        "total_factura_del",
        "total_flete",
        "rate_cif",
        "rate_del",
    ]:
        out[col] = pd.to_numeric(out.get(col, 0), errors="coerce").fillna(0)

    out["flete_cif_distribuido"] = out["total_factura_cif"]
    out["flete_del_distribuido"] = out["total_factura_del"]
    out["flete_total_distribuido"] = out["total_flete"]
    out["precio_fob_estimado"] = out["ventas_usd"] - out["total_flete"]
    out["flete_por_tallo"] = out["total_flete"] / out["tallos_confirmados"].replace(0, np.nan)
    out["precio_fob_por_tallo"] = out["precio_fob_estimado"] / out["tallos_confirmados"].replace(0, np.nan)
    out["precio_venta_por_tallo"] = out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)
    out["tiene_flete"] = out["total_flete"].ne(0)
    out["tipo_pedido_operativo"] = _normalize_freight_order_type(out)
    for col in [
        "cliente",
        "NomCompania",
        "pais",
        "producto",
        "color",
        "variedad",
        "tipo_caja",
        "tipo_pedido_operativo",
        "tipo_flete",
        "tipo_transporte_cif",
        "clase_cif",
        "agencia_carga_cif",
        "tipo_transporte_del",
        "clase_del",
        "agencia_carga_del",
    ]:
        if col in out.columns:
            out[col] = out[col].fillna("Sin dato").astype(str).replace({"": "Sin dato", "None": "Sin dato", "nan": "Sin dato"})

    selected_types = set(_selected_values(order_types))
    if selected_types and "tipo_pedido_operativo" in out.columns:
        out = out[out["tipo_pedido_operativo"].astype(str).isin(selected_types)].copy()

    stats = {
        "table": f"{schema}.{table}",
        "tipo_pedido_source": ", ".join(type_columns.values()) if type_columns else "no disponible",
        "invoices_fletes": int(out["invoice"].nunique()),
        "invoices_con_flete": int(out.loc[out["tiene_flete"], "invoice"].nunique()),
        "error": "",
    }
    return out, stats


def _aggregate(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work["_rate_cif_weight"] = work["rate_cif"] * work["flete_cif_distribuido"]
    work["_rate_del_weight"] = work["rate_del"] * work["flete_del_distribuido"]
    negotiation_term = _ascii_upper_text(work.get("tipo_flete", pd.Series("", index=work.index))).str.strip()
    has_cif_term = negotiation_term.str.contains(r"(?:^|[^A-Z])CIF(?:[^A-Z]|$)", regex=True, na=False)
    has_del_term = negotiation_term.str.contains(r"(?:^|[^A-Z])DEL(?:[^A-Z]|$)", regex=True, na=False)
    # DEL includes the international CIF leg plus the final-delivery leg.
    work["_tallos_cif"] = np.where(
        (has_cif_term | has_del_term) & work["flete_cif_distribuido"].gt(0),
        work["tallos_confirmados"],
        0,
    )
    work["_tallos_del"] = np.where(
        has_del_term & work["flete_del_distribuido"].gt(0),
        work["tallos_confirmados"],
        0,
    )
    grouped = work.groupby(group_cols, dropna=False, as_index=False).agg(
        tallos=("tallos_confirmados", "sum"),
        tallos_cif=("_tallos_cif", "sum"),
        tallos_del=("_tallos_del", "sum"),
        ventas_usd=("ventas_usd", "sum"),
        flete_cif=("flete_cif_distribuido", "sum"),
        flete_del=("flete_del_distribuido", "sum"),
        flete_total=("flete_total_distribuido", "sum"),
        precio_fob=("precio_fob_estimado", "sum"),
        rate_cif_num=("_rate_cif_weight", "sum"),
        rate_del_num=("_rate_del_weight", "sum"),
        facturas=("invoice", "nunique"),
        lineas=("lineas_flete", "sum"),
    )
    grouped["rate_cif_prom"] = grouped["rate_cif_num"] / grouped["flete_cif"].replace(0, np.nan)
    grouped["rate_del_prom"] = grouped["rate_del_num"] / grouped["flete_del"].replace(0, np.nan)
    grouped["flete_x_tallo"] = grouped["flete_total"] / grouped["tallos"].replace(0, np.nan)
    grouped["cif_x_tallo"] = grouped["flete_cif"] / grouped["tallos_cif"].replace(0, np.nan)
    grouped["del_x_tallo"] = grouped["flete_del"] / grouped["tallos_del"].replace(0, np.nan)
    grouped["flete_pct_venta"] = grouped["flete_total"] / grouped["ventas_usd"].replace(0, np.nan)
    grouped["precio_fob_x_tallo"] = grouped["precio_fob"] / grouped["tallos"].replace(0, np.nan)
    grouped["precio_venta_x_tallo"] = grouped["ventas_usd"] / grouped["tallos"].replace(0, np.nan)
    grouped = grouped.drop(columns=["rate_cif_num", "rate_del_num"])
    return grouped.replace([np.inf, -np.inf], np.nan).fillna(0)


def get_sales_freight_summary(
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
    order_types: list[str] | None = None,
) -> pd.DataFrame:
    """Return annual freight totals aligned with General Sales filters.

    Freight is aggregated from its distributed SQL source before it is joined
    to sales KPIs, avoiding a many-to-many line-level merge.
    """
    # The card only needs annual totals. Avoid the detailed freight query unless
    # an operational-type filter requires its normalization logic.
    if not _selected_values(order_types):
        try:
            load_local_credentials(override=True)
            os.environ["OP_SALES_USE_SQL_SERVER"] = "1"
            with get_connection() as con:
                resolved = _resolve_freight_table(con)
                if resolved is None:
                    return pd.DataFrame()
                schema, table = resolved
                filters = ["NULLIF(LTRIM(RTRIM(CAST(INVOICE AS varchar(120)))), '') IS NOT NULL"]
                params: list[Any] = []
                selected_years = [int(year) for year in _selected_values(years) if str(year).strip().isdigit()]
                if selected_years:
                    placeholders = ", ".join("?" for _ in selected_years)
                    filters.append(f"ANO IN ({placeholders})")
                    params.extend(selected_years)
                if week_range and len(week_range) == 2:
                    filters.append("SEMANA BETWEEN ? AND ?")
                    params.extend([int(week_range[0]), int(week_range[1])])
                _append_filter(filters, params, "NomCompania", companies)
                _append_filter(filters, params, "CODCUSTOM", clients)
                _append_filter(filters, params, "PAIS", countries)
                _append_filter(filters, params, "PRODUCTO", products)
                _append_filter(filters, params, "COLOR", colors)
                where = " AND ".join(filters)
                fast = pd.read_sql_query(
                    f"""
                    SELECT
                        ANO AS anio,
                        UPPER(LTRIM(RTRIM(CAST(Tipo_Flete AS nvarchar(120))))) AS terminos_flete,
                        SUM(COALESCE(CAST(TallosConfirmados AS float), 0)) AS tallos,
                        SUM(CASE WHEN
                            (UPPER(CAST(Tipo_Flete AS nvarchar(120))) LIKE '%CIF%'
                             OR UPPER(CAST(Tipo_Flete AS nvarchar(120))) LIKE '%DEL%')
                            AND COALESCE(CAST(Total_Factura_cif AS float), 0) > 0
                            THEN COALESCE(CAST(TallosConfirmados AS float), 0) ELSE 0 END) AS tallos_cif,
                        SUM(CASE WHEN
                            UPPER(CAST(Tipo_Flete AS nvarchar(120))) LIKE '%DEL%'
                            AND COALESCE(CAST(Total_Factura_del AS float), 0) > 0
                            THEN COALESCE(CAST(TallosConfirmados AS float), 0) ELSE 0 END) AS tallos_del,
                        SUM(COALESCE(CAST(VENTAS_USD AS float), 0)) AS ventas_usd,
                        SUM(COALESCE(CAST(Total_Factura_cif AS float), 0)) AS flete_cif,
                        SUM(COALESCE(CAST(Total_Factura_del AS float), 0)) AS flete_del,
                        SUM(COALESCE(CAST(Total_Flete AS float), 0)) AS flete_total,
                        COUNT(DISTINCT CAST(INVOICE AS varchar(120))) AS facturas
                    FROM [{schema}].[{table}]
                    WHERE {where}
                    GROUP BY ANO, UPPER(LTRIM(RTRIM(CAST(Tipo_Flete AS nvarchar(120)))))
                    """,
                    con,
                    params=params,
                )
            if fast.empty:
                return pd.DataFrame()
            numeric = ["tallos", "tallos_cif", "tallos_del", "ventas_usd", "flete_cif", "flete_del", "flete_total", "facturas"]
            for col in numeric:
                fast[col] = pd.to_numeric(fast[col], errors="coerce").fillna(0)
            terms = fast.groupby("anio")["terminos_flete"].agg(
                lambda values: ", ".join(sorted({str(value).strip() for value in values if str(value).strip()}))
            )
            summary = fast.groupby("anio", as_index=False)[numeric].sum()
            summary["cif_x_tallo"] = summary["flete_cif"] / summary["tallos_cif"].replace(0, np.nan)
            summary["del_x_tallo"] = summary["flete_del"] / summary["tallos_del"].replace(0, np.nan)
            summary["flete_x_tallo"] = summary["flete_total"] / summary["tallos"].replace(0, np.nan)
            summary["precio_fob"] = summary["ventas_usd"] - summary["flete_total"]
            summary["precio_fob_x_tallo"] = summary["precio_fob"] / summary["tallos"].replace(0, np.nan)
            return summary.merge(terms.rename("terminos_flete").reset_index(), on="anio", how="left").replace([np.inf, -np.inf], np.nan).fillna(0)
        except Exception as exc:
            print(f"Fallo resumen rapido de fletes; usando detalle: {exc}", file=sys.stderr, flush=True)

    try:
        frame, _ = _read_freight_scope(
            years, week_range, companies, clients, countries, products, colors, order_types
        )
    except Exception as exc:
        print(f"No se pudo resumir flete para Ventas generales: {exc}", file=sys.stderr, flush=True)
        return pd.DataFrame()
    if frame.empty:
        return pd.DataFrame()
    summary = _aggregate(frame, ["anio"])
    terms = (
        frame.groupby("anio", dropna=False)["tipo_flete"]
        .agg(lambda values: ", ".join(sorted({str(value).strip().upper() for value in values if str(value).strip()})))
        .rename("terminos_flete")
        .reset_index()
    )
    return summary.merge(terms, on="anio", how="left")


def _display(
    frame: pd.DataFrame,
    group_cols: list[str],
    rows: int = 20,
    sort_col: str = "flete_total",
    min_tallos: float | None = None,
) -> pd.DataFrame:
    rename = {
        "anio": "Ano",
        "semana_iso": "Semana",
        "NomCompania": "Compania",
        "cod_cliente": "Cod. cliente",
        "cliente": "Cliente",
        "pais": "Pais",
        "producto": "Producto",
        "color": "Color",
        "tipo_caja": "Tipo caja",
        "tipo_pedido_operativo": "Tipo operativo",
        "tipo_flete": "Tipo flete",
        "tipo_transporte_cif": "Transporte CIF",
        "clase_cif": "Clase CIF",
        "agencia_carga_cif": "Agencia CIF",
        "tipo_transporte_del": "Transporte DEL",
        "clase_del": "Clase DEL",
        "agencia_carga_del": "Agencia DEL",
        "tallos": "Tallos CIF/DEL",
        "tallos_cif": "Tallos CIF",
        "tallos_del": "Tallos DEL",
        "ventas_usd": "Valor factura USD",
        "flete_cif": "Total Flete CIF",
        "flete_del": "Total Flete DEL",
        "flete_total": "Total Flete",
        "flete_x_tallo": "Flete x tallo CIF/DEL",
        "cif_x_tallo": "CIF x tallo",
        "del_x_tallo": "DEL x tallo",
        "flete_pct_venta": "% flete/venta",
        "precio_fob": "Precio FOB estimado",
        "precio_fob_x_tallo": "FOB x tallo",
        "precio_venta_x_tallo": "Venta x tallo",
        "rate_cif_prom": "Rate CIF pond.",
        "rate_del_prom": "Rate DEL pond.",
        "facturas": "Facturas",
        "lineas": "Lineas",
    }
    aggregated = _aggregate(frame, group_cols)
    if aggregated.empty:
        return pd.DataFrame()
    if min_tallos is not None and "tallos" in aggregated.columns:
        aggregated = aggregated[aggregated["tallos"].ge(float(min_tallos))].copy()
        if aggregated.empty:
            return pd.DataFrame()
    sort_col = sort_col if sort_col in aggregated.columns else "flete_total"
    out = aggregated.sort_values(sort_col, ascending=False).head(rows).rename(columns=rename)
    ordered = [rename.get(col, col) for col in group_cols] + [
        "Facturas",
        "Lineas",
        "Tallos CIF/DEL",
        "Tallos CIF",
        "Tallos DEL",
        "Valor factura USD",
        "Total Flete CIF",
        "Total Flete DEL",
        "Total Flete",
        "Flete x tallo CIF/DEL",
        "CIF x tallo",
        "DEL x tallo",
        "% flete/venta",
        "Precio FOB estimado",
        "FOB x tallo",
        "Rate CIF pond.",
        "Rate DEL pond.",
    ]
    out = out[[col for col in ordered if col in out.columns]].copy()
    for col in out.columns:
        if col == "% flete/venta":
            out[col] = pd.to_numeric(out[col], errors="coerce").map(_pct)
        elif col in {"Ano", "Semana", "Facturas", "Lineas", "Tallos CIF/DEL", "Tallos CIF", "Tallos DEL"}:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(0)
        elif col not in {"Compania", "Cod. cliente", "Cliente", "Pais", "Producto", "Color", "Tipo caja", "Tipo operativo", "Tipo flete", "Transporte CIF", "Clase CIF", "Agencia CIF", "Transporte DEL", "Clase DEL", "Agencia DEL"}:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(4)
    return out


def _freight_applicable(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "tipo_flete" not in frame.columns:
        return frame.copy()
    tipo = frame["tipo_flete"].fillna("Sin dato").astype(str).str.strip().str.upper()
    excluded = {"", "FOB", "NAL", "NAN", "NONE", "SIN DATO", "SIN_DATO"}
    flete = pd.to_numeric(frame.get("flete_total_distribuido", pd.Series(0, index=frame.index)), errors="coerce").fillna(0)
    return frame[~tipo.isin(excluded) & flete.gt(0)].copy()


def _min_volume(frame: pd.DataFrame) -> float:
    total = float(pd.to_numeric(frame.get("tallos_confirmados", pd.Series(dtype=float)), errors="coerce").sum())
    return max(1000.0, total * 0.01)


def _top_metric(frame: pd.DataFrame, group_cols: list[str], metric: str, ascending: bool = False) -> pd.Series | None:
    grouped = _aggregate(frame, group_cols)
    if grouped.empty or metric not in grouped.columns:
        return None
    grouped = grouped[grouped["tallos"].ge(_min_volume(frame))].copy()
    if grouped.empty:
        return None
    return grouped.sort_values(metric, ascending=ascending).iloc[0]


def _row_label(row: pd.Series | None, cols: list[str]) -> str:
    if row is None:
        return "Sin dato"
    parts = [str(row.get(col, "")).strip() for col in cols if str(row.get(col, "")).strip()]
    return " | ".join(parts) if parts else "Sin dato"


def _freight_insight_cards(applicable: pd.DataFrame, weekly: pd.DataFrame):
    if applicable.empty:
        return [
            html.Div("No hay flete aplicable para construir insights.", className="strategy-card")
        ]
    company_high = _top_metric(applicable, ["NomCompania"], "flete_x_tallo", ascending=False)
    company_low = _top_metric(applicable, ["NomCompania"], "flete_x_tallo", ascending=True)
    client_high = _top_metric(applicable, ["cod_cliente", "cliente"], "flete_pct_venta", ascending=False)
    product_high = _top_metric(applicable, ["producto"], "flete_x_tallo", ascending=False)
    box_high = _top_metric(applicable, ["tipo_caja"], "flete_x_tallo", ascending=False)

    trend_text = "Sin tendencia semanal suficiente."
    if not weekly.empty and len(weekly) >= 2:
        first = weekly.sort_values(["anio", "semana_iso"]).iloc[0]
        last = weekly.sort_values(["anio", "semana_iso"]).iloc[-1]
        start = float(first.get("flete_x_tallo", 0) or 0)
        end = float(last.get("flete_x_tallo", 0) or 0)
        delta = (end / start - 1) if start else 0
        trend_text = f"La tarifa por tallo pasa de {_fmt(start, 4)} a {_fmt(end, 4)} ({_pct(delta)})."

    cards = [
        f"Compania mas costosa por tallo: {_row_label(company_high, ['NomCompania'])} ({_fmt(company_high.get('flete_x_tallo', 0) if company_high is not None else 0, 4)} USD/tallo).",
        f"Compania mas eficiente comparable: {_row_label(company_low, ['NomCompania'])} ({_fmt(company_low.get('flete_x_tallo', 0) if company_low is not None else 0, 4)} USD/tallo).",
        f"Cliente con mayor presion de flete sobre venta: {_row_label(client_high, ['cod_cliente', 'cliente'])} ({_pct(client_high.get('flete_pct_venta', 0) if client_high is not None else 0)}).",
        f"Producto mas caro de mover por tallo: {_row_label(product_high, ['producto'])} ({_fmt(product_high.get('flete_x_tallo', 0) if product_high is not None else 0, 4)} USD/tallo).",
        f"Tipo de caja mas caro por tallo: {_row_label(box_high, ['tipo_caja'])} ({_fmt(box_high.get('flete_x_tallo', 0) if box_high is not None else 0, 4)} USD/tallo).",
        trend_text,
    ]
    return [_mini_insight(text) for text in cards[:4]]


def _scatter_figure(frame: pd.DataFrame, group_cols: list[str], label_col: str, title: str):
    grouped = _aggregate(frame, group_cols)
    if grouped.empty:
        return _empty_figure(title)
    grouped = grouped[grouped["tallos"].ge(_min_volume(frame))].copy()
    if grouped.empty:
        return _empty_figure(title)
    fig = px.scatter(
        grouped,
        x="ventas_usd",
        y="flete_x_tallo",
        size="tallos",
        color=label_col if label_col in grouped.columns else None,
        hover_data=["flete_total", "flete_pct_venta", "facturas"],
        title=title,
    )
    fig.update_layout(height=360, margin=dict(l=25, r=20, t=55, b=45), xaxis_title="Ventas USD CIF/DEL", yaxis_title="Flete CIF/DEL USD/tallo")
    return fig


def _add_period_axis(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or not {"anio", "semana_iso"}.issubset(frame.columns):
        return frame.copy()
    out = frame.copy()
    year = pd.to_numeric(out["anio"], errors="coerce").fillna(0).astype(int)
    week = pd.to_numeric(out["semana_iso"], errors="coerce").fillna(0).astype(int)
    out["period_order"] = year * 100 + week
    out["periodo"] = year.astype(str) + "-W" + week.astype(str).str.zfill(2)
    return out.sort_values("period_order")


def _fob_evolution_frame(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    weekly = _aggregate(frame, ["anio", "semana_iso"])
    weekly = _add_period_axis(weekly)
    if weekly.empty:
        return weekly
    weekly["serie"] = label
    return weekly


CARD_STYLE = {
    "background": "#FFFFFF",
    "border": "1px solid #E5E7EB",
    "borderRadius": "8px",
    "boxShadow": "0 1px 3px rgba(15, 23, 42, 0.08)",
    "padding": "14px",
}

GRID_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
    "gap": "12px",
}

SECTION_STYLE = {"marginTop": "18px"}


def _risk_status(pct_value: float) -> tuple[str, str, str]:
    if pct_value <= 0.18:
        return "Saludable", "#15803D", "#DCFCE7"
    if pct_value <= 0.23:
        return "Atencion", "#B45309", "#FEF3C7"
    return "Critico", "#B91C1C", "#FEE2E2"


def _section_header(title: str, subtitle: str = ""):
    return html.Div(
        [
            html.H3(title, style={"margin": "0", "fontSize": "18px", "color": "#111827"}),
            html.Div(subtitle, style={"color": "#6B7280", "fontSize": "13px", "marginTop": "3px"}) if subtitle else None,
        ],
        style={"margin": "0 0 10px 0"},
    )


def _fletes_kpi_card(title: str, value: str, detail: str, status: str = "", color: str = "#4F46E5", bg: str = "#EEF2FF"):
    return html.Div(
        [
            html.Div(title, style={"fontSize": "12px", "fontWeight": "700", "color": "#6B7280", "textTransform": "uppercase"}),
            html.Div(value, style={"fontSize": "26px", "fontWeight": "800", "color": "#111827", "marginTop": "6px"}),
            html.Div(detail, style={"fontSize": "12px", "color": "#4B5563", "marginTop": "4px", "lineHeight": "1.35"}),
            html.Div(status, style={"display": "inline-block", "marginTop": "10px", "padding": "4px 8px", "borderRadius": "999px", "background": bg, "color": color, "fontSize": "11px", "fontWeight": "700"}) if status else None,
        ],
        style={**CARD_STYLE, "borderTop": f"3px solid {color}"},
    )


def _small_insight(text: str, tone: str = "neutral"):
    colors = {
        "good": ("#15803D", "#F0FDF4"),
        "warn": ("#B45309", "#FFFBEB"),
        "bad": ("#B91C1C", "#FEF2F2"),
        "neutral": ("#374151", "#F9FAFB"),
    }
    color, bg = colors.get(tone, colors["neutral"])
    return html.Div(text, style={**CARD_STYLE, "background": bg, "color": color, "fontSize": "13px", "lineHeight": "1.45"})


def _calculate_fletes_kpis(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {}
    total_tallos = float(pd.to_numeric(frame["tallos_confirmados"], errors="coerce").fillna(0).sum())
    total_ventas = float(pd.to_numeric(frame["ventas_usd"], errors="coerce").fillna(0).sum())
    total_cif = float(pd.to_numeric(frame["flete_cif_distribuido"], errors="coerce").fillna(0).sum())
    total_del = float(pd.to_numeric(frame["flete_del_distribuido"], errors="coerce").fillna(0).sum())
    total_flete = total_cif + total_del
    tallos_cif = float(frame.loc[pd.to_numeric(frame["flete_cif_distribuido"], errors="coerce").fillna(0).gt(0), "tallos_confirmados"].sum())
    tallos_del = float(frame.loc[pd.to_numeric(frame["flete_del_distribuido"], errors="coerce").fillna(0).gt(0), "tallos_confirmados"].sum())
    fob = total_ventas - total_flete
    rate_cif_den = float(frame["flete_cif_distribuido"].sum())
    rate_del_den = float(frame["flete_del_distribuido"].sum())
    rate_cif_pond = float((frame["rate_cif"] * frame["flete_cif_distribuido"]).sum() / rate_cif_den) if rate_cif_den else 0
    rate_del_pond = float((frame["rate_del"] * frame["flete_del_distribuido"]).sum() / rate_del_den) if rate_del_den else 0
    return {
        "total_tallos": total_tallos,
        "tallos_cif": tallos_cif,
        "tallos_del": tallos_del,
        "total_ventas": total_ventas,
        "total_cif": total_cif,
        "total_del": total_del,
        "total_flete": total_flete,
        "flete_x_tallo": total_flete / total_tallos if total_tallos else 0,
        "cif_x_tallo": total_cif / tallos_cif if tallos_cif else 0,
        "del_x_tallo": total_del / tallos_del if tallos_del else 0,
        "rate_cif_pond": rate_cif_pond,
        "rate_del_pond": rate_del_pond,
        "pct_flete_venta": total_flete / total_ventas if total_ventas else 0,
        "precio_fob": fob,
        "fob_x_tallo": fob / total_tallos if total_tallos else 0,
        "facturas": float(frame["invoice"].nunique()) if "invoice" in frame.columns else 0,
        "lineas": float(pd.to_numeric(frame.get("lineas_flete", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
    }


def _data_quality(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {}
    rows = max(len(frame), 1)
    tipo = frame.get("tipo_pedido_operativo", pd.Series("Sin dato", index=frame.index)).fillna("Sin dato").astype(str).str.upper()
    agencia = frame.get("agencia_carga_cif", pd.Series("Sin dato", index=frame.index)).fillna("Sin dato").astype(str).str.upper()
    transporte = frame.get("tipo_transporte_cif", pd.Series("Sin dato", index=frame.index)).fillna("Sin dato").astype(str).str.upper()
    pais = frame.get("pais", pd.Series("Sin dato", index=frame.index)).fillna("Sin dato").astype(str).str.upper()
    tallos = pd.to_numeric(frame.get("tallos_confirmados", pd.Series(dtype=float)), errors="coerce").fillna(0)
    flete = pd.to_numeric(frame.get("flete_total_distribuido", pd.Series(dtype=float)), errors="coerce").fillna(0)
    venta = pd.to_numeric(frame.get("ventas_usd", pd.Series(dtype=float)), errors="coerce").fillna(0)
    missing_values = {"", "NAN", "NONE", "SIN DATO", "SIN_DATO"}
    return {
        "rows": float(rows),
        "tipo_sin_dato": float(tipo.isin(missing_values).sum()),
        "agencia_sin_dato": float(agencia.isin(missing_values).sum()),
        "transporte_sin_dato": float(transporte.isin(missing_values).sum()),
        "pais_sin_dato": float(pais.isin(missing_values).sum()),
        "flete_sin_tallos": float((flete.gt(0) & tallos.le(0)).sum()),
        "venta_sin_flete": float((venta.gt(0) & flete.le(0)).sum()),
        "facturas": float(frame["invoice"].nunique()) if "invoice" in frame.columns else 0,
    }


def _quality_card(frame: pd.DataFrame):
    q = _data_quality(frame)
    if not q:
        return _small_insight("Sin datos para evaluar calidad.", "warn")
    rows = q["rows"]
    lines = [
        f"Tipo operativo sin dato: {_stems(q['tipo_sin_dato'])} ({_pct(q['tipo_sin_dato'] / rows)})",
        f"Agencia CIF sin dato: {_stems(q['agencia_sin_dato'])} ({_pct(q['agencia_sin_dato'] / rows)})",
        f"Transporte sin dato: {_stems(q['transporte_sin_dato'])} ({_pct(q['transporte_sin_dato'] / rows)})",
        f"Flete con tallos cero: {_stems(q['flete_sin_tallos'])}",
    ]
    tone = "bad" if q["tipo_sin_dato"] / rows > 0.3 or q["flete_sin_tallos"] > 0 else ("warn" if q["tipo_sin_dato"] else "good")
    return html.Div(
        [
            html.Div("Calidad de datos", style={"fontWeight": "800", "marginBottom": "8px"}),
            html.Div([html.Div(line, style={"marginBottom": "4px"}) for line in lines]),
            html.Div("Completar tipo operativo, agencia y transporte mejora la trazabilidad logistica.", style={"marginTop": "8px", "fontSize": "12px", "color": "#6B7280"}),
        ],
        style={**CARD_STYLE, "background": "#FFFFFF"},
        className=f"quality-card-{tone}",
    )


def _mark_outliers(weekly: pd.DataFrame, metric: str) -> pd.DataFrame:
    if weekly.empty or metric not in weekly.columns:
        return pd.DataFrame()
    values = pd.to_numeric(weekly[metric], errors="coerce").fillna(0)
    threshold = max(values.quantile(0.90), values.mean() + values.std(ddof=0))
    return weekly[values.ge(threshold) & values.gt(0)].copy()


def _line_or_message(frame: pd.DataFrame, metric: str, title: str, y_title: str, formatter: str = ""):
    if frame.empty or metric not in frame.columns or frame["periodo"].nunique() < 2:
        return html.Div(_small_insight(f"No hay suficientes semanas para leer tendencia de {title.lower()}.", "warn"))
    fig = px.line(frame, x="periodo", y=metric, color="serie", markers=True, title=title, hover_data=["anio", "semana_iso", "tallos", "ventas_usd", "flete_total"])
    peaks = _mark_outliers(frame[frame["serie"].eq(frame["serie"].iloc[-1])], metric)
    if not peaks.empty:
        fig.add_trace(go.Scatter(x=peaks["periodo"], y=peaks[metric], mode="markers", marker=dict(color="#DC2626", size=10, symbol="diamond"), name="Pico"))
    fig.update_layout(height=320, margin=dict(l=35, r=20, t=55, b=55), xaxis_title="Semana", yaxis_title=y_title, legend_title="")
    if formatter == "pct":
        fig.update_yaxes(tickformat=".1%")
    return dcc.Graph(figure=fig)


def _bar_or_insight(frame: pd.DataFrame, x: str, y: str, title: str, color: str = "#4F46E5", percent_axis: bool = False):
    if frame.empty or x not in frame.columns or y not in frame.columns:
        return _small_insight(f"No hay datos suficientes para {title.lower()}.", "warn")
    if frame[x].nunique() <= 1:
        row = frame.iloc[0]
        value = _pct(row[y]) if percent_axis else _usd_unit(row[y])
        return _small_insight(f"{title}: solo hay una categoria visible ({row[x]}: {value}).", "neutral")
    plot = frame.sort_values(y, ascending=True).tail(10)
    fig = px.bar(plot, x=y, y=x, orientation="h", title=title, hover_data=[col for col in ["tallos", "ventas_usd", "flete_total", "flete_x_tallo", "rate_cif_prom"] if col in plot.columns])
    fig.update_traces(marker_color=color)
    fig.update_layout(height=340, margin=dict(l=20, r=20, t=55, b=35), xaxis_title="", yaxis_title="")
    if percent_axis:
        fig.update_xaxes(tickformat=".1%")
    return dcc.Graph(figure=fig)


def _commercial_pressure_chart(frame: pd.DataFrame, clients_selected: bool):
    group_cols = ["producto"] if clients_selected else ["cod_cliente", "cliente"]
    label = "producto" if clients_selected else "cliente"
    grouped = _aggregate(frame, group_cols)
    if grouped.empty or len(grouped) < 2:
        return _small_insight("No hay suficientes puntos para dispersión comercial; revisa el resumen y la tendencia semanal.", "warn")
    threshold = grouped["flete_x_tallo"].quantile(0.75)
    fig = px.scatter(
        grouped,
        x="ventas_usd",
        y="flete_x_tallo",
        size="tallos",
        color=label,
        title="Venta vs flete x tallo",
        hover_data=["tallos", "flete_total", "flete_pct_venta", "precio_fob_x_tallo"],
    )
    fig.add_hline(y=threshold, line_dash="dash", line_color="#F97316", annotation_text="Zona de flete alto")
    fig.update_layout(height=360, margin=dict(l=30, r=20, t=55, b=45), xaxis_title="Venta USD", yaxis_title="USD/tallo", legend_title="")
    return dcc.Graph(figure=fig)


def _cif_del_section(applicable: pd.DataFrame, metric_trend: pd.DataFrame, kpis: dict[str, float]):
    if applicable.empty:
        return html.Div()
    unit_long = pd.DataFrame()
    if not metric_trend.empty:
        unit_long = metric_trend.melt(
            id_vars=["periodo", "anio", "semana_iso", "serie", "tallos", "ventas_usd", "flete_total"],
            value_vars=[col for col in ["cif_x_tallo", "del_x_tallo"] if col in metric_trend.columns],
            var_name="componente",
            value_name="usd_tallo",
        )
        unit_long["componente"] = unit_long["componente"].map({"cif_x_tallo": "CIF x tallo", "del_x_tallo": "DEL x tallo"})

    rate_long = pd.DataFrame()
    if not metric_trend.empty:
        rate_long = metric_trend.melt(
            id_vars=["periodo", "anio", "semana_iso", "serie", "tallos"],
            value_vars=[col for col in ["rate_cif_prom", "rate_del_prom"] if col in metric_trend.columns],
            var_name="componente",
            value_name="rate",
        )
        rate_long["componente"] = rate_long["componente"].map({"rate_cif_prom": "Rate CIF", "rate_del_prom": "Rate DEL"})
        rate_long = rate_long[pd.to_numeric(rate_long["rate"], errors="coerce").fillna(0).gt(0)].copy()

    unit_fig = None
    if not unit_long.empty and unit_long["periodo"].nunique() >= 2:
        unit_fig = px.line(
            unit_long,
            x="periodo",
            y="usd_tallo",
            color="componente",
            line_dash="serie",
            markers=True,
            title="CIF vs DEL: unitario por tallo",
            hover_data=["anio", "semana_iso", "serie", "tallos", "flete_total"],
        )
        unit_fig.update_layout(height=320, margin=dict(l=35, r=20, t=55, b=55), xaxis_title="Semana", yaxis_title="USD/tallo", legend_title="")

    rate_fig = None
    if not rate_long.empty and rate_long["periodo"].nunique() >= 2:
        rate_fig = px.line(
            rate_long,
            x="periodo",
            y="rate",
            color="componente",
            line_dash="serie",
            markers=True,
            title="CIF vs DEL: rate ponderado",
            hover_data=["anio", "semana_iso", "serie", "tallos"],
        )
        rate_fig.update_layout(height=320, margin=dict(l=35, r=20, t=55, b=55), xaxis_title="Semana", yaxis_title="Rate", legend_title="")

    agency_cif = _aggregate(applicable[applicable["flete_cif_distribuido"].gt(0)], ["agencia_carga_cif"]).sort_values("flete_cif", ascending=False)
    agency_del = _aggregate(applicable[applicable["flete_del_distribuido"].gt(0)], ["agencia_carga_del"]).sort_values("flete_del", ascending=False)
    transport_cif = _aggregate(applicable[applicable["flete_cif_distribuido"].gt(0)], ["tipo_transporte_cif"]).sort_values("cif_x_tallo", ascending=False)
    transport_del = _aggregate(applicable[applicable["flete_del_distribuido"].gt(0)], ["tipo_transporte_del"]).sort_values("del_x_tallo", ascending=False)

    return html.Div(
        [
            _section_header("CIF vs DEL", "Separacion central del costo logistico: monto, unitario, rate y responsables."),
            html.Div(
                [
                    _fletes_kpi_card("Flete CIF", _usd(kpis["total_cif"]), f"{_usd_unit(kpis['cif_x_tallo'])} USD/tallo | rate {_rate(kpis['rate_cif_pond'])}", "CIF", "#4F46E5", "#EEF2FF"),
                    _fletes_kpi_card("Flete DEL", _usd(kpis["total_del"]), f"{_usd_unit(kpis['del_x_tallo'])} USD/tallo | rate {_rate(kpis['rate_del_pond'])}", "DEL", "#F97316", "#FFEDD5"),
                    _fletes_kpi_card("Participacion CIF", _pct(kpis["total_cif"] / kpis["total_flete"] if kpis["total_flete"] else 0), "peso sobre flete total", "Mix", "#2563EB", "#DBEAFE"),
                    _fletes_kpi_card("Participacion DEL", _pct(kpis["total_del"] / kpis["total_flete"] if kpis["total_flete"] else 0), "peso sobre flete total", "Mix", "#EA580C", "#FED7AA"),
                ],
                style=GRID_STYLE,
            ),
            html.Div(
                [
                    html.Div(dcc.Graph(figure=unit_fig) if unit_fig else _small_insight("No hay suficientes semanas para comparar unitario CIF vs DEL.", "warn"), style=CARD_STYLE),
                    html.Div(dcc.Graph(figure=rate_fig) if rate_fig else _small_insight("No hay suficientes semanas con rate para comparar CIF vs DEL.", "warn"), style=CARD_STYLE),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))", "gap": "12px", "marginTop": "12px"},
            ),
            html.Div(
                [
                    html.Div(_bar_or_insight(agency_cif, "agencia_carga_cif", "flete_cif", "Agencias CIF por costo", "#4F46E5"), style=CARD_STYLE),
                    html.Div(_bar_or_insight(agency_del, "agencia_carga_del", "flete_del", "Agencias DEL por costo", "#F97316"), style=CARD_STYLE),
                    html.Div(_bar_or_insight(transport_cif, "tipo_transporte_cif", "cif_x_tallo", "Transporte CIF por USD/tallo", "#6366F1"), style=CARD_STYLE),
                    html.Div(_bar_or_insight(transport_del, "tipo_transporte_del", "del_x_tallo", "Transporte DEL por USD/tallo", "#FB923C"), style=CARD_STYLE),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "12px", "marginTop": "12px"},
            ),
        ],
        style=SECTION_STYLE,
    )


def _detail_table(frame: pd.DataFrame, group_cols: list[str], title: str, rows: int = 12):
    display = _display(frame, group_cols, rows=80)
    if display.empty:
        content = html.Div("Sin datos para este detalle.", style={"padding": "12px", "color": "#6B7280"})
    else:
        content = _table(display, rows=rows)
    return html.Details(
        [
            html.Summary(title, style={"cursor": "pointer", "fontWeight": "800", "padding": "12px 0"}),
            content,
        ],
        style={**CARD_STYLE, "paddingTop": "2px", "paddingBottom": "8px"},
    )


def _generate_fletes_insights(frame: pd.DataFrame, weekly: pd.DataFrame, clients: list[str] | None, benchmark: pd.DataFrame) -> list:
    kpis = _calculate_fletes_kpis(frame)
    if not kpis:
        return [_small_insight("Sin datos para generar lectura rapida.", "warn")]
    status, _, _ = _risk_status(kpis["pct_flete_venta"])
    insights = [
        _small_insight(f"El flete representa {_pct(kpis['pct_flete_venta'])} de la venta con flete CIF/DEL; clasificacion: {status.lower()}.", "bad" if status == "Critico" else ("warn" if status == "Atencion" else "good")),
        _small_insight(f"CIF explica {_pct(kpis['total_cif'] / kpis['total_flete'] if kpis['total_flete'] else 0)} del flete y DEL {_pct(kpis['total_del'] / kpis['total_flete'] if kpis['total_flete'] else 0)}.", "neutral"),
    ]
    product = _top_metric(frame, ["producto"], "flete_x_tallo", ascending=False)
    if product is not None:
        insights.append(_small_insight(f"Producto con mayor flete por tallo: {_row_label(product, ['producto'])} ({_usd_unit(product.get('flete_x_tallo', 0))} USD/tallo).", "warn"))
    if not weekly.empty:
        peak = weekly.sort_values("flete_pct_venta", ascending=False).iloc[0]
        insights.append(_small_insight(f"Semana mas presionada: {int(peak['anio'])}-W{int(peak['semana_iso']):02d}, con {_pct(peak.get('flete_pct_venta', 0))} flete/venta.", "warn"))
    selected_clients = _selected_values(clients)
    if selected_clients and not benchmark.empty:
        client_rate = kpis["flete_x_tallo"]
        bench_rate = _calculate_fletes_kpis(benchmark).get("flete_x_tallo", 0)
        delta = (client_rate / bench_rate - 1) if bench_rate else 0
        direction = "por encima" if delta > 0 else "por debajo"
        insights.append(_small_insight(f"Cliente seleccionado: {_usd_unit(client_rate)} USD/tallo vs benchmark {_usd_unit(bench_rate)}; esta {_pct(abs(delta))} {direction}.", "bad" if delta > 0.1 else "good"))
    q = _data_quality(frame)
    if q and q["tipo_sin_dato"] > 0:
        insights.append(_small_insight(f"Hay {_stems(q['tipo_sin_dato'])} registros con tipo operativo sin dato; esto limita el analisis por solido/surtido/bouquet.", "warn"))
    return insights[:6]


def get_fletes_type_options(
    years: list[int] | None = None,
    week_range: list[int] | None = None,
    companies: list[str] | None = None,
    clients: list[str] | None = None,
    countries: list[str] | None = None,
    products: list[str] | None = None,
    colors: list[str] | None = None,
) -> list[dict[str, str]]:
    try:
        frame, _ = _read_freight_scope(years, week_range, companies, clients, countries, products, colors, None)
    except Exception:
        return []
    if frame.empty or "tipo_pedido_operativo" not in frame.columns:
        return []
    values = sorted(value for value in frame["tipo_pedido_operativo"].dropna().astype(str).unique() if value.strip())
    return [{"label": value, "value": value} for value in values]


def _fletes_options_from_frame(frame: pd.DataFrame, value_col: str, label_col: str | None = None) -> tuple[list[dict[str, str]], list[str]]:
    if frame.empty or value_col not in frame.columns:
        return [], []
    label_col = label_col if label_col and label_col in frame.columns else value_col
    work = frame[[value_col, label_col, "tallos_confirmados"]].copy() if "tallos_confirmados" in frame.columns else frame[[value_col, label_col]].copy()
    work["_value"] = work[value_col].fillna("").astype(str).str.strip()
    work["_label"] = work[label_col].fillna("").astype(str).str.strip()
    work = work[~work["_value"].str.lower().isin({"", "nan", "none", "sin dato"})].copy()
    if work.empty:
        return [], []
    if "tallos_confirmados" in work.columns:
        grouped = work.groupby(["_value", "_label"], as_index=False)["tallos_confirmados"].sum().sort_values("tallos_confirmados", ascending=False)
    else:
        grouped = work.drop_duplicates(["_value", "_label"])
    options = [{"label": row["_label"], "value": row["_value"]} for row in grouped.to_dict("records")]
    return options, [option["value"] for option in options]


def get_fletes_filter_options(
    years: list[int] | None = None,
    week_range: list[int] | None = None,
) -> dict[str, tuple[list[dict[str, str]], list[str]]]:
    """Opciones de filtros leidas desde la tabla propia de fletes."""
    try:
        frame, _ = _read_freight_scope(years, week_range, None, None, None, None, None, None)
    except Exception:
        empty = ([], [])
        return {"companies": empty, "clients": empty, "countries": empty, "products": empty, "colors": empty, "types": empty}
    if frame.empty:
        empty = ([], [])
        return {"companies": empty, "clients": empty, "countries": empty, "products": empty, "colors": empty, "types": empty}
    client_frame = frame.copy()
    if {"cliente", "cod_cliente"}.issubset(client_frame.columns):
        client_frame["cliente_label"] = client_frame["cliente"].astype(str) + " | " + client_frame["cod_cliente"].astype(str)
    return {
        "companies": _fletes_options_from_frame(frame, "NomCompania"),
        "clients": _fletes_options_from_frame(client_frame, "cod_cliente", "cliente_label"),
        "countries": _fletes_options_from_frame(frame, "pais"),
        "products": _fletes_options_from_frame(frame, "producto"),
        "colors": _fletes_options_from_frame(frame, "color"),
        "types": _fletes_options_from_frame(frame, "tipo_pedido_operativo"),
    }


def _render_fletes_dashboard(
    frame: pd.DataFrame,
    stats: dict[str, Any],
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
    comparison_frame: pd.DataFrame,
):
    applicable = _freight_applicable(frame)
    if applicable.empty:
        return html.Div([_section_header("Analisis de Fletes"), _small_insight("No hay flete CIF/DEL aplicable con los filtros actuales.", "warn")], style={"padding": "16px"})
    kpis = _calculate_fletes_kpis(applicable)
    status, status_color, status_bg = _risk_status(kpis["pct_flete_venta"])
    weekly = _aggregate(applicable, ["anio", "semana_iso"])
    weekly_axis = _add_period_axis(weekly)
    comparison_applicable = _freight_applicable(comparison_frame)
    trend_parts = []
    if not comparison_applicable.empty and _selected_values(clients):
        trend_parts.append(_fob_evolution_frame(comparison_applicable, "General filtrado"))
    trend_parts.append(_fob_evolution_frame(applicable, "Cliente seleccionado" if _selected_values(clients) else "Filtro actual"))
    trend = pd.concat([part for part in trend_parts if not part.empty], ignore_index=True) if trend_parts else pd.DataFrame()
    metric_parts = []
    if not comparison_applicable.empty and _selected_values(clients):
        metric_parts.append(_fob_evolution_frame(comparison_applicable, "General filtrado"))
    metric_parts.append(_fob_evolution_frame(applicable, "Cliente seleccionado" if _selected_values(clients) else "Filtro actual"))
    metric_trend = pd.concat([part for part in metric_parts if not part.empty], ignore_index=True) if metric_parts else pd.DataFrame()

    subtitle_parts = [
        f"Anios: {_selected_label(years)}",
        f"Semanas: {week_range[0]}-{week_range[1]}" if week_range and len(week_range) == 2 else "Semanas: todas",
        f"Cliente: {_selected_label(clients)}",
        f"Producto: {_selected_label(products)}",
        f"Pais: {_selected_label(countries)}",
    ]
    q = _data_quality(frame)
    alert = q and q["tipo_sin_dato"] > 0

    kpi_cards = [
        _fletes_kpi_card("Venta con flete USD", _usd(kpis["total_ventas"]), "Solo registros CIF/DEL con flete > 0", "Venta", "#2563EB", "#DBEAFE"),
        _fletes_kpi_card("Total flete", _usd(kpis["total_flete"]), f"CIF {_usd(kpis['total_cif'])} / DEL {_usd(kpis['total_del'])}", "Logistica", "#4F46E5", "#EEF2FF"),
        _fletes_kpi_card("Flete por tallo", _usd_unit(kpis["flete_x_tallo"]), f"CIF {_usd_unit(kpis['cif_x_tallo'])} / DEL {_usd_unit(kpis['del_x_tallo'])}", "USD/tallo", "#7C3AED", "#F3E8FF"),
        _fletes_kpi_card("% flete / venta", _pct(kpis["pct_flete_venta"]), "<=18% saludable | 18%-23% atencion | >23% critico", status, status_color, status_bg),
        _fletes_kpi_card("FOB estimado", _usd(kpis["precio_fob"]), f"{_usd_unit(kpis['fob_x_tallo'])} USD/tallo", "Margen", "#059669", "#D1FAE5"),
        _fletes_kpi_card("Volumen logistico", _stems(kpis["total_tallos"]), f"{_stems(kpis['facturas'])} facturas | {_stems(kpis['lineas'])} lineas", "Tallos con flete", "#0F766E", "#CCFBF1"),
    ]

    client_rank = _aggregate(applicable, ["cod_cliente", "cliente"])
    min_volume = _min_volume(applicable)
    client_rank = client_rank[client_rank["tallos"].ge(min_volume)].copy() if not client_rank.empty else client_rank
    client_rank["cliente_label"] = client_rank["cliente"].astype(str).str.slice(0, 34) + " | " + client_rank["cod_cliente"].astype(str) if not client_rank.empty else ""
    product_rank = _aggregate(applicable, ["producto"])
    agency_rank = _aggregate(applicable, ["agencia_carga_cif"])
    week_rank = weekly_axis.sort_values("flete_pct_venta", ascending=False).head(10) if not weekly_axis.empty else pd.DataFrame()
    if not week_rank.empty:
        week_rank["semana_label"] = week_rank["anio"].astype(int).astype(str) + "-W" + week_rank["semana_iso"].astype(int).astype(str).str.zfill(2)
    country_agency = _aggregate(applicable, ["pais", "agencia_carga_cif"]).sort_values("flete_total", ascending=False).head(10)
    country = _aggregate(applicable, ["pais"]).sort_values("flete_total", ascending=False).head(10)
    transport = _aggregate(applicable, ["tipo_transporte_cif"]).sort_values("flete_total", ascending=False).head(10)
    type_mix = _aggregate(applicable, ["tipo_pedido_operativo"]).sort_values("flete_total", ascending=False)

    component_fig = go.Figure(data=[go.Pie(labels=["CIF", "DEL"], values=[kpis["total_cif"], kpis["total_del"]], hole=0.55, marker=dict(colors=["#4F46E5", "#F97316"]))])
    component_fig.update_layout(height=300, title="Composicion CIF vs DEL", margin=dict(l=20, r=20, t=55, b=20), showlegend=True)

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Resumen ejecutivo", style={"fontSize": "12px", "fontWeight": "800", "color": "#4F46E5", "textTransform": "uppercase"}),
                            html.H2("Analisis de Fletes", style={"margin": "4px 0", "fontSize": "28px", "color": "#111827"}),
                            html.Div(" | ".join(subtitle_parts), style={"color": "#4B5563", "fontSize": "13px"}),
                            html.Div(f"Fuente: {stats.get('table', 'Venta_Fletes_Distribuidos')}", style={"color": "#6B7280", "fontSize": "12px", "marginTop": "4px"}),
                        ]
                    ),
                    _small_insight("Alerta: tipo operativo sin dato en la tabla de fletes." if alert else "Campos criticos suficientes para lectura operativa.", "warn" if alert else "good"),
                ],
                style={"display": "grid", "gridTemplateColumns": "minmax(0, 1fr) minmax(240px, 340px)", "gap": "14px", "alignItems": "stretch", **CARD_STYLE},
            ),
            html.Div(kpi_cards, style={**GRID_STYLE, **SECTION_STYLE}),
            html.Div([_section_header("Lectura rapida", "Insights generados con los filtros actuales."), html.Div(_generate_fletes_insights(applicable, weekly_axis, clients, comparison_applicable), style=GRID_STYLE)], style=SECTION_STYLE),
            html.Div(
                [
                    _section_header("Evolucion semanal", "Tendencias utiles: presion de flete, unitario logistico y FOB x tallo."),
                    html.Div(
                        [
                            html.Div(_line_or_message(metric_trend, "flete_pct_venta", "% flete / venta por semana", "% flete / venta", "pct"), style=CARD_STYLE),
                            html.Div(_line_or_message(metric_trend, "flete_x_tallo", "Flete x tallo por semana", "USD/tallo"), style=CARD_STYLE),
                            html.Div(_line_or_message(trend, "precio_fob_x_tallo", "FOB x tallo vs benchmark", "USD/tallo"), style=CARD_STYLE),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "12px"},
                    ),
                ],
                style=SECTION_STYLE,
            ),
            _cif_del_section(applicable, metric_trend, kpis),
            html.Div(
                [
                    _section_header("Donde se encarece", "Rankings con minimo de volumen para evitar ruido."),
                    html.Div(
                        [
                            html.Div(_bar_or_insight(client_rank, "cliente_label", "flete_pct_venta", "Top clientes por % flete/venta", "#EF4444", True), style=CARD_STYLE),
                            html.Div(_bar_or_insight(product_rank, "producto", "flete_x_tallo", "Top productos por flete x tallo", "#7C3AED"), style=CARD_STYLE),
                            html.Div(_bar_or_insight(agency_rank, "agencia_carga_cif", "flete_cif", "Top agencias CIF por costo", "#4F46E5"), style=CARD_STYLE),
                            html.Div(_bar_or_insight(week_rank, "semana_label", "flete_pct_venta", "Top semanas criticas", "#F97316", True), style=CARD_STYLE),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(340px, 1fr))", "gap": "12px"},
                    ),
                ],
                style=SECTION_STYLE,
            ),
            html.Div(
                [
                    _section_header("Presion comercial", "Relaciona venta, flete unitario y volumen para priorizar revision."),
                    html.Div(
                        [
                            html.Div(_commercial_pressure_chart(applicable, bool(_selected_values(clients))), style=CARD_STYLE),
                            html.Div(
                                [
                                    _small_insight("Alto volumen + alto flete: prioridad comercial y logistica.", "bad"),
                                    _small_insight("Bajo volumen + alto flete: posible pedido poco eficiente o caso aislado.", "warn"),
                                    _small_insight("Alto volumen + bajo flete: referencia de eficiencia.", "good"),
                                ],
                                style={"display": "grid", "gap": "10px"},
                            ),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "minmax(0, 2fr) minmax(240px, 1fr)", "gap": "12px"},
                    ),
                ],
                style=SECTION_STYLE,
            ),
            html.Div(
                [
                    _section_header("Explicacion logistica", "Pais, agencia, transporte y calidad de trazabilidad."),
                    html.Div(
                        [
                            html.Div(_bar_or_insight(country, "pais", "flete_total", "Flete por pais", "#2563EB"), style=CARD_STYLE),
                            html.Div(_bar_or_insight(country_agency, "agencia_carga_cif", "flete_total", "Pais/agencia con mayor costo", "#4F46E5"), style=CARD_STYLE),
                            html.Div(dcc.Graph(figure=component_fig), style=CARD_STYLE),
                            _quality_card(applicable),
                            html.Div(_bar_or_insight(transport, "tipo_transporte_cif", "flete_total", "Tipo de transporte CIF", "#0F766E"), style=CARD_STYLE),
                            html.Div(_bar_or_insight(type_mix, "tipo_pedido_operativo", "precio_fob_x_tallo", "FOB x tallo por tipo operativo", "#059669"), style=CARD_STYLE),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "12px"},
                    ),
                ],
                style=SECTION_STYLE,
            ),
            html.Div(
                [
                    _section_header("Detalle operativo", "Detalle secundario para auditoria. Las tablas quedan cerradas por defecto."),
                    html.Div(
                        [
                            _detail_table(applicable, ["anio", "semana_iso"], "Detalle semanal"),
                            _detail_table(applicable, ["cod_cliente", "cliente"], "Detalle por cliente"),
                            _detail_table(applicable, ["producto"], "Detalle por producto"),
                            _detail_table(applicable, ["pais", "agencia_carga_cif"], "Detalle por agencia / pais"),
                            _detail_table(applicable, ["tipo_caja"], "Detalle por tipo de caja"),
                        ],
                        style={"display": "grid", "gap": "10px"},
                    ),
                ],
                style=SECTION_STYLE,
            ),
        ],
        style={"background": "#F6F8FB", "padding": "16px", "borderRadius": "8px"},
    )


def render_fletes_tab(
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
    order_types: list[str] | None = None,
):
    try:
        frame, stats = _read_freight_scope(years, week_range, companies, clients, countries, products, colors, order_types)
        comparison_frame = pd.DataFrame()
        if _selected_values(clients):
            comparison_frame, _ = _read_freight_scope(
                years,
                week_range,
                companies,
                None,
                countries,
                products,
                colors,
                order_types,
            )
    except Exception as exc:
        print(f"ERROR leyendo fletes desde SQL Server: {exc}", file=sys.stderr, flush=True)
        return html.Div(
            [
                html.Div("Fletes", className="panel-title"),
                html.Div(f"No se pudo cargar la vista de fletes: {exc}", className="empty-state"),
            ],
            className="table-panel",
        )

    if frame.empty:
        message = stats.get("error") or "No hay datos de fletes/ventas para los filtros actuales."
        return html.Div(
            [
                html.Div("Fletes", className="panel-title"),
                html.Div(message, className="empty-state"),
            ],
            className="table-panel",
        )

    return _render_fletes_dashboard(
        frame,
        stats,
        years,
        week_range,
        companies,
        clients,
        countries,
        products,
        colors,
        comparison_frame,
    )

    total_tallos = frame["tallos_confirmados"].sum()
    total_ventas = frame["ventas_usd"].sum()
    total_flete = frame["flete_total_distribuido"].sum()
    total_cif = frame["flete_cif_distribuido"].sum()
    total_del = frame["flete_del_distribuido"].sum()
    fob = frame["precio_fob_estimado"].sum()
    applicable = _freight_applicable(frame)
    applicable_tallos = applicable["tallos_confirmados"].sum()
    applicable_flete = applicable["flete_total_distribuido"].sum()
    applicable_ventas = applicable["ventas_usd"].sum()
    ranking_min_tallos = max(1000.0, applicable_tallos * 0.002) if applicable_tallos else 1000.0
    flete_x_tallo = applicable_flete / applicable_tallos if applicable_tallos else 0
    flete_pct_venta = applicable_flete / applicable_ventas if applicable_ventas else 0
    fob_x_tallo = fob / total_tallos if total_tallos else 0

    weekly = _aggregate(applicable, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    company = _aggregate(applicable, ["NomCompania"]).sort_values("flete_x_tallo", ascending=False).head(15)
    client = _aggregate(applicable, ["cod_cliente", "cliente"]).sort_values("flete_x_tallo", ascending=False).head(20)
    product = _aggregate(applicable, ["producto"]).sort_values("flete_x_tallo", ascending=False).head(18)
    box_type = _aggregate(applicable, ["tipo_caja"]).sort_values("flete_x_tallo", ascending=False).head(18)
    order_type = _aggregate(applicable, ["tipo_pedido_operativo"]).sort_values("flete_total", ascending=False).head(18)
    freight_type = _aggregate(applicable, ["tipo_flete"]).sort_values("flete_total", ascending=False).head(12)
    country_agency = _aggregate(applicable, ["pais", "agencia_carga_cif"]).sort_values("flete_total", ascending=False).head(18)
    rate = _aggregate(applicable[applicable["rate_cif"] > 0], ["anio", "semana_iso", "NomCompania"]).sort_values(["anio", "semana_iso"])
    weekly_axis = _add_period_axis(weekly)
    rate_axis = _add_period_axis(rate)
    rate_cif_global = (applicable["rate_cif"] * applicable["flete_cif_distribuido"]).sum() / applicable["flete_cif_distribuido"].replace(0, np.nan).sum() if not applicable.empty else 0
    insight_cards = _freight_insight_cards(applicable, weekly)
    comparison_applicable = _freight_applicable(comparison_frame)
    fob_parts = []
    if not comparison_applicable.empty:
        fob_parts.append(_fob_evolution_frame(comparison_applicable, "General filtrado"))
    client_label = "Cliente seleccionado" if _selected_values(clients) else "Filtro actual"
    fob_parts.append(_fob_evolution_frame(applicable, client_label))
    fob_evolution = pd.concat([part for part in fob_parts if not part.empty], ignore_index=True) if fob_parts else pd.DataFrame()

    if not weekly_axis.empty:
        trend_long = weekly_axis.melt(
            id_vars=["periodo", "anio", "semana_iso", "tallos", "flete_total", "flete_pct_venta"],
            value_vars=["cif_x_tallo", "del_x_tallo", "flete_x_tallo"],
            var_name="metrica",
            value_name="valor",
        )
        trend_long["metrica"] = trend_long["metrica"].map(
            {
                "cif_x_tallo": "CIF x tallo",
                "del_x_tallo": "DEL x tallo",
                "flete_x_tallo": "Total x tallo",
            }
        )
    else:
        trend_long = pd.DataFrame()

    freight_fig = (
        px.line(
            trend_long,
            x="periodo",
            y="valor",
            color="metrica",
            markers=True,
            title="Unitario CIF vs DEL por periodo",
            hover_data=["anio", "semana_iso", "tallos", "flete_total", "flete_pct_venta"],
        )
        if not trend_long.empty
        else _empty_figure("Unitario CIF vs DEL por periodo")
    )
    freight_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=55), xaxis_title="Periodo", yaxis_title="USD/tallo")

    fob_fig = (
        px.line(
            fob_evolution,
            x="periodo",
            y="precio_fob_x_tallo",
            color="serie",
            markers=True,
            title="Evolucion FOB x tallo: cliente vs general",
            hover_data=["anio", "semana_iso", "tallos", "ventas_usd", "flete_total", "precio_fob"],
        )
        if not fob_evolution.empty
        else _empty_figure("Evolucion FOB x tallo: cliente vs general")
    )
    fob_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=55), xaxis_title="Periodo", yaxis_title="USD/tallo")

    company_fig = (
        px.bar(company, x="NomCompania", y="flete_x_tallo", title="Flete x tallo CIF/DEL por compania", hover_data=["tallos", "ventas_usd", "flete_total"])
        if not company.empty
        else _empty_figure("Flete x tallo CIF/DEL por compania")
    )
    company_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=95), xaxis_title="", yaxis_title="USD/tallo")

    company_unit_long = company.melt(
        id_vars=["NomCompania", "tallos", "ventas_usd", "flete_total"],
        value_vars=["cif_x_tallo", "del_x_tallo"],
        var_name="componente",
        value_name="valor",
    ) if not company.empty else pd.DataFrame()
    if not company_unit_long.empty:
        company_unit_long["componente"] = company_unit_long["componente"].map({"cif_x_tallo": "CIF x tallo", "del_x_tallo": "DEL x tallo"})
    company_unit_fig = (
        px.bar(company_unit_long, x="NomCompania", y="valor", color="componente", barmode="group", title="Unitario CIF/DEL por compania", hover_data=["tallos", "ventas_usd", "flete_total"])
        if not company_unit_long.empty
        else _empty_figure("Unitario CIF/DEL por compania")
    )
    company_unit_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=95), xaxis_title="", yaxis_title="USD/tallo")

    rate_fig = (
        px.line(
            rate_axis,
            x="periodo",
            y="rate_cif_prom",
            color="NomCompania",
            markers=True,
            title="Evolucion Rate CIF por compania",
            hover_data=["anio", "semana_iso", "tallos", "flete_cif"],
        )
        if not rate_axis.empty
        else _empty_figure("Evolucion Rate CIF por compania")
    )
    rate_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=55), xaxis_title="Periodo", yaxis_title="Rate CIF")

    type_fig = (
        px.bar(freight_type, x="tipo_flete", y="flete_total", title="Flete por tipo", hover_data=["tallos", "ventas_usd", "flete_x_tallo"])
        if not freight_type.empty
        else _empty_figure("Flete por tipo")
    )
    type_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=70), xaxis_title="", yaxis_title="USD")

    order_type_fig = (
        px.bar(order_type, x="tipo_pedido_operativo", y="precio_fob_x_tallo", title="FOB x tallo por tipo operativo", hover_data=["tallos", "ventas_usd", "flete_total", "flete_x_tallo"])
        if not order_type.empty
        else _empty_figure("FOB x tallo por tipo operativo")
    )
    order_type_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=70), xaxis_title="", yaxis_title="USD/tallo")

    product_fig = (
        px.bar(product, x="producto", y="flete_x_tallo", title="Flete x tallo CIF/DEL por producto", hover_data=["tallos", "ventas_usd", "flete_total"])
        if not product.empty
        else _empty_figure("Flete x tallo CIF/DEL por producto")
    )
    product_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=80), xaxis_title="", yaxis_title="USD/tallo")

    product_unit_long = product.melt(
        id_vars=["producto", "tallos", "ventas_usd", "flete_total"],
        value_vars=["cif_x_tallo", "del_x_tallo"],
        var_name="componente",
        value_name="valor",
    ) if not product.empty else pd.DataFrame()
    if not product_unit_long.empty:
        product_unit_long["componente"] = product_unit_long["componente"].map({"cif_x_tallo": "CIF x tallo", "del_x_tallo": "DEL x tallo"})
    product_unit_fig = (
        px.bar(product_unit_long, x="producto", y="valor", color="componente", barmode="group", title="Unitario CIF/DEL por producto", hover_data=["tallos", "ventas_usd", "flete_total"])
        if not product_unit_long.empty
        else _empty_figure("Unitario CIF/DEL por producto")
    )
    product_unit_fig.update_layout(height=340, margin=dict(l=25, r=20, t=55, b=80), xaxis_title="", yaxis_title="USD/tallo")

    client_scatter_fig = _scatter_figure(applicable, ["cod_cliente", "cliente", "NomCompania"], "NomCompania", "Clientes CIF/DEL: ventas vs flete x tallo")
    product_scatter_fig = _scatter_figure(applicable, ["producto"], "producto", "Productos CIF/DEL: ventas vs flete x tallo")

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Fletes", className="executive-kicker"),
                    html.Div("Analisis descriptivo de fletes", className="executive-title"),
                    html.Div(
                        f"Fuente unica: {stats.get('table', '')}. Tipo operativo: {stats.get('tipo_pedido_source', 'no disponible')}.",
                        className="executive-subtitle",
                    ),
                ],
                className="sales-executive-header",
            ),
            html.Div(
                [
                    _card("Valor factura USD", _fmt(total_ventas, 2), "ventas filtradas"),
                    _card("Total flete", _fmt(total_flete, 2), f"CIF {_fmt(total_cif, 2)} / DEL {_fmt(total_del, 2)}"),
                    _card("Flete x tallo CIF/DEL", _fmt(flete_x_tallo, 4), "total flete CIF/DEL / tallos CIF/DEL"),
                    _card("% flete/venta", _pct(flete_pct_venta), "presion sobre ingreso aplicable"),
                    _card("Rate CIF pond.", _fmt(rate_cif_global, 4), "ponderado por flete CIF"),
                    _card("Precio FOB estimado", _fmt(fob, 2), f"{_fmt(fob_x_tallo, 4)} USD/tallo"),
                    _card("Facturas flete", _fmt(stats["invoices_fletes"], 0), f"{_fmt(stats['invoices_con_flete'], 0)} con flete mayor a cero"),
                    _card("Tallos CIF/DEL", _fmt(applicable_tallos, 0), f"ventas CIF/DEL USD {_fmt(applicable_ventas, 2)}"),
                ],
                className="metrics-grid",
            ),
            html.Div(
                [
                    html.Div("Lectura gerencial", className="panel-title"),
                    html.Div(insight_cards, className="metrics-grid"),
                ],
                className="section-gap",
            ),
            _section("1. Tendencia de tarifas", "Separa unitario CIF y DEL para ver que componente mueve el costo."),
            html.Div(
                [
                    html.Div([html.Div("FOB x tallo cliente vs general", className="panel-title"), dcc.Graph(figure=fob_fig)], className="panel"),
                    html.Div([html.Div("Unitario CIF vs DEL", className="panel-title"), dcc.Graph(figure=freight_fig)], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([html.Div("Rate CIF por compania", className="panel-title"), dcc.Graph(figure=rate_fig)], className="panel"),
                    html.Div([html.Div("Tipo operativo: FOB x tallo", className="panel-title"), dcc.Graph(figure=order_type_fig)], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            _section("2. Donde se encarece", "Ranking por flete x tallo CIF/DEL con minimo de volumen para evitar ruido de casos pequenos."),
            html.Div(
                [
                    html.Div([html.Div("Companias: unitario CIF/DEL", className="panel-title"), dcc.Graph(figure=company_unit_fig)], className="panel"),
                    html.Div([html.Div("Productos: unitario CIF/DEL", className="panel-title"), dcc.Graph(figure=product_unit_fig)], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Companias", className="panel-title"),
                            _table(_display(applicable, ["NomCompania"], 20, sort_col="flete_x_tallo", min_tallos=ranking_min_tallos), 10),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Clientes", className="panel-title"),
                            _table(_display(applicable, ["cod_cliente", "cliente"], 20, sort_col="flete_x_tallo", min_tallos=ranking_min_tallos), 10),
                        ],
                        className="table-panel no-top-margin",
                    ),
                ],
                className="executive-table-grid section-gap",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Productos", className="panel-title"),
                            _table(_display(applicable, ["producto"], 30, sort_col="flete_x_tallo", min_tallos=ranking_min_tallos), 12),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Tipo de caja", className="panel-title"),
                            _table(_display(applicable, ["tipo_caja"], 18, sort_col="flete_x_tallo", min_tallos=ranking_min_tallos), 12),
                        ],
                        className="table-panel no-top-margin",
                    ),
                ],
                className="executive-table-grid section-gap",
            ),
            _section("3. Presion comercial", "Relaciona ventas con costo logistico para ubicar clientes o productos que castigan margen."),
            html.Div(
                [
                    html.Div([html.Div("Clientes CIF/DEL: ventas vs flete x tallo", className="panel-title"), dcc.Graph(figure=client_scatter_fig)], className="panel"),
                    html.Div([html.Div("Productos CIF/DEL: ventas vs flete x tallo", className="panel-title"), dcc.Graph(figure=product_scatter_fig)], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            _section("4. Explicacion logistica", "Descompone el costo por tipo de flete, agencia, pais y transporte."),
            html.Div(
                [
                    html.Div([html.Div("Tipo de flete", className="panel-title"), dcc.Graph(figure=type_fig)], className="panel"),
                    html.Div(
                        [
                            html.Div("Tipo operativo", className="panel-title"),
                            _table(_display(applicable, ["tipo_pedido_operativo"], 18, sort_col="precio_fob_x_tallo"), 10),
                        ],
                        className="table-panel no-top-margin",
                    ),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div("Pais y agencia CIF", className="panel-title"),
                    _table(_display(applicable, ["pais", "agencia_carga_cif"], 18), 10),
                ],
                className="table-panel section-gap",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Tipo flete / transporte", className="panel-title"),
                            _table(_display(applicable, ["tipo_flete", "tipo_transporte_cif", "clase_cif"], 30), 12),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Criterios de calculo", className="panel-title"),
                            html.Div(
                                [
                                    html.Div("La vista usa solo la tabla de fletes distribuida; no cruza contra Ventas generales ni contra op_sales.", className="strategy-card"),
                                    html.Div("El flete x tallo se calcula solamente con CIF y DEL; FOB, NAL y Sin dato quedan fuera del denominador.", className="strategy-card"),
                                    html.Div("Precio FOB estimado = valor factura USD - total flete de la tabla de fletes.", className="strategy-card"),
                                ],
                                className="strategy-grid",
                            ),
                        ],
                        className="strategy-panel",
                    ),
                ],
                className="executive-table-grid section-gap",
            ),
            _section("5. Detalle operativo", "Base semanal para validar el origen de los cambios."),
            html.Div(
                [
                    html.Div("Detalle semanal", className="panel-title"),
                    _table(_display(applicable, ["anio", "semana_iso"], 40), 15),
                ],
                className="table-panel section-gap",
            ),
        ],
        className="sales-executive-panel",
    )
