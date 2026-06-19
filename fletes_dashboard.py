"""Vista descriptiva de fletes desde la tabla operativa de Gaitana.

La fuente `Venta.Fletes_Distribuidos` ya trae ventas, tallos y fletes al nivel
distribuido de producto/color. Esta vista no cruza contra otras paginas del
dashboard; resume directamente esa tabla para evitar descuadres.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
from dash import dash_table, dcc, html

from src.lgf_operativo.local_env import load_local_credentials
from src.lgf_operativo.op_sales_sql import get_connection


FREIGHT_TABLE_CANDIDATES = [
    ("Venta", "Fletes_Distribuidos"),
    ("Ventas", "Fletes_Distribuidoos"),
    ("Ventas", "Fletes_Distribuidos"),
]


def _selected_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _fmt(value: Any, decimals: int = 0) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        numeric = 0
    return f"{float(numeric):,.{decimals}f}"


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


def _read_freight_scope(
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    load_local_credentials(override=True)
    os.environ["OP_SALES_USE_SQL_SERVER"] = "1"
    with get_connection() as con:
        resolved = _resolve_freight_table(con)
        if resolved is None:
            return pd.DataFrame(), {"error": "No encontre la tabla de fletes en SQL."}
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
                CAST(TIPCAJA AS nvarchar(120)) AS tipo_caja,
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
                    AVG(CAST(Rate_cif AS float))
                ) AS rate_cif,
                COALESCE(
                    SUM(COALESCE(CAST(Rate_del AS float), 0) * COALESCE(CAST(Total_Factura_del AS float), 0))
                    / NULLIF(SUM(COALESCE(CAST(Total_Factura_del AS float), 0)), 0),
                    AVG(CAST(Rate_del AS float))
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
                CAST(TIPCAJA AS nvarchar(120)),
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
    for col in [
        "cliente",
        "NomCompania",
        "pais",
        "producto",
        "color",
        "variedad",
        "tipo_caja",
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

    stats = {
        "table": f"{schema}.{table}",
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
    work["_tallos_cif"] = np.where(work["flete_cif_distribuido"].gt(0), work["tallos_confirmados"], 0)
    work["_tallos_del"] = np.where(work["flete_del_distribuido"].gt(0), work["tallos_confirmados"], 0)
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
        "rate_cif_prom": "Rate CIF prom.",
        "rate_del_prom": "Rate DEL prom.",
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
        "Rate CIF prom.",
        "Rate DEL prom.",
    ]
    out = out[[col for col in ordered if col in out.columns]].copy()
    for col in out.columns:
        if col == "% flete/venta":
            out[col] = pd.to_numeric(out[col], errors="coerce").map(_pct)
        elif col in {"Ano", "Semana", "Facturas", "Lineas", "Tallos CIF/DEL", "Tallos CIF", "Tallos DEL"}:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(0)
        elif col not in {"Compania", "Cod. cliente", "Cliente", "Pais", "Producto", "Color", "Tipo caja", "Tipo flete", "Transporte CIF", "Clase CIF", "Agencia CIF", "Transporte DEL", "Clase DEL", "Agencia DEL"}:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(4)
    return out


def _freight_applicable(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "tipo_flete" not in frame.columns:
        return frame.copy()
    tipo = frame["tipo_flete"].fillna("Sin dato").astype(str).str.strip().str.upper()
    excluded = {"", "FOB", "NAL", "NAN", "NONE", "SIN DATO", "SIN_DATO"}
    return frame[~tipo.isin(excluded)].copy()


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


def render_fletes_tab(
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
):
    try:
        frame, stats = _read_freight_scope(years, week_range, companies, clients, countries, products, colors)
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
    freight_type = _aggregate(applicable, ["tipo_flete"]).sort_values("flete_total", ascending=False).head(12)
    country_agency = _aggregate(applicable, ["pais", "agencia_carga_cif"]).sort_values("flete_total", ascending=False).head(18)
    rate = _aggregate(applicable[applicable["rate_cif"] > 0], ["anio", "semana_iso", "NomCompania"]).sort_values(["anio", "semana_iso"])
    weekly_axis = _add_period_axis(weekly)
    rate_axis = _add_period_axis(rate)
    rate_cif_global = (applicable["rate_cif"] * applicable["flete_cif_distribuido"]).sum() / applicable["flete_cif_distribuido"].replace(0, np.nan).sum() if not applicable.empty else 0
    insight_cards = _freight_insight_cards(applicable, weekly)

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
                        f"Fuente unica: {stats.get('table', '')}. La tabla ya trae flete distribuido, ventas y tallos.",
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
                    html.Div([html.Div("Unitario CIF vs DEL", className="panel-title"), dcc.Graph(figure=freight_fig)], className="panel"),
                    html.Div([html.Div("Rate CIF por compania", className="panel-title"), dcc.Graph(figure=rate_fig)], className="panel"),
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
                            html.Div("Pais y agencia CIF", className="panel-title"),
                            _table(_display(applicable, ["pais", "agencia_carga_cif"], 18), 10),
                        ],
                        className="table-panel no-top-margin",
                    ),
                ],
                className="grid-2 section-gap",
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
