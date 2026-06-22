"""Dashboard modular de analitica comercial LGF.

Consume de forma separada outputs descriptivos y forecast historico de solidos.
Las pestaÃ±as de inventario se mantienen como
reservas funcionales hasta que exista una fuente oficial de proyeccion.
"""

from __future__ import annotations

import argparse
import base64
import io
import math
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import Dash
from dash import ALL
from dash import Input
from dash import MATCH
from dash import Output
from dash import State
from dash import ctx
from dash import dash_table
from dash import dcc
from dash import html

from fletes_dashboard import get_fletes_type_options, render_fletes_tab
from src.lgf_operativo.local_env import load_local_credentials


load_local_credentials()


DEFAULT_DATA_DIR = Path("resultados") / "descriptivos"
DEFAULT_FORECAST_DIR = Path("resultados") / "forecast_solidos"
DEFAULT_DASHBOARD_DB = Path("resultados") / "dashboard_operativo.sqlite"
DEFAULT_LOGO_PATH = Path("Logos") / "Logo La Gaitana-01.png"


def resolve_logo_path() -> Path | None:
    preferred_names = ("Logo La Gaitana-01.png", "Logo La Gaitana-02.png")
    for folder in (Path("Logos"), Path("logos")):
        for name in preferred_names:
            candidate = folder / name
            if candidate.exists():
                return candidate
        if folder.exists():
            images = sorted([*folder.glob("*.png"), *folder.glob("*.jpg"), *folder.glob("*.jpeg")])
            if images:
                return images[0]
    return DEFAULT_LOGO_PATH if DEFAULT_LOGO_PATH.exists() else None

CORPORATE_BURGUNDY = "#800020"
FORECAST_LINE_COLOR = "#E63946"
SCENARIO_LINE_COLOR = "#00875A"
REGION_COLOR_MAP = {
    "EEUU / CANADA": "#4E79A7",
    "EEUU / CANADÃ": "#4E79A7",
    "USA": "#4E79A7",
    "UNITED STATES": "#4E79A7",
    "CANADA": "#4E79A7",
    "CANADÃ": "#4E79A7",
    "EUROPA": "#59A14F",
    "EUROPE": "#59A14F",
    "ASIA": "#F28E2B",
    "OTROS": "#B07AA1",
    "OTHER": "#B07AA1",
}
REGION_FALLBACK_COLOR = "#9CA3AF"
GRAPH_CONTAINER_BG = "#FAFAFA"
GRAPH_LABEL_LINE = "#555555"
GRAPH_TEXT = "#374151"
CORPORATE_SEQUENCE = [
    CORPORATE_BURGUNDY,
    "#4E79A7",
    "#59A14F",
    "#F28E2B",
    "#B07AA1",
    "#9CA3AF",
    "#E15759",
    "#76B7B2",
]
FLOWER_COLOR_KEYWORDS = {
    "RED": "#C1121F",
    "ROJO": "#C1121F",
    "BURGUNDY": CORPORATE_BURGUNDY,
    "VINOTINTO": CORPORATE_BURGUNDY,
    "WHITE": "#F3F4F6",
    "BLANCO": "#F3F4F6",
    "YELLOW": "#F2C94C",
    "AMARILLO": "#F2C94C",
    "ORANGE": "#F28E2B",
    "NARANJA": "#F28E2B",
    "PINK": "#F472B6",
    "ROSADO": "#F472B6",
    "PURPLE": "#7C3AED",
    "MORADO": "#7C3AED",
    "LAVENDER": "#A78BFA",
    "LILA": "#A78BFA",
    "GREEN": "#59A14F",
    "VERDE": "#59A14F",
    "BLUE": "#4E79A7",
    "AZUL": "#4E79A7",
    "CREAM": "#F7E7CE",
    "CREMA": "#F7E7CE",
    "PEACH": "#FDBA74",
    "DURAZNO": "#FDBA74",
}

PROFILE_COLS = [
    "cod_cliente",
    "cliente",
    "semanas_activas",
    "tallos_total",
    "tallos_promedio_semana",
    "pct_semanas_activas",
    "cv_volumen",
    "cumplimiento_tallos",
    "incumplimiento_tallos",
    "share_top5_sku_terminado",
    "share_top3_color",
    "share_top3_empaque",
    "share_top1_tipo_pedido",
    "share_solido",
    "share_surtido",
    "share_surtido_m",
    "share_rainbow",
    "share_bouquet",
    "share_combo",
    "share_bulk",
    "share_estructuras_mixtas",
    "share_facil_compra",
    "share_top5_analisis_operativo",
    "score_facilidad_compra_operativa",
    "score_compra_terminada_operativo",
    "entropia_color",
    "entropia_sku_terminado",
    "entropia_analisis_operativo",
    "score_frecuencia",
    "score_volumen",
    "score_color",
    "score_sku_terminado",
    "score_analisis_operativo",
    "score_empaque",
    "score_tipo_pedido",
    "score_oportunidad_incumplimiento",
    "score_compra_terminada",
    "recomendacion_compra",
    "segmento_cliente",
    "ultima_fecha_confirmada",
    "dias_desde_ultima_compra",
    "semanas_activas_ult_8w",
    "semanas_activas_ult_12w",
    "semanas_activas_ult_26w",
    "tallos_ult_8w",
    "tallos_ult_12w",
    "tallos_ult_26w",
    "cliente_activo_ult_16w",
]

SERIE_COLS = [
    "cod_cliente",
    "cliente",
    "anio_semana",
    "anio",
    "semana_iso",
    "tallos",
    "tallos_confirmados",
    "faltante_tallos",
    "colores",
    "skus_terminados",
    "productos",
    "tipos_pedido",
]

MIX_COMMON_COLS = [
    "cod_cliente",
    "cliente",
    "tallos",
    "tallos_confirmados",
    "faltante_tallos",
    "semanas_activas",
    "participacion_cliente",
    "cumplimiento",
]

DEMAND_COLS = [
    "fecha_forecast",
    "cod_cliente",
    "cliente",
    "tipo_pedido_operativo",
    "familia_analisis_operativa",
    "enfoque_analisis_operativo",
    "rol_color_operativo",
    "producto",
    "variedad",
    "color",
    "grado",
    "tipo_caja",
    "sku_flexible",
    "llave_analisis_operativo",
    "color_componente_key",
    "receta_estructura_key",
    "fuente_demanda",
    "tallos_estimados",
    "score_compra_terminada",
    "recomendacion_compra",
    "confianza_estimacion",
    "version_modelo",
]

INVENTORY_COLS = DEMAND_COLS + [
    "inventario_total",
    "inventario_color_total",
    "inventario_variedad_total",
    "faltante_proyectado_item",
    "faltante_variedad_proyectado",
    "sobrante_proyectado_item",
    "sobrante_variedad_proyectado",
    "riesgo_disponibilidad",
    "riesgo_variedad",
    "share_variedad_demanda_no_usa",
    "ranking_variedad_no_usa",
    "lectura_inventario",
    "criterio_compra_variedad",
    "tallos_prioridad_compra_cliente",
    "prioridad_compra",
]

INVENTORY_COLOR_COLS = [
    "fecha",
    "anio_semana",
    "producto",
    "color",
    "grado",
    "inventario_color_total",
    "variedades",
    "fincas",
    "faltante_color_proyectado",
    "sobrante_color_proyectado",
    "estado_disponibilidad_color",
]

ESTIMADOS_COLS = [
    "fecha",
    "cod_cliente",
    "cliente",
    "tipo_pedido_operativo",
    "familia_analisis_operativa",
    "enfoque_analisis_operativo",
    "rol_color_operativo",
    "producto",
    "variedad",
    "color",
    "grado",
    "tipo_caja",
    "sku_flexible",
    "llave_analisis_operativo",
    "color_componente_key",
    "receta_estructura_key",
    "tallos",
    "tallos_confirmados",
    "faltante_tallos",
    "fuente_demanda",
]

HISTORICO_SOLIDOS_COLS = [
    "fecha",
    "cod_cliente",
    "cliente",
    "pedido",
    "tipo_pedido_operativo",
    "familia_analisis_operativa",
    "enfoque_analisis_operativo",
    "rol_color_operativo",
    "producto",
    "variedad",
    "color",
    "grado",
    "tipo_caja",
    "tallos_x_ramo",
    "capuchon",
    "comida",
    "empaque",
    "tallos_analisis",
    "tallos_total",
    "tallos_confirmados",
    "faltante_tallos",
    "ventas_usd",
    "sku_terminado",
    "sku_flexible",
    "llave_analisis_operativo",
    "color_componente_key",
    "receta_estructura_key",
    "receta_programa_key",
    "receta_programa_tamano_key",
    "sku_operativo",
    "sku_composicion",
    "instancia_pedido_operativo",
    "caja_operativa",
    "ramos_pedidos",
    "ramos_x_caja",
    "ramos_x_caja_detalle",
    "piezas",
    "fulles",
    "equivalencia",
    "tallos_componente_caja",
    "tallos_programa_caja",
    "tallos_componentes_caja",
    "ramos_programa_caja_inferidos",
    "tallos_programa_ramo",
    "VALORUNITARIO",
    "VALORTOTAL",
    "NomMoneda",
]

STRUCTURE_COLS = [
    "cod_cliente",
    "cliente",
    "producto",
    "variedad",
    "color",
    "tipo_caja",
    "tallos_por_ramo",
    "capuchon",
    "comida",
    "empaque",
    "tipo_pedido_operativo",
    "tallos_ultimas_12_semanas",
    "frecuencia_ultimas_12_semanas",
    "cumplimiento",
    "vigencia_estructura",
    "recomendacion",
    "estructura_accionable",
    "tallos_historico",
    "semanas_historico",
    "tallos_ultimas_4_semanas",
    "frecuencia_ultimas_4_semanas",
]

TYPICAL_WEEK_COLS = [
    "cod_cliente",
    "cliente",
    "semana",
    "producto",
    "tipo_pedido_operativo",
    "color",
    "variedad",
    "tipo_caja",
    "tallos_por_ramo",
    "tallos_mediana_historica_semana",
    "tallos_promedio_historico_semana",
    "comportamiento_reciente",
    "confianza",
    "clasificacion_semana",
    "veces_aparece_en_misma_semana",
]

SKU_SUMMARY_COLS = [
    "cod_cliente", "cliente", "sku_operativo", "lectura_operativa", "tipo_pedido_operativo", "subtipo_pedido_operativo",
    "producto", "empaque", "tipo_caja", "tallos_por_ramo", "tallos_programa_caja", "tallos_componentes_caja",
    "ramos_programa_caja_inferidos", "tallos_programa_ramo", "ramos_x_caja", "fulles", "piezas", "capuchon", "comida", "receta", "caja_operativa", "codempaque", "bulkbouquet",
    "productos_composicion", "colores_composicion", "variedades_composicion", "lineas_componentes", "composicion_versiones",
    "composicion_firma_principal", "tallos_promedio_estructura", "ramos_estimados_comercial",
    "tallos_promedio_semana_normal", "porcentaje_semana_normal", "frecuencia_en_ventana", "pedidos_en_ventana", "instancias_en_ventana",
    "cumplimiento", "vigencia_sku", "recomendacion", "tallos_ventana", "ventas_usd_ventana",
]

SKU_COMPOSITION_COLS = [
    "cod_cliente", "cliente", "sku_operativo", "tipo_pedido_operativo", "producto", "color", "variedad",
    "porcentaje_composicion", "tallos_promedio_semana_normal", "ramos_promedio_semana_normal",
    "tipo_caja", "tallos_por_ramo", "capuchon", "comida", "empaque", "semanas", "estabilidad_composicion", "std_share_color",
    "productos_composicion", "colores_composicion", "variedades_composicion", "lineas_componentes", "composicion_versiones",
    "composicion_firma_principal",
]

WEEK_SKU_COLS = [
    "cod_cliente", "cliente", "anio", "semana_iso", "anio_semana", "sku_operativo", "tipo_pedido_operativo",
    "tallos_pedidos", "tallos_confirmados", "ventas_usd", "productos", "colores", "variedades", "lineas", "pedidos",
    "cumplimiento", "tallos_cliente_semana", "participacion_semana_cliente",
]

SALES_VISUAL_COLS = [
    "anio",
    "semana_iso",
    "anio_semana",
    "cod_cliente",
    "cliente",
    "NomCompania",
    "pais",
    "tipo_pedido_operativo",
    "producto",
    "color",
    "moneda_original",
    "tallos_confirmados",
    "ventas_usd",
    "valor_total_original",
    "pedidos",
    "cajas_ids",
    "precio_usd_tallo",
    "precio_moneda_original_tallo",
]

SALES_BOX_COLS = SALES_VISUAL_COLS + ["caja_operativa", "tipo_caja"]

STRUCTURE_BOX_COLS = [
    "estructura_caja_id", "composicion_version_id", "composicion_firma", "fecha", "anio_semana", "cod_cliente", "cliente", "pedido",
    "tipo_pedido_operativo", "sku_operativo", "sku_composicion", "caja_operativa", "tipo_caja",
    "capuchon", "comida", "empaque", "receta", "lineas_componentes", "productos", "colores", "variedades",
    "tallos_x_ramo_lista", "repeticiones_estructura", "tallos_estructura", "ramos_componentes", "ramos_estimados",
]

STRUCTURE_COMPONENT_COLS = [
    "estructura_caja_id", "composicion_version_id", "fecha", "anio_semana", "cod_cliente", "cliente", "pedido",
    "tipo_pedido_operativo", "sku_operativo", "sku_composicion", "caja_operativa", "tipo_caja",
    "producto", "variedad", "color", "grado", "tallos_x_ramo", "tallos_analisis",
    "ramos_pedidos", "ramos_estimados_linea", "estructuras_componente", "participacion_tallos_estructura",
]

STRUCTURE_VERSION_COLS = [
    "cod_cliente", "cliente", "tipo_pedido_operativo", "sku_operativo", "composicion_version_id", "composicion_firma",
    "veces_observada", "semanas_observada", "primera_fecha", "ultima_fecha",
    "tallos_promedio_estructura", "ramos_promedio_estimados",
]


def parse_args() -> argparse.Namespace:
    """Lee rutas de los modulos independientes que alimentan el dashboard."""
    parser = argparse.ArgumentParser(description="Dashboard Dash de analitica comercial LGF.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Carpeta con los CSV generados por run_descriptivos.py.")
    parser.add_argument(
        "--forecast-dir",
        default=str(DEFAULT_FORECAST_DIR),
        help="Carpeta independiente con los CSV generados por run_forecast_solidos.py.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host local para Dash.")
    parser.add_argument("--port", type=int, default=8050, help="Puerto local para Dash.")
    parser.add_argument("--debug", action="store_true", help="Activa debug de Dash.")
    return parser.parse_args()


def read_csv_if_exists(path: Path, usecols: list[str] | None = None, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, usecols=lambda col: usecols is None or col in usecols, parse_dates=parse_dates, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except ValueError:
        try:
            return pd.read_csv(path, parse_dates=parse_dates, low_memory=False)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()


def moneyless_number(value: float | int | None, decimals: int = 0) -> str:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return "0"
    return f"{value:,.{decimals}f}"


def percent(value: float | int | None) -> str:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return "0.00%"
    return f"{value * 100:,.2f}%"


def panel_note(text: str) -> html.Div:
    return html.Div(text, className="panel-note")


def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True)


def valid_validation_window_starts(frame: pd.DataFrame, year: int | None, weeks: int) -> list[int]:
    if frame.empty or year is None or "anio" not in frame.columns or "semana_iso" not in frame.columns:
        return []
    try:
        year = int(year)
        weeks = int(weeks)
    except (TypeError, ValueError):
        return []
    if weeks <= 0:
        return []
    work = frame.copy()
    work["anio"] = pd.to_numeric(work["anio"], errors="coerce")
    work["semana_iso"] = pd.to_numeric(work["semana_iso"], errors="coerce")
    work = work[work["anio"].eq(year) & work["semana_iso"].notna()]
    if work.empty:
        return []
    available = set(work["semana_iso"].astype(int).unique().tolist())
    starts = []
    for start in sorted(available):
        window = set(range(start, start + weeks))
        if window.issubset(available):
            starts.append(int(start))
    return starts


def read_dashboard_sql_view(db_path: Path, view_name: str) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as con:
        try:
            return pd.read_sql_query(f"SELECT * FROM {view_name}", con)
        except Exception:
            return pd.DataFrame()


def read_op_sales_sql_table(table_name: str, params: list | None = None, where: str = "") -> pd.DataFrame:
    sql_enabled = os.getenv("OP_SALES_USE_SQL_SERVER", "0").strip().lower() in {"1", "true", "yes", "si"}
    if not sql_enabled:
        return pd.DataFrame()
    allowed = {
        "op_sales.agg_sales_week_client_product",
        "op_sales.agg_client_sku_week",
        "op_sales.result_descriptivo_perfil_cliente",
        "op_sales.result_descriptivo_serie_cliente_semana",
        "op_sales.result_descriptivo_mix_producto",
        "op_sales.result_descriptivo_mix_color",
        "op_sales.result_descriptivo_mix_tipo_pedido",
        "op_sales.result_descriptivo_mix_sku_terminado",
        "op_sales.result_descriptivo_mix_analisis_operativo",
        "op_sales.result_descriptivo_mix_color_rol",
        "op_sales.result_descriptivo_estado_resumen",
        "op_sales.result_descriptivo_cliente_estructuras_repetidas",
        "op_sales.result_descriptivo_cliente_semana_tipica",
        "op_sales.result_descriptivo_cliente_sku_operativo_resumen",
        "op_sales.result_descriptivo_cliente_sku_operativo_composicion",
        "op_sales.result_descriptivo_cliente_semana_sku_operativo",
        "op_sales.result_descriptivo_ventas_producto_periodo",
        "op_sales.result_descriptivo_ventas_cliente_periodo",
        "op_sales.result_descriptivo_ventas_caja_periodo",
        "op_sales.result_descriptivo_estructura_caja",
        "op_sales.result_descriptivo_estructura_componentes",
        "op_sales.result_descriptivo_catalogo_estructura_version",
        "op_sales.result_forecast_solid_forecast_fuente_datos",
        "op_sales.result_forecast_solid_forecast_model_evaluation",
        "op_sales.result_forecast_solid_forecast_feature_importance",
        "op_sales.result_forecast_solid_forecast_market_feature_importance",
        "op_sales.result_forecast_solid_forecast_market_calibration",
        "op_sales.result_forecast_solid_forecast_predictors",
        "op_sales.result_forecast_solid_forecast_weekly_demand",
        "op_sales.result_forecast_solid_forecast_test_predictions",
        "op_sales.result_forecast_solid_forecast_historical_validation",
        "op_sales.result_forecast_solid_forecast_future",
        "op_sales.result_forecast_solid_forecast_error_by_market",
    }
    if table_name not in allowed:
        return pd.DataFrame()
    try:
        from src.lgf_operativo.op_sales_sql import get_connection

        with get_connection() as con:
            return pd.read_sql_query(f"SELECT * FROM {table_name}{where}", con, params=params or [])
    except Exception as exc:
        print(f"ERROR leyendo {table_name} desde SQL Server: {exc}", file=sys.stderr, flush=True)
        return pd.DataFrame()


def read_result_or_csv(
    sql_table: str,
    path: Path,
    usecols: list[str] | None = None,
    parse_dates: list[str] | None = None,
) -> pd.DataFrame:
    frame = read_op_sales_sql_table(sql_table)
    if frame.empty:
        frame = read_csv_if_exists(path, usecols, parse_dates)
    elif usecols:
        frame = frame[[col for col in usecols if col in frame.columns]].copy()
    if not frame.empty and parse_dates:
        for col in parse_dates:
            if col in frame.columns:
                frame[col] = pd.to_datetime(frame[col], errors="coerce")
    return frame


def read_client_sku_week_from_sql(client_code: str | None) -> pd.DataFrame:
    if not client_code:
        return pd.DataFrame()
    frame = read_op_sales_sql_table(
        "op_sales.agg_client_sku_week",
        params=[str(client_code)],
        where=" WHERE cod_cliente = ?",
    )
    if frame.empty:
        return frame
    frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
    if "fecha" in frame.columns:
        frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce")
    for col in ["tallos_confirmados", "tallos_pedidos", "tallos_historicos", "ventas_usd", "valor_total_original"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    return frame


def read_client_sku_week_many_from_sql(client_codes: list[str]) -> pd.DataFrame:
    codes = [str(code) for code in client_codes if str(code).strip()]
    if not codes:
        return pd.DataFrame()
    placeholders = ", ".join("?" for _ in codes)
    frame = read_op_sales_sql_table(
        "op_sales.agg_client_sku_week",
        params=codes,
        where=f" WHERE cod_cliente IN ({placeholders})",
    )
    if frame.empty:
        return frame
    frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
    if "fecha" in frame.columns:
        frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce")
    for col in ["tallos_confirmados", "tallos_pedidos", "tallos_historicos", "ventas_usd", "valor_total_original"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    return frame


ADMIN_PASSWORD = "142806"


ADMIN_ETL_JOB_LOCK = threading.RLock()
ADMIN_ETL_JOBS: dict[str, dict[str, object]] = {}
ADMIN_ETL_MAX_LINES = 220


def admin_job_timestamp() -> str:
    return time.strftime("%H:%M:%S")


def admin_format_duration(seconds: float | int | None) -> str:
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def admin_parse_progress_fraction(line: str) -> float | None:
    clean = str(line)
    patterns = [
        r"(?:lote|periodo|bloque)\s+([\d.,]+)\s*/\s*([\d.,]+)",
        r"([\d.,]+)\s*/\s*([\d.,]+)\s+filas",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        current = re.sub(r"\D", "", match.group(1))
        total = re.sub(r"\D", "", match.group(2))
        if not current or not total:
            continue
        total_value = int(total)
        if total_value <= 0:
            continue
        return min(1.0, max(0.0, int(current) / total_value))
    return None


def admin_job_create(initial_lines: list[str], step_titles: list[str]) -> str:
    job_id = f"admin-etl-{int(time.time() * 1000)}"
    with ADMIN_ETL_JOB_LOCK:
        ADMIN_ETL_JOBS[job_id] = {
            "lines": list(initial_lines),
            "steps": [
                {
                    "title": title,
                    "status": "pending",
                    "percent": 0.0,
                    "started_at": None,
                    "finished_at": None,
                }
                for title in step_titles
            ],
            "current_step": None,
            "status": "running",
            "started_at": time.time(),
            "finished_at": None,
        }
    return job_id


def admin_job_append(job_id: str, line: str = "") -> None:
    with ADMIN_ETL_JOB_LOCK:
        job = ADMIN_ETL_JOBS.get(job_id)
        if not job:
            return
        lines = job.setdefault("lines", [])
        if isinstance(lines, list):
            lines.append(f"[{admin_job_timestamp()}] {line}" if line else "")
            if len(lines) > ADMIN_ETL_MAX_LINES:
                del lines[: len(lines) - ADMIN_ETL_MAX_LINES]


def admin_job_finish(job_id: str, status: str) -> None:
    with ADMIN_ETL_JOB_LOCK:
        job = ADMIN_ETL_JOBS.get(job_id)
        if not job:
            return
        job["status"] = status
        job["finished_at"] = time.time()


def admin_job_start_step(job_id: str, step_index: int) -> None:
    with ADMIN_ETL_JOB_LOCK:
        job = ADMIN_ETL_JOBS.get(job_id)
        if not job:
            return
        steps = job.get("steps")
        if not isinstance(steps, list) or not (0 <= step_index < len(steps)):
            return
        step = steps[step_index]
        if not isinstance(step, dict):
            return
        step["status"] = "running"
        step["percent"] = max(float(step.get("percent") or 0), 0.02)
        step["started_at"] = time.time()
        step["finished_at"] = None
        job["current_step"] = step_index


def admin_job_update_current_step_progress(job_id: str, fraction: float) -> None:
    with ADMIN_ETL_JOB_LOCK:
        job = ADMIN_ETL_JOBS.get(job_id)
        if not job:
            return
        step_index = job.get("current_step")
        steps = job.get("steps")
        if not isinstance(step_index, int) or not isinstance(steps, list) or not (0 <= step_index < len(steps)):
            return
        step = steps[step_index]
        if not isinstance(step, dict) or step.get("status") != "running":
            return
        step["percent"] = min(0.98, max(float(step.get("percent") or 0), float(fraction)))


def admin_job_finish_step(job_id: str, step_index: int, ok: bool) -> None:
    with ADMIN_ETL_JOB_LOCK:
        job = ADMIN_ETL_JOBS.get(job_id)
        if not job:
            return
        steps = job.get("steps")
        if not isinstance(steps, list) or not (0 <= step_index < len(steps)):
            return
        step = steps[step_index]
        if not isinstance(step, dict):
            return
        step["status"] = "done" if ok else "error"
        step["percent"] = 1.0 if ok else max(float(step.get("percent") or 0), 0.0)
        step["finished_at"] = time.time()
        if job.get("current_step") == step_index:
            job["current_step"] = None


def admin_job_progress_lines(job: dict[str, object]) -> list[str]:
    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        return []
    now = time.time()
    percents = [float(step.get("percent") or 0) for step in steps if isinstance(step, dict)]
    total_percent = sum(percents) / len(steps) * 100 if percents else 0
    lines = [
        f"Avance total: {total_percent:5.1f}% | Tiempo total: {admin_format_duration(now - float(job.get('started_at') or now))}",
        "",
    ]
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        status = str(step.get("status") or "pending")
        label = {"pending": "PENDIENTE", "running": "EN CURSO", "done": "OK", "error": "ERROR"}.get(status, status.upper())
        started = step.get("started_at")
        finished = step.get("finished_at")
        elapsed = 0
        if isinstance(started, (int, float)):
            elapsed = (float(finished) if isinstance(finished, (int, float)) else now) - float(started)
        percent = float(step.get("percent") or 0) * 100
        lines.append(f"[{label:<9}] {percent:5.1f}% | {admin_format_duration(elapsed):>8} | Paso {index}/{len(steps)}: {step.get('title')}")
    return lines


def admin_job_snapshot(job_id: str | None) -> tuple[str, bool]:
    if not job_id:
        return "", True
    with ADMIN_ETL_JOB_LOCK:
        job = ADMIN_ETL_JOBS.get(job_id)
        if not job:
            return "No hay una ejecucion activa.", True
        progress_lines = admin_job_progress_lines(job)
        lines = list(job.get("lines") or [])
        done = job.get("status") != "running"
    output = [*progress_lines, "", "Detalle:", *[str(line) for line in lines]]
    return "\n".join(output), bool(done)


def admin_job_log_process_output(job_id: str, line: str, index: int) -> None:
    clean = re.sub(r"\s+", " ", str(line)).strip()
    if not clean:
        return
    lower = clean.lower()
    important = any(
        token in lower
        for token in [
            "error",
            "exception",
            "traceback",
            "filas",
            "rows",
            "insert",
            "delete",
            "batch",
            "lote",
            "carga",
            "termin",
            "valid",
        ]
    )
    if important or index <= 6 or index % 25 == 0:
        admin_job_append(job_id, f"  {clean[:260]}")
    fraction = admin_parse_progress_fraction(clean)
    if fraction is not None:
        admin_job_update_current_step_progress(job_id, fraction)


def admin_sql_status() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Read operational SQL coverage and latest ETL batches for the admin tab."""
    try:
        from src.lgf_operativo.op_sales_sql import get_connection

        with get_connection() as con:
            coverage = pd.read_sql_query(
                """
                SELECT
                    MIN(fecha) AS fecha_min,
                    MAX(fecha) AS fecha_max,
                    COUNT_BIG(*) AS filas,
                    COUNT(DISTINCT CONVERT(date, fecha)) AS dias,
                    COUNT(DISTINCT anio) AS anios
                FROM op_sales.fact_sales_line
                """,
                con,
            )
            batches = pd.read_sql_query(
                """
                SELECT TOP 12
                    load_id,
                    source_name,
                    period_start,
                    period_end,
                    status,
                    rows_deleted,
                    rows_inserted,
                    started_at,
                    finished_at
                FROM op_sales.etl_load_batch
                ORDER BY load_id DESC
                """,
                con,
            )
            result_counts = pd.read_sql_query(
                """
                SELECT 'Clientes perfil' AS metrica, COUNT(DISTINCT CAST(cod_cliente AS varchar(50))) AS valor
                FROM op_sales.result_descriptivo_perfil_cliente
                UNION ALL
                SELECT 'Clientes ventas', COUNT(DISTINCT CAST(cod_cliente AS varchar(50)))
                FROM op_sales.agg_sales_week_client_product
                UNION ALL
                SELECT 'Clientes SKU', COUNT(DISTINCT CAST(cod_cliente AS varchar(50)))
                FROM op_sales.result_descriptivo_cliente_sku_operativo_resumen
                UNION ALL
                SELECT 'Forecast futuro', COUNT_BIG(*)
                FROM op_sales.result_forecast_solid_forecast_future
                """,
                con,
            )
        if not coverage.empty:
            raw_min = pd.to_datetime(coverage.loc[0, "fecha_min"], errors="coerce")
            raw_max = pd.to_datetime(coverage.loc[0, "fecha_max"], errors="coerce")
            coverage.attrs["fecha_min"] = raw_min.strftime("%Y-%m-%d") if pd.notna(raw_min) else ""
            coverage.attrs["fecha_max"] = raw_max.strftime("%Y-%m-%d") if pd.notna(raw_max) else ""
            coverage.attrs["next_start"] = (raw_max + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if pd.notna(raw_max) else ""
            raw_rows = pd.to_numeric(coverage.loc[0, "filas"], errors="coerce")
            raw_days = pd.to_numeric(coverage.loc[0, "dias"], errors="coerce")
            coverage.attrs["filas"] = int(raw_rows) if pd.notna(raw_rows) else 0
            coverage.attrs["dias"] = int(raw_days) if pd.notna(raw_days) else 0
            if not result_counts.empty:
                counts = {
                    str(row.metrica): int(pd.to_numeric(row.valor, errors="coerce") or 0)
                    for row in result_counts.itertuples(index=False)
                }
                coverage.attrs["clientes_perfil"] = counts.get("Clientes perfil", 0)
                coverage.attrs["clientes_ventas"] = counts.get("Clientes ventas", 0)
                coverage.attrs["clientes_sku"] = counts.get("Clientes SKU", 0)
                coverage.attrs["forecast_futuro"] = counts.get("Forecast futuro", 0)
            for col in ["fecha_min", "fecha_max"]:
                coverage[col] = pd.to_datetime(coverage[col], errors="coerce").dt.strftime("%Y-%m-%d")
            for col in ["filas", "dias", "anios"]:
                coverage[col] = coverage[col].map(lambda value: moneyless_number(value, 0))
            coverage = coverage.rename(
                columns={
                    "fecha_min": "Desde SQL",
                    "fecha_max": "Hasta SQL",
                    "filas": "Filas",
                    "dias": "Dias cargados",
                    "anios": "Anios",
                }
            )
        if not batches.empty:
            for col in ["period_start", "period_end", "started_at", "finished_at"]:
                batches[col] = pd.to_datetime(batches[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            batches = batches.rename(
                columns={
                    "load_id": "Load ID",
                    "source_name": "Fuente",
                    "period_start": "Desde",
                    "period_end": "Hasta",
                    "status": "Estado",
                    "rows_deleted": "Filas eliminadas",
                    "rows_inserted": "Filas insertadas",
                    "started_at": "Inicio",
                    "finished_at": "Fin",
                    "error_message": "Error",
                }
            )
        return coverage, batches, ""
    except Exception as exc:
        return pd.DataFrame(), pd.DataFrame(), f"No se pudo leer SQL Server: {exc}"


def admin_run_command(command: list[str], job_id: str | None = None, timeout_seconds: int = 7200) -> tuple[int, str]:
    load_local_credentials()
    env = os.environ.copy()
    env.update(load_local_credentials())
    env["OP_SALES_USE_SQL_SERVER"] = "1"
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=Path.cwd(),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output_lines: list[str] = []
    output_queue: queue.Queue[str] = queue.Queue()

    def read_process_output() -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            output_queue.put(line.rstrip())

    reader = threading.Thread(target=read_process_output, daemon=True)
    reader.start()
    output_index = 0
    try:
        while True:
            try:
                clean_line = output_queue.get(timeout=0.2)
                output_lines.append(clean_line)
                output_index += 1
                if job_id:
                    admin_job_log_process_output(job_id, clean_line, output_index)
            except queue.Empty:
                pass
            if process.poll() is not None:
                break
            if time.monotonic() - started > timeout_seconds:
                process.kill()
                raise subprocess.TimeoutExpired(command, timeout_seconds, output="\n".join(output_lines))
            time.sleep(0.2)
    finally:
        reader.join(timeout=1)
        while True:
            try:
                output_lines.append(output_queue.get_nowait())
            except queue.Empty:
                break
        if process.stdout is not None:
            process.stdout.close()
    return int(process.returncode or 0), "\n".join(output_lines).strip()


def run_admin_etl_job(
    job_id: str,
    commands: list[tuple[str, list[str]]],
    is_dry_run: bool,
    data: dict[str, pd.DataFrame],
    data_dir: Path,
    forecast_dir: Path | None,
) -> None:
    final_status = "done"
    try:
        for step_number, (title, command) in enumerate(commands, start=1):
            step_index = step_number - 1
            admin_job_start_step(job_id, step_index)
            admin_job_append(job_id, "")
            admin_job_append(job_id, f"Paso {step_number}/{len(commands)}: {title}")
            admin_job_append(job_id, f"Comando: {' '.join(command)}")
            try:
                code, output = admin_run_command(command, job_id=job_id)
            except subprocess.TimeoutExpired as exc:
                partial = "\n".join(part for part in [getattr(exc, "stdout", "") or getattr(exc, "output", "") or "", exc.stderr or ""] if part)
                if partial:
                    admin_job_append(job_id, "Salida parcial antes del timeout:")
                    for line in partial.splitlines()[-12:]:
                        admin_job_append(job_id, f"  {line[:260]}")
                admin_job_append(job_id, "ERROR: tiempo maximo agotado.")
                admin_job_finish_step(job_id, step_index, False)
                admin_job_finish(job_id, "error")
                return
            except Exception as exc:
                admin_job_append(job_id, f"ERROR ejecutando comando: {exc}")
                admin_job_finish_step(job_id, step_index, False)
                admin_job_finish(job_id, "error")
                return

            admin_job_append(job_id, f"Codigo de salida: {code}")
            if code != 0:
                if output:
                    admin_job_append(job_id, "Ultimas lineas del proceso:")
                    for line in output.splitlines()[-12:]:
                        admin_job_append(job_id, f"  {line[:260]}")
                admin_job_append(job_id, "Proceso detenido por error. SQL no queda marcado como listo hasta corregir este punto.")
                admin_job_finish_step(job_id, step_index, False)
                admin_job_finish(job_id, "error")
                return
            admin_job_finish_step(job_id, step_index, True)

        if not is_dry_run:
            admin_job_append(job_id, "")
            admin_job_append(job_id, "Recargando datos del Dash en memoria...")
            try:
                data.clear()
                data.update(load_data(data_dir, forecast_dir))
                admin_job_append(job_id, "Datos del Dash recargados en memoria.")
            except Exception as exc:
                admin_job_append(job_id, f"La carga termino, pero no se pudo recargar el Dash en memoria: {exc}")
                admin_job_append(job_id, "Reinicia el Dash para ver todos los cambios.")
                final_status = "warning"

        admin_job_append(job_id, "")
        admin_job_append(job_id, "Consultando estado SQL despues del proceso...")
        coverage, batches, status_error = admin_sql_status()
        if status_error:
            admin_job_append(job_id, status_error)
            final_status = "warning"
        elif not coverage.empty:
            rows = coverage.attrs.get("filas", 0)
            loaded_to = coverage.attrs.get("fecha_max", "")
            admin_job_append(job_id, f"SQL actualizado hasta: {loaded_to or 'Sin datos'} | filas: {moneyless_number(rows, 0)}")
            if not batches.empty:
                latest = batches.head(1).to_dict("records")[0]
                admin_job_append(job_id, f"Ultima carga: {latest.get('Estado', '')} | insertadas: {latest.get('Filas insertadas', '')}")

        admin_job_append(job_id, "Listo para trabajar." if not is_dry_run else "Validacion terminada; no se escribio en SQL.")
        admin_job_finish(job_id, final_status)
    except Exception as exc:
        admin_job_append(job_id, f"ERROR inesperado en ejecucion Admin: {exc}")
        admin_job_finish(job_id, "error")


def render_admin_tab() -> html.Div:
    coverage, batches, message = admin_sql_status()
    today = pd.Timestamp.today().normalize()
    next_start = coverage.attrs.get("next_start", "") if not coverage.empty else ""
    loaded_from = coverage.attrs.get("fecha_min", "") if not coverage.empty else ""
    loaded_to = coverage.attrs.get("fecha_max", "") if not coverage.empty else ""
    loaded_rows = moneyless_number(coverage.attrs.get("filas", 0), 0) if not coverage.empty else "0"
    loaded_days = moneyless_number(coverage.attrs.get("dias", 0), 0) if not coverage.empty else "0"
    clientes_perfil = moneyless_number(coverage.attrs.get("clientes_perfil", 0), 0) if not coverage.empty else "0"
    clientes_ventas = moneyless_number(coverage.attrs.get("clientes_ventas", 0), 0) if not coverage.empty else "0"
    clientes_sku = moneyless_number(coverage.attrs.get("clientes_sku", 0), 0) if not coverage.empty else "0"
    forecast_futuro = moneyless_number(coverage.attrs.get("forecast_futuro", 0), 0) if not coverage.empty else "0"
    default_end = today.strftime("%Y-%m-%d")
    default_start = next_start or (today - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    if pd.to_datetime(default_start, errors="coerce") > today:
        default_start = default_end
    coverage_cards = html.Div(
        [
            html.Div([html.Div("Desde SQL", className="admin-card-label"), html.Div(loaded_from or "Sin datos", className="admin-card-value")], className="admin-status-card"),
            html.Div([html.Div("Hasta SQL", className="admin-card-label"), html.Div(loaded_to or "Sin datos", className="admin-card-value")], className="admin-status-card admin-status-card-accent"),
            html.Div([html.Div("Siguiente sugerido", className="admin-card-label"), html.Div(default_start, className="admin-card-value")], className="admin-status-card"),
            html.Div([html.Div("Filas / dias", className="admin-card-label"), html.Div(f"{loaded_rows} / {loaded_days}", className="admin-card-value")], className="admin-status-card"),
            html.Div([html.Div("Clientes perfil / ventas", className="admin-card-label"), html.Div(f"{clientes_perfil} / {clientes_ventas}", className="admin-card-value")], className="admin-status-card"),
            html.Div([html.Div("Clientes SKU", className="admin-card-label"), html.Div(clientes_sku, className="admin-card-value")], className="admin-status-card"),
            html.Div([html.Div("Forecast futuro", className="admin-card-label"), html.Div(forecast_futuro, className="admin-card-value")], className="admin-status-card"),
        ],
        className="admin-status-grid",
    )
    admin_guidance = html.Div(
        [
            html.Div("Como decidir la carga", className="panel-title"),
            html.Div(
                [
                    html.Div("1. Si SQL llega hasta una fecha anterior, carga desde el dia siguiente hasta la fecha nueva.", className="admin-guidance-item"),
                    html.Div("2. Usa Validar sin escribir antes de cargar si no estas seguro del rango.", className="admin-guidance-item"),
                    html.Div("3. Reconstruir agregados SQL del Dash debe quedar marcado casi siempre: actualiza las vistas rapidas que lee Ventas generales.", className="admin-guidance-item"),
                    html.Div("4. Descriptivos no siempre son obligatorios. Correlos cuando quieras actualizar perfiles, SKUs, estructuras, resumen de clientes o forecast con la historia nueva.", className="admin-guidance-item"),
                ],
                className="admin-guidance-list",
            ),
        ],
        className="admin-guidance",
    )
    status_block = (
        html.Div(message, className="panel-note")
        if message
        else html.Div(
            [
                html.Div("Cobertura actual en SQL", className="panel-title"),
                make_table(coverage, 5),
                html.Div("Ultimas cargas", className="panel-title section-gap"),
                make_table(batches, 8),
            ],
            className="table-panel",
        )
    )
    return html.Div(
        [
            html.Div(
                [
                    html.Div("Administrador", className="admin-hero-title"),
                    html.Div("Carga controlada de ventas a SQL Server y preparacion de datos para el Dash.", className="admin-hero-subtitle"),
                    coverage_cards,
                ],
                className="admin-hero",
            ),
            html.Div(
                [
                    dcc.Store(id="admin-run-job", data=None),
                    dcc.Interval(id="admin-run-poll", interval=1000, n_intervals=0, disabled=True),
                    html.Div("Datos en memoria", className="panel-title"),
                    panel_note("Recarga las tablas que el Dash ya consulta desde SQL sin ejecutar ETL ni pedir clave."),
                    html.Div(
                        [
                            html.Button("Recargar datos del Dash", id="admin-refresh-data", n_clicks=0, type="button", className="executive-button secondary"),
                            html.Div(id="admin-refresh-status", className="panel-note"),
                        ],
                        className="executive-button-group",
                    ),
                    html.Div("Nueva carga", className="panel-title section-gap"),
                    panel_note("Ingresa la clave de administrador. El rango se inicializa con el siguiente dia sugerido segun SQL."),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Contrasena"),
                                    dcc.Input(id="admin-password", type="password", value="", placeholder="Clave de administrador", className="admin-input"),
                                ],
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Rango ETL"),
                                    dcc.DatePickerRange(
                                        id="admin-date-range",
                                        start_date=default_start,
                                        end_date=default_end,
                                        display_format="YYYY-MM-DD",
                                    ),
                                ],
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Particionar carga"),
                                    dcc.Dropdown(
                                        id="admin-split-by",
                                        options=[
                                            {"label": "Sin partir", "value": "none"},
                                            {"label": "Por mes", "value": "month"},
                                            {"label": "Por ano", "value": "year"},
                                        ],
                                        value="none",
                                        clearable=False,
                                    ),
                                ],
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Filas por lote"),
                                    dcc.Input(id="admin-chunk-size", type="number", min=100, step=100, value=5000, className="admin-input"),
                                ],
                                className="demand-control",
                            ),
                        ],
                        className="grid-2",
                    ),
                    html.Div(
                        [
                            html.Label("Acciones adicionales"),
                            dcc.Checklist(
                                id="admin-extra-actions",
                                options=[
                                    {"label": "Reconstruir agregados SQL del Dash", "value": "materialize"},
                                    {"label": "Regenerar descriptivos desde SQL", "value": "descriptivos"},
                                    {"label": "Regenerar forecast solidos", "value": "forecast"},
                                ],
                                value=["materialize"],
                                inputStyle={"marginRight": "8px"},
                                labelStyle={"display": "block"},
                            ),
                        ],
                        className="demand-control",
                    ),
                    html.Div(
                        [
                            html.Button("Validar sin escribir", id="admin-dry-run", n_clicks=0, type="button", className="executive-button secondary"),
                            html.Button("Ejecutar ETL y cargar SQL", id="admin-run-etl", n_clicks=0, type="button", className="executive-button primary"),
                        ],
                        className="executive-button-group",
                    ),
                    html.Pre(id="admin-run-output", className="admin-output"),
                ],
                className="table-panel",
            ),
            admin_guidance,
            status_block,
        ],
        className="section-gap",
    )


def build_client_dropdown_options(perfil: pd.DataFrame) -> list[dict[str, str]]:
    if perfil.empty or "cod_cliente" not in perfil.columns:
        return []
    cols = [col for col in ["cod_cliente", "cliente"] if col in perfil.columns]
    rows = perfil[cols].drop_duplicates("cod_cliente").head(5000)
    options = []
    for row in rows.itertuples(index=False):
        code = str(getattr(row, "cod_cliente"))
        name = str(getattr(row, "cliente", "") or "").strip()
        label = f"{code} | {name}" if name else code
        options.append({"label": label, "value": code})
    return options


def load_data(
    data_dir: Path,
    forecast_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Carga outputs independientes para construir las vistas del dashboard.

    ``data_dir`` contiene descriptivos y ``forecast_dir`` contiene solo el
    forecast de solidos.
    """
    eager_results = os.getenv("OP_SALES_EAGER_RESULTS", "0").strip().lower() in {"1", "true", "yes", "si"}
    perfil = read_result_or_csv("op_sales.result_descriptivo_perfil_cliente", data_dir / "perfil_cliente.csv", PROFILE_COLS)
    if not perfil.empty:
        perfil["cod_cliente"] = normalize_code(perfil["cod_cliente"])
        if "ultima_fecha_confirmada" in perfil.columns:
            perfil["ultima_fecha_confirmada"] = pd.to_datetime(perfil["ultima_fecha_confirmada"], errors="coerce")
        if "dias_desde_ultima_compra" not in perfil.columns and "ultima_fecha_confirmada" in perfil.columns:
            perfil["dias_desde_ultima_compra"] = (perfil["ultima_fecha_confirmada"].max() - perfil["ultima_fecha_confirmada"]).dt.days
        perfil = perfil.sort_values(["score_compra_terminada", "tallos_total"], ascending=False)

    serie = read_result_or_csv("op_sales.result_descriptivo_serie_cliente_semana", data_dir / "serie_cliente_semana.csv", SERIE_COLS)
    if not serie.empty:
        serie["cod_cliente"] = normalize_code(serie["cod_cliente"])
        serie["semana_orden"] = serie["anio"].astype(int) * 100 + serie["semana_iso"].astype(int)
        serie["week_start"] = pd.to_datetime(
            serie["anio"].astype(int).astype(str)
            + "-W"
            + serie["semana_iso"].astype(int).astype(str).str.zfill(2)
            + "-1",
            format="%G-W%V-%u",
            errors="coerce",
        )
        serie = serie.sort_values(["cod_cliente", "semana_orden"])
        if not perfil.empty:
            max_week = serie["week_start"].max()
            recency = serie.groupby(["cod_cliente", "cliente"], as_index=False).agg(
                ultima_fecha_confirmada=("week_start", "max"),
            )
            recency["dias_desde_ultima_compra"] = (max_week - recency["ultima_fecha_confirmada"]).dt.days
            for weeks in [8, 12, 26, 52]:
                recent = serie[serie["week_start"] >= max_week - pd.Timedelta(weeks=weeks)]
                recent_summary = recent.groupby(["cod_cliente", "cliente"], as_index=False).agg(
                    **{
                        f"semanas_activas_ult_{weeks}w": ("anio_semana", "nunique"),
                        f"tallos_ult_{weeks}w": ("tallos", "sum"),
                    }
                )
                recency = recency.merge(recent_summary, on=["cod_cliente", "cliente"], how="left")
                recency[f"semanas_activas_ult_{weeks}w"] = recency[f"semanas_activas_ult_{weeks}w"].fillna(0).astype(int)
                recency[f"tallos_ult_{weeks}w"] = recency[f"tallos_ult_{weeks}w"].fillna(0)
            recency["cliente_activo_ult_16w"] = recency["dias_desde_ultima_compra"].fillna(99999).le(16 * 7)
            drop_cols = [col for col in recency.columns if col in perfil.columns and col not in ["cod_cliente", "cliente"]]
            perfil = perfil.drop(columns=drop_cols).merge(recency, on=["cod_cliente", "cliente"], how="left")

    mix_producto = read_result_or_csv("op_sales.result_descriptivo_mix_producto", data_dir / "mix_producto.csv", MIX_COMMON_COLS + ["producto"]) if eager_results else pd.DataFrame()
    mix_color = read_result_or_csv("op_sales.result_descriptivo_mix_color", data_dir / "mix_color.csv", MIX_COMMON_COLS + ["color"]) if eager_results else pd.DataFrame()
    mix_tipo = read_result_or_csv(
        "op_sales.result_descriptivo_mix_tipo_pedido",
        data_dir / "mix_tipo_pedido.csv",
        MIX_COMMON_COLS + ["tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_empaque", "receta"],
    ) if eager_results else pd.DataFrame()
    mix_sku = read_result_or_csv(
        "op_sales.result_descriptivo_mix_sku_terminado",
        data_dir / "mix_sku_terminado.csv",
        MIX_COMMON_COLS
        + [
            "sku_terminado",
            "tipo_pedido_operativo",
            "familia_analisis_operativa",
            "enfoque_analisis_operativo",
            "rol_color_operativo",
            "producto",
            "variedad",
            "color",
            "grado",
            "tipo_caja",
            "tallos_x_ramo",
            "llave_analisis_operativo",
        ],
    ) if eager_results else pd.DataFrame()
    mix_analisis = read_result_or_csv(
        "op_sales.result_descriptivo_mix_analisis_operativo",
        data_dir / "mix_analisis_operativo.csv",
        MIX_COMMON_COLS
        + [
            "familia_analisis_operativa",
            "enfoque_analisis_operativo",
            "rol_color_operativo",
            "llave_analisis_operativo",
            "tipo_pedido_operativo",
            "producto",
            "color",
            "tipo_caja",
            "receta",
        ],
    ) if eager_results else pd.DataFrame()
    mix_color_rol = read_result_or_csv(
        "op_sales.result_descriptivo_mix_color_rol",
        data_dir / "mix_color_rol.csv",
        MIX_COMMON_COLS + ["familia_analisis_operativa", "rol_color_operativo", "tipo_pedido_operativo", "producto", "color"],
    ) if eager_results else pd.DataFrame()
    for frame in [mix_producto, mix_color, mix_tipo, mix_sku, mix_analisis, mix_color_rol]:
        if not frame.empty:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])

    demanda = read_csv_if_exists(data_dir / "demanda_operativa_futura.csv", DEMAND_COLS, ["fecha_forecast"])
    if not demanda.empty:
        demanda["cod_cliente"] = normalize_code(demanda["cod_cliente"])
        demanda = add_week_columns(demanda, "fecha_forecast")

    estimados = read_csv_if_exists(data_dir / "estimados_comerciales_estructura.csv", ESTIMADOS_COLS, ["fecha"])
    if not estimados.empty:
        estimados["cod_cliente"] = normalize_code(estimados["cod_cliente"])
        estimados = estimados.rename(columns={"fecha": "fecha_forecast", "tallos": "tallos_estimados"})

    forecast_historico = read_csv_if_exists(data_dir / "forecast_historico_confirmado.csv", DEMAND_COLS, ["fecha_forecast"])
    if not forecast_historico.empty:
        forecast_historico["cod_cliente"] = normalize_code(forecast_historico["cod_cliente"])
        forecast_historico = add_week_columns(forecast_historico, "fecha_forecast")

    cruce = read_csv_if_exists(data_dir / "cruce_forecast_inventario.csv", INVENTORY_COLS, ["fecha_forecast"])
    if not cruce.empty:
        cruce["cod_cliente"] = normalize_code(cruce["cod_cliente"])
        cruce = add_week_columns(cruce, "fecha_forecast")

    inventario_color = read_csv_if_exists(data_dir / "inventario_fecha_color.csv", INVENTORY_COLOR_COLS, ["fecha"])
    if not inventario_color.empty:
        inventario_color = inventario_color.rename(columns={"fecha": "fecha_forecast"})
        inventario_color = add_week_columns(inventario_color, "fecha_forecast")

    dashboard_db = DEFAULT_DASHBOARD_DB
    historico_visualizador_comercial = pd.DataFrame()
    historico_confirmado = pd.DataFrame()
    for history_frame in [historico_confirmado, historico_visualizador_comercial]:
        if history_frame.empty:
            continue
        history_frame["cod_cliente"] = normalize_code(history_frame["cod_cliente"])
        tallos_source = history_frame.get(
            "tallos_analisis",
            history_frame.get("tallos_total", history_frame.get("tallos_confirmados", pd.Series(0, index=history_frame.index))),
        )
        history_frame["tallos_historicos"] = pd.to_numeric(tallos_source, errors="coerce").fillna(0)
        if "ventas_usd" not in history_frame.columns:
            history_frame["ventas_usd"] = 0.0
        history_frame["ventas_usd"] = pd.to_numeric(history_frame["ventas_usd"], errors="coerce").fillna(0)
        for col in ["VALORUNITARIO", "VALORTOTAL"]:
            if col in history_frame.columns:
                history_frame[col] = pd.to_numeric(history_frame[col], errors="coerce").fillna(0)
        if "NomMoneda" not in history_frame.columns:
            history_frame["NomMoneda"] = "SIN_MONEDA"
        if "fecha" in history_frame.columns:
            enriched = add_week_columns(history_frame, "fecha")
            history_frame[enriched.columns] = enriched
    historico_solidos = historico_confirmado.copy()
    if not historico_solidos.empty:
        historico_solidos = historico_solidos[
            historico_solidos["tipo_pedido_operativo"].astype(str).str.upper().eq("SOLIDO")
        ].copy()

    estado = read_result_or_csv("op_sales.result_descriptivo_estado_resumen", data_dir / "estado_resumen.csv")

    forecast_dir = forecast_dir or DEFAULT_FORECAST_DIR
    solid_forecast_source = read_result_or_csv("op_sales.result_forecast_solid_forecast_fuente_datos", forecast_dir / "solid_forecast_fuente_datos.csv", parse_dates=["fecha_min", "fecha_max"])
    solid_forecast_eval = read_result_or_csv("op_sales.result_forecast_solid_forecast_model_evaluation", forecast_dir / "solid_forecast_model_evaluation.csv")
    solid_forecast_importance = read_result_or_csv("op_sales.result_forecast_solid_forecast_feature_importance", forecast_dir / "solid_forecast_feature_importance.csv")
    solid_forecast_market_importance = read_result_or_csv("op_sales.result_forecast_solid_forecast_market_feature_importance", forecast_dir / "solid_forecast_market_feature_importance.csv")
    solid_forecast_market_calibration = read_result_or_csv("op_sales.result_forecast_solid_forecast_market_calibration", forecast_dir / "solid_forecast_market_calibration.csv")
    solid_forecast_predictors = read_result_or_csv("op_sales.result_forecast_solid_forecast_predictors", forecast_dir / "solid_forecast_predictors.csv")
    solid_forecast_weekly = read_result_or_csv("op_sales.result_forecast_solid_forecast_weekly_demand", forecast_dir / "solid_forecast_weekly_demand.csv", parse_dates=["week_start"])
    solid_forecast_test = read_result_or_csv("op_sales.result_forecast_solid_forecast_test_predictions", forecast_dir / "solid_forecast_test_predictions.csv", parse_dates=["week_start"])
    solid_forecast_historical_validation = read_result_or_csv("op_sales.result_forecast_solid_forecast_historical_validation", forecast_dir / "solid_forecast_historical_validation.csv", parse_dates=["week_start"])
    solid_forecast_future = read_result_or_csv("op_sales.result_forecast_solid_forecast_future", forecast_dir / "solid_forecast_future.csv", parse_dates=["week_start"])
    solid_forecast_error_market = read_result_or_csv("op_sales.result_forecast_solid_forecast_error_by_market", forecast_dir / "solid_forecast_error_by_market.csv")
    for frame in [solid_forecast_weekly, solid_forecast_test, solid_forecast_historical_validation, solid_forecast_future]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
        if not frame.empty:
            for col in ["tallos", "prediccion", "tallos_estimados", "anio", "semana_iso", "probabilidad_compra", "volumen_si_compra"]:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    estructuras = read_result_or_csv("op_sales.result_descriptivo_cliente_estructuras_repetidas", data_dir / "cliente_estructuras_repetidas.csv", STRUCTURE_COLS) if eager_results else pd.DataFrame()
    if not estructuras.empty:
        estructuras["cod_cliente"] = normalize_code(estructuras["cod_cliente"])

    semana_tipica = read_result_or_csv("op_sales.result_descriptivo_cliente_semana_tipica", data_dir / "cliente_semana_tipica.csv", TYPICAL_WEEK_COLS) if eager_results else pd.DataFrame()
    if not semana_tipica.empty:
        semana_tipica["cod_cliente"] = normalize_code(semana_tipica["cod_cliente"])
        semana_tipica["semana"] = pd.to_numeric(semana_tipica["semana"], errors="coerce").astype("Int64")

    sku_resumen = read_result_or_csv("op_sales.result_descriptivo_cliente_sku_operativo_resumen", data_dir / "cliente_sku_operativo_resumen.csv", SKU_SUMMARY_COLS)
    sku_composicion = read_result_or_csv("op_sales.result_descriptivo_cliente_sku_operativo_composicion", data_dir / "cliente_sku_operativo_composicion.csv", SKU_COMPOSITION_COLS)
    semana_sku = read_result_or_csv("op_sales.result_descriptivo_cliente_semana_sku_operativo", data_dir / "cliente_semana_sku_operativo.csv", WEEK_SKU_COLS) if eager_results else pd.DataFrame()
    for frame in [sku_resumen, sku_composicion, semana_sku]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])

    ventas_semana = read_op_sales_sql_table("op_sales.agg_sales_week_client_product")
    if ventas_semana.empty:
        ventas_semana = read_dashboard_sql_view(dashboard_db, "vw_ventas_generales_semana_cliente_producto")
    if ventas_semana.empty:
        ventas_semana = read_csv_if_exists(data_dir / "ventas_semana_cliente_producto.csv", SALES_VISUAL_COLS)
    ventas_producto = read_result_or_csv("op_sales.result_descriptivo_ventas_producto_periodo", data_dir / "ventas_producto_periodo.csv", [col for col in SALES_VISUAL_COLS if col not in ["cod_cliente", "cliente"]]) if eager_results else pd.DataFrame()
    ventas_cliente = read_result_or_csv("op_sales.result_descriptivo_ventas_cliente_periodo", data_dir / "ventas_cliente_periodo.csv", ["anio", "semana_iso", "anio_semana", "cod_cliente", "cliente", "moneda_original", "tallos_confirmados", "ventas_usd", "valor_total_original", "pedidos", "cajas_ids", "precio_usd_tallo", "precio_moneda_original_tallo"]) if eager_results else pd.DataFrame()
    ventas_caja = read_result_or_csv("op_sales.result_descriptivo_ventas_caja_periodo", data_dir / "ventas_caja_periodo.csv", SALES_BOX_COLS) if eager_results else pd.DataFrame()
    for frame in [ventas_semana, ventas_cliente, ventas_caja]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
    for frame in [ventas_semana, ventas_producto, ventas_cliente, ventas_caja]:
        if not frame.empty:
            for col in ["anio", "semana_iso", "tallos_confirmados", "ventas_usd", "valor_total_original", "precio_usd_tallo", "precio_moneda_original_tallo"]:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    estructura_caja = read_result_or_csv("op_sales.result_descriptivo_estructura_caja", data_dir / "estructura_caja.csv", STRUCTURE_BOX_COLS, ["fecha"]) if eager_results else pd.DataFrame()
    estructura_componentes = read_result_or_csv("op_sales.result_descriptivo_estructura_componentes", data_dir / "estructura_componentes.csv", STRUCTURE_COMPONENT_COLS, ["fecha"]) if eager_results else pd.DataFrame()
    catalogo_estructura_version = read_result_or_csv(
        "op_sales.result_descriptivo_catalogo_estructura_version",
        data_dir / "catalogo_estructura_version.csv",
        STRUCTURE_VERSION_COLS,
        ["primera_fecha", "ultima_fecha"],
    ) if eager_results else pd.DataFrame()
    for frame in [estructura_caja, estructura_componentes, catalogo_estructura_version]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
    for frame in [estructura_caja, estructura_componentes, catalogo_estructura_version]:
        if not frame.empty:
            for col in [
                "lineas_componentes", "tallos_estructura", "ramos_componentes", "ramos_estimados",
                "tallos_analisis", "ramos_pedidos", "ramos_estimados_linea", "participacion_tallos_estructura",
                "veces_observada", "semanas_observada", "tallos_promedio_estructura", "ramos_promedio_estimados",
            ]:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    return {
        "perfil": perfil,
        "serie": serie,
        "mix_producto": mix_producto,
        "mix_color": mix_color,
        "mix_tipo": mix_tipo,
        "mix_sku": mix_sku,
        "mix_analisis": mix_analisis,
        "mix_color_rol": mix_color_rol,
        "demanda": demanda,
        "estimados": estimados,
        "forecast_historico": forecast_historico,
        "cruce": cruce,
        "inventario_color": inventario_color,
        "historico_confirmado": historico_confirmado,
        "historico_visualizador_comercial": historico_visualizador_comercial,
        "historico_solidos": historico_solidos,
        "estructuras": estructuras,
        "semana_tipica": semana_tipica,
        "sku_resumen": sku_resumen,
        "sku_composicion": sku_composicion,
        "semana_sku": semana_sku,
        "ventas_semana": ventas_semana,
        "ventas_producto": ventas_producto,
        "ventas_cliente": ventas_cliente,
        "ventas_caja": ventas_caja,
        "estructura_caja": estructura_caja,
        "estructura_componentes": estructura_componentes,
        "catalogo_estructura_version": catalogo_estructura_version,
        "estado": estado,
        "solid_forecast_source": solid_forecast_source,
        "solid_forecast_eval": solid_forecast_eval,
        "solid_forecast_importance": solid_forecast_importance,
        "solid_forecast_market_importance": solid_forecast_market_importance,
        "solid_forecast_market_calibration": solid_forecast_market_calibration,
        "solid_forecast_predictors": solid_forecast_predictors,
        "solid_forecast_weekly": solid_forecast_weekly,
        "solid_forecast_test": solid_forecast_test,
        "solid_forecast_historical_validation": solid_forecast_historical_validation,
        "solid_forecast_future": solid_forecast_future,
        "solid_forecast_error_market": solid_forecast_error_market,
    }


def empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="Sin datos para los filtros seleccionados", x=0.5, y=0.5, showarrow=False)
    fig.update_layout(title=title, template="plotly_white", height=360)
    return apply_common_layout(fig, 360)


def normalize_category(value) -> str:
    return str(value or "").upper().replace("Ã", "A").replace("Ã‰", "E").replace("Ã", "I").replace("Ã“", "O").replace("Ãš", "U").strip()


def color_for_category(value, index: int = 0) -> str:
    text = normalize_category(value)
    for key, color in REGION_COLOR_MAP.items():
        if normalize_category(key) in text:
            return color
    for key, color in FLOWER_COLOR_KEYWORDS.items():
        if key in text:
            return color
    if text in {"SIN_INFO", "SIN COLOR", "NAN", "NONE", ""}:
        return REGION_FALLBACK_COLOR
    return CORPORATE_SEQUENCE[index % len(CORPORATE_SEQUENCE)]


def category_color_map(values) -> dict[str, str]:
    unique = []
    for value in values:
        text = str(value)
        if text not in unique:
            unique.append(text)
    return {value: color_for_category(value, i) for i, value in enumerate(unique)}


def color_map_for(df: pd.DataFrame, column: str) -> dict[str, str]:
    if df.empty or column not in df.columns:
        return {}
    return category_color_map(df[column].dropna().astype(str).tolist())


def apply_pie_label_style(fig: go.Figure) -> go.Figure:
    fig.update_traces(textfont_color=GRAPH_TEXT, marker_line_color=GRAPH_LABEL_LINE, marker_line_width=1)
    return fig


def apply_common_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=24, r=24, t=56, b=40),
        legend_title_text="",
        font=dict(family="Arial, sans-serif", size=12, color=GRAPH_TEXT),
        paper_bgcolor=GRAPH_CONTAINER_BG,
        plot_bgcolor=GRAPH_CONTAINER_BG,
        colorway=CORPORATE_SEQUENCE,
    )
    fig.update_xaxes(gridcolor="#E5E7EB", zerolinecolor="#D1D5DB")
    fig.update_yaxes(gridcolor="#E5E7EB", zerolinecolor="#D1D5DB")
    return fig


def make_card(title: str, value: str, detail: str = "") -> html.Div:
    return html.Div(
        [html.Div(title, className="metric-title"), html.Div(value, className="metric-value"), html.Div(detail, className="metric-detail")],
        className="metric-card",
    )


def make_year_comparison_card(
    title: str,
    annual: pd.DataFrame,
    metric: str,
    formatter,
    detail: str,
) -> html.Div:
    """Render a metric by selected year with change against the prior visible year."""
    rows = []
    previous_value = None
    previous_year = None
    for row in annual.sort_values("anio").itertuples(index=False):
        year = int(getattr(row, "anio"))
        value = float(getattr(row, metric))
        if previous_value is None:
            delta = "base"
            delta_class = "year-delta neutral"
        elif previous_value == 0:
            delta = "nuevo" if value else "0.00%"
            delta_class = "year-delta positive" if value else "year-delta neutral"
        else:
            change = (value - previous_value) / previous_value
            delta = f"{change:+.2%} vs {previous_year}"
            delta_class = "year-delta positive" if change >= 0 else "year-delta negative"
        rows.append(
            html.Div(
                [
                    html.Span(str(year), className="year-label"),
                    html.Span(formatter(value), className="year-value"),
                    html.Span(delta, className=delta_class),
                ],
                className="year-row",
            )
        )
        previous_value = value
        previous_year = year
    return html.Div(
        [html.Div(title, className="metric-title"), html.Div(rows, className="year-comparison"), html.Div(detail, className="metric-detail")],
        className="metric-card metric-card-comparison",
    )


def make_delta_card(title: str, value: str, delta_value: float | None, detail: str = "") -> html.Div:
    """Metric card with an explicit percentage change badge."""
    if delta_value is None or pd.isna(delta_value):
        delta_text = "sin base"
        delta_class = "delta-badge neutral"
    else:
        delta_text = f"{delta_value:+.2%}"
        delta_class = "delta-badge positive" if delta_value >= 0 else "delta-badge negative"
    return html.Div(
        [
            html.Div([html.Div(title, className="metric-title"), html.Span(delta_text, className=delta_class)], className="metric-card-head"),
            html.Div(value, className="metric-value"),
            html.Div(detail, className="metric-detail"),
        ],
        className="metric-card metric-card-accent",
    )


def logo_data_uri(path: Path | None = None) -> str | None:
    path = path or resolve_logo_path()
    if path is None:
        return None
    if not path.exists():
        return None
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else "png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


def make_table(
    df: pd.DataFrame,
    page_size: int = 10,
    sort_by: list[dict[str, str]] | None = None,
    table_id: str | None = None,
) -> html.Div:
    if df.empty:
        df = pd.DataFrame({"mensaje": ["Sin datos para mostrar"]})
    numeric_cols = {
        col
        for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col])
    }
    table_kwargs = {"id": {"type": "managed-table", "index": table_id}} if table_id else {}
    table_component = dash_table.DataTable(
        **table_kwargs,
        data=df.to_dict("records"),
        columns=[
            {"name": col, "id": col, "type": "numeric"} if col in numeric_cols else {"name": col, "id": col}
            for col in df.columns
        ],
        page_size=page_size,
        sort_action="native",
        sort_by=sort_by or [],
        filter_action="native",
        export_format="xlsx",
        style_table={"overflowX": "auto", "maxHeight": "430px", "overflowY": "auto"},
        style_cell={
            "fontFamily": "Arial, sans-serif",
            "fontSize": 12,
            "padding": "7px",
            "minWidth": "90px",
            "maxWidth": "280px",
            "whiteSpace": "normal",
            "height": "auto",
        },
        style_header={"backgroundColor": CORPORATE_BURGUNDY, "color": "white", "fontWeight": "600"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f7f9fb"},
        ],
    )
    if not table_id:
        return table_component
    return html.Div(
        [
            html.Div(
                [
                    html.Button(
                        "Reiniciar filtros",
                        id={"type": "table-reset", "index": table_id},
                        n_clicks=0,
                        type="button",
                        className="table-reset-button",
                    ),
                    dcc.Store(id={"type": "table-default-sort", "index": table_id}, data=sort_by or []),
                ],
                className="table-tools",
            ),
            table_component,
        ],
        className="managed-table-wrap",
    )


def build_app(data_dir: Path, forecast_dir: Path | None = None) -> Dash:
    """Construye el tablero a partir de los modulos analiticos activos."""
    data = load_data(data_dir, forecast_dir)
    perfil = data["perfil"]

    recommendation_options = []
    segment_options = []
    client_options = []
    product_options = []
    color_options = []
    sales_year_options = []
    sales_default_years = []
    sales_base_year_options = []
    sales_default_base_year = None
    sales_default_compare_year = None
    general_sales_client_options = []
    general_sales_company_options = []
    general_sales_product_options = []
    general_sales_country_options = []
    general_sales_color_options = []
    general_sales_type_options = []
    forecast_year_options = []
    forecast_default_years = []
    forecast_market_options = []
    forecast_country_options = []
    forecast_client_options = []
    forecast_product_options = []
    forecast_color_options = []
    forecast_model_options = []
    forecast_date_min = None
    forecast_date_max = None
    validation_year_options = []
    validation_default_year = None
    validation_default_weeks = 5
    validation_start_week_options = []
    validation_default_start_week = None
    sales_week_marks = {1: "1", 13: "13", 26: "26", 39: "39", 53: "53"}
    if not perfil.empty:
        recommendation_options = [{"label": rec, "value": rec} for rec in sorted(perfil["recomendacion_compra"].dropna().unique())]
        segment_options = [{"label": seg, "value": seg} for seg in sorted(perfil["segmento_cliente"].dropna().unique())]
        client_options = build_client_dropdown_options(perfil)
    ventas_source = data.get("ventas_semana", pd.DataFrame())
    if ventas_source.empty:
        ventas_source = data.get("ventas_producto", pd.DataFrame())
    if not ventas_source.empty and "anio" in ventas_source.columns:
        years = sorted(pd.to_numeric(ventas_source["anio"], errors="coerce").dropna().astype(int).unique())
        sales_year_options = [{"label": str(year), "value": int(year)} for year in years]
        sales_default_years = years[-2:] if len(years) >= 2 else years
        sales_base_year_options = [{"label": str(year), "value": int(year)} for year in years]
        sales_default_base_year = years[-2] if len(years) >= 2 else (years[0] if years else None)
        sales_default_compare_year = years[-1] if years else None
        if "cod_cliente" in ventas_source.columns and "cliente" in ventas_source.columns:
            sales_clients = (
                ventas_source[["cod_cliente", "cliente"]]
                .drop_duplicates()
                .sort_values(["cliente", "cod_cliente"])
            )
            general_sales_client_options = [
                {"label": f"{row.cliente} | {row.cod_cliente}", "value": str(row.cod_cliente)}
                for row in sales_clients.itertuples(index=False)
            ]
        if "NomCompania" in ventas_source.columns:
            general_sales_company_options = [
                {"label": company, "value": company}
                for company in sorted(ventas_source["NomCompania"].dropna().astype(str).unique())
                if company.strip()
            ]
        if "producto" in ventas_source.columns:
            general_sales_product_options = [
                {"label": product, "value": product}
                for product in sorted(ventas_source["producto"].dropna().astype(str).unique())
            ]
        if "color" in ventas_source.columns:
            general_sales_color_options = [
                {"label": color, "value": color}
                for color in sorted(ventas_source["color"].dropna().astype(str).unique())
                if color.strip()
            ]
        if "pais" in ventas_source.columns:
            general_sales_country_options = [
                {"label": country, "value": country}
                for country in sorted(ventas_source["pais"].dropna().astype(str).unique())
            ]
        if "tipo_pedido_operativo" in ventas_source.columns:
            general_sales_type_options = [
                {"label": tipo, "value": tipo}
                for tipo in sorted(ventas_source["tipo_pedido_operativo"].dropna().astype(str).unique())
                if tipo.strip()
            ]
    product_sources = [
        frame
        for frame in [data["demanda"], data["forecast_historico"], data["cruce"], data["historico_solidos"]]
        if not frame.empty and "producto" in frame.columns
    ]
    if product_sources:
        products = pd.concat([frame[["producto"]] for frame in product_sources], ignore_index=True)
        product_options = [
            {"label": product, "value": product}
            for product in sorted(products["producto"].dropna().astype(str).unique())
        ]
        color_sources = [frame[["color"]] for frame in product_sources if "color" in frame.columns]
        if color_sources:
            colors = pd.concat(color_sources, ignore_index=True)
            color_options = [
                {"label": color, "value": color}
                for color in sorted(colors["color"].dropna().astype(str).unique())
            ]
    forecast_sources = [
        frame
        for frame in [data.get("solid_forecast_weekly", pd.DataFrame()), data.get("solid_forecast_future", pd.DataFrame())]
        if not frame.empty
    ]
    if forecast_sources:
        forecast_scope = pd.concat(forecast_sources, ignore_index=True)
        forecast_history_scope = data.get("solid_forecast_weekly", pd.DataFrame())
        if forecast_history_scope.empty:
            forecast_history_scope = forecast_scope
        dates = pd.to_datetime(forecast_history_scope["week_start"], errors="coerce")
        forecast_date_min = dates.min().date() if dates.notna().any() else None
        forecast_date_max = dates.max().date() if dates.notna().any() else None
        years = sorted(pd.to_numeric(forecast_history_scope["anio"], errors="coerce").dropna().astype(int).unique())
        forecast_year_options = [{"label": str(year), "value": int(year)} for year in years]
        forecast_default_years = years
        option_specs = [
            ("mercado_cluster", "forecast_market_options"),
            ("pais", "forecast_country_options"),
            ("producto", "forecast_product_options"),
            ("color", "forecast_color_options"),
        ]
        option_values = {}
        for col, name in option_specs:
            values = sorted(forecast_scope[col].dropna().astype(str).unique()) if col in forecast_scope else []
            option_values[name] = [{"label": value, "value": value} for value in values]
        forecast_market_options = option_values["forecast_market_options"]
        forecast_country_options = option_values["forecast_country_options"]
        forecast_product_options = option_values["forecast_product_options"]
        forecast_color_options = option_values["forecast_color_options"]
        clients = forecast_scope[["cod_cliente", "cliente"]].drop_duplicates().sort_values(["cliente", "cod_cliente"])
        forecast_client_options = [
            {"label": f"{row.cliente} | {row.cod_cliente}", "value": row.cod_cliente}
            for row in clients.itertuples(index=False)
        ]
    if not data.get("solid_forecast_eval", pd.DataFrame()).empty:
        evaluation = data["solid_forecast_eval"]
        selected_models = (
            evaluation[evaluation["modelo_seleccionado"].eq(True)]["modelo"].astype(str).tolist()
            if "modelo_seleccionado" in evaluation.columns
            else []
        )
        forecast_model_options = [
            {
                "label": f"{row.modelo}{' | usado' if bool(getattr(row, 'modelo_seleccionado', False)) else ''}",
                "value": str(row.modelo),
            }
            for row in evaluation.itertuples(index=False)
        ]
        forecast_default_model = selected_models[0] if selected_models else str(evaluation.iloc[0]["modelo"])
    else:
        forecast_default_model = None
    validation_source = data.get("solid_forecast_historical_validation", pd.DataFrame())
    if not validation_source.empty:
        validation_years = [
            int(year)
            for year in sorted(pd.to_numeric(validation_source["anio"], errors="coerce").dropna().unique())
            if valid_validation_window_starts(validation_source, int(year), validation_default_weeks)
        ]
        validation_year_options = [{"label": str(year), "value": year} for year in validation_years]
        validation_default_year = validation_years[-1] if validation_years else None
        if validation_default_year is not None:
            starts = valid_validation_window_starts(validation_source, validation_default_year, validation_default_weeks)
            validation_start_week_options = [
                {"label": f"Semanas {week:02d} - {week + validation_default_weeks - 1:02d}", "value": week}
                for week in starts
            ]
            validation_default_start_week = starts[0] if starts else None

    if not data.get("historico_confirmado", pd.DataFrame()).empty:
        max_hist_date = pd.to_datetime(data["historico_confirmado"]["fecha"], errors="coerce").max()
        current_week = int(max_hist_date.isocalendar().week) if pd.notna(max_hist_date) else int(pd.Timestamp.today().isocalendar().week)
    else:
        current_week = int(pd.Timestamp.today().isocalendar().week)
    app = Dash(__name__, title="LGF Analitica Comercial", suppress_callback_exceptions=True)

    @app.callback(
        Output({"type": "managed-table", "index": MATCH}, "filter_query"),
        Output({"type": "managed-table", "index": MATCH}, "sort_by"),
        Input({"type": "table-reset", "index": MATCH}, "n_clicks"),
        State({"type": "table-default-sort", "index": MATCH}, "data"),
        prevent_initial_call=True,
    )
    def reset_managed_table_filters(n_clicks, default_sort):
        if not n_clicks:
            return dash.no_update, dash.no_update
        return "", default_sort or []

    app.layout = html.Div(
        [
            dcc.Store(id="data-dir", data=str(data_dir)),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("LGF Analitica Comercial"),
                            html.P("Visualizador de clientes, ventas, estructuras y forecast historico de solidos."),
                        ],
                        className="header-copy",
                    ),
                    html.Div(
                        [
                            html.Div(f"Fuente: {data_dir.resolve()}", className="source-line"),
                            html.Div("Dash + Plotly", className="tech-pill"),
                        ],
                        className="header-meta",
                    ),
                ],
                className="app-header",
            ),
            html.Div(
                [
                    html.Aside(
                        [
                            html.Label("Cliente"),
                            dcc.Dropdown(id="client", options=client_options, value=[], multi=True, clearable=True, placeholder="Todos los clientes"),
                            html.Div("Selecciona uno o varios clientes. El visualizador detalla compras recientes y separa solidos, surtidos, recetas y bulk.", className="filter-help"),
                            html.Div(
                                [
                                    html.Label("Producto cliente"),
                                    dcc.Dropdown(
                                        id="client-product-filter",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        clearable=True,
                                        placeholder="Todos los productos del cliente",
                                    ),
                                    html.Div(
                                        [
                                            html.Button("Todo", id="product-select-all", n_clicks=0, type="button"),
                                            html.Button("Limpiar", id="product-clear", n_clicks=0, type="button"),
                                        ],
                                        className="filter-actions",
                                    ),
                                ],
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Color interno"),
                                    dcc.Dropdown(
                                        id="client-color-filter",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        clearable=True,
                                        placeholder="Todos los colores internos",
                                    ),
                                    html.Div(
                                        [
                                            html.Button("Todo", id="color-select-all", n_clicks=0, type="button"),
                                            html.Button("Limpiar", id="color-clear", n_clicks=0, type="button"),
                                        ],
                                        className="filter-actions",
                                    ),
                                ],
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("SKU operativo cliente"),
                                    dcc.Dropdown(
                                        id="client-program-filter",
                                        options=[],
                                        value=None,
                                        clearable=True,
                                        placeholder="Todos los SKUs",
                                    ),
                                ],
                                id="client-program-filter-wrap",
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("SKU composicion 360"),
                                    dcc.Dropdown(
                                        id="selected-sku-operativo",
                                        options=[],
                                        value=None,
                                        clearable=True,
                                        placeholder="Todos los SKUs / selecciona para composicion",
                                    ),
                                ],
                                id="selected-sku-operativo-wrap",
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("SKU operativo"),
                                    dcc.Dropdown(
                                        id="visual-sku-filter",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        clearable=True,
                                        searchable=True,
                                        placeholder="Todos los SKUs operativos",
                                        className="sku-multiselect",
                                    ),
                                    html.Div(
                                        [
                                            html.Button("Todo", id="sku-select-all", n_clicks=0, type="button"),
                                            html.Button("Limpiar", id="sku-clear", n_clicks=0, type="button"),
                                        ],
                                        className="filter-actions",
                                    ),
                                ],
                                id="visual-sku-filter-wrap",
                                className="demand-control sku-picker-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Vista de color"),
                                    dcc.Dropdown(
                                        id="client-color-view",
                                        options=[
                                            {"label": "Semana seleccionada", "value": "selected_week"},
                                            {"label": "Promedio del periodo", "value": "period_average"},
                                            {"label": "Acumulado del periodo", "value": "period_total"},
                                        ],
                                        value="period_total",
                                        clearable=False,
                                    ),
                                ],
                                className="demand-control",
                            ),
                            html.Div(
                                [
                                    html.Label("Detalle interno"),
                                    dcc.Dropdown(
                                        id="client-internal-detail",
                                        options=[
                                            {"label": "Color interno", "value": "color"},
                                            {"label": "Color + variedad", "value": "color_variedad"},
                                            {"label": "Variedades internas", "value": "variedad"},
                                        ],
                                        value="color",
                                        clearable=False,
                                    ),
                                ],
                                className="demand-control",
                            ),
                        ],
                        id="global-client-filters",
                        className="filters",
                    ),
                    html.Main(
                        [
                            dcc.Tabs(
                                id="tabs",
                                value="visualizador_clientes_general",
                                children=[
                                    dcc.Tab(label="Visualizador clientes detallado", value="visualizador_clientes_general"),
                                    dcc.Tab(label="Ventas generales", value="ventas_generales"),
                                    dcc.Tab(label="Fletes", value="fletes"),
                                    dcc.Tab(label="Comprador", value="comprador"),
                                    dcc.Tab(label="Demanda e inventario", value="demanda"),
                                    dcc.Tab(label="Forecast solidos historico", value="forecast_solidos"),
                                    dcc.Tab(label="Administrador", value="administrador"),
                                ],
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Semana de analisis"),
                                            dcc.Dropdown(
                                                id="analysis-week",
                                                options=[{"label": f"Semana {week}", "value": week} for week in range(1, 54)],
                                                value=current_week,
                                                clearable=False,
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Semanas hacia atras"),
                                            dcc.Dropdown(
                                                id="client-lookback-weeks",
                                                options=[
                                                    {"label": "4 semanas", "value": 4},
                                                    {"label": "8 semanas", "value": 8},
                                                    {"label": "12 semanas", "value": 12},
                                                    {"label": "26 semanas", "value": 26},
                                                    {"label": "52 semanas", "value": 52},
                                                ],
                                                value=12,
                                                clearable=False,
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Anios ventas"),
                                            dcc.Dropdown(
                                                id="visual-sales-years",
                                                options=sales_year_options,
                                                value=sales_default_years,
                                                multi=True,
                                                clearable=True,
                                                placeholder="Selecciona anios",
                                            ),
                                        ],
                                        className="demand-control visual-only-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Rango semanas"),
                                            dcc.RangeSlider(
                                                id="visual-week-range",
                                                min=1,
                                                max=53,
                                                step=1,
                                                value=[1, 53],
                                                marks=sales_week_marks,
                                                allowCross=False,
                                                tooltip={"placement": "bottom", "always_visible": False},
                                            ),
                                        ],
                                        className="demand-control visual-only-control slider-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Tipo operativo"),
                                            dcc.Dropdown(
                                                id="visual-tipo-filter",
                                                options=[],
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los tipos",
                                            ),
                                        ],
                                        className="demand-control visual-only-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Comparacion"),
                                            dcc.Checklist(
                                                id="client-compare-last-year",
                                                options=[{"label": "Mostrar ano anterior", "value": "last_year"}],
                                                value=[],
                                                inputStyle={"marginRight": "8px"},
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Metrica grafica"),
                                            dcc.Dropdown(
                                                id="client-volume-metric",
                                                options=[
                                                    {"label": "Tallos confirmados", "value": "tallos_confirmados"},
                                                    {"label": "Tallos pedidos", "value": "tallos_pedidos"},
                                                    {"label": "Ventas USD", "value": "ventas_usd"},
                                                    {"label": "Cajas", "value": "cajas_ids"},
                                                ],
                                                value="tallos_confirmados",
                                                clearable=False,
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Filas"),
                                            dcc.Dropdown(
                                                id="top-n",
                                                options=[{"label": str(n), "value": n} for n in [10, 15, 20, 30, 40]],
                                                value=15,
                                                clearable=False,
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                ],
                                id="client-options",
                                className="demand-options",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Anios"),
                                            dcc.Dropdown(
                                                id="general-sales-years",
                                                options=sales_year_options,
                                                value=sales_default_years,
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los anios",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("AÃ±o base"),
                                            dcc.Dropdown(
                                                id="general-sales-base-year",
                                                options=sales_base_year_options,
                                                value=sales_default_base_year,
                                                clearable=False,
                                                placeholder="Base",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("AÃ±o comparativo"),
                                            dcc.Dropdown(
                                                id="general-sales-compare-year",
                                                options=sales_base_year_options,
                                                value=sales_default_compare_year,
                                                clearable=False,
                                                placeholder="Comparativo",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Rango semanas"),
                                            dcc.RangeSlider(
                                                id="general-sales-week-range",
                                                min=1,
                                                max=53,
                                                step=1,
                                                value=[1, 53],
                                                marks=sales_week_marks,
                                                allowCross=False,
                                                tooltip={"placement": "bottom", "always_visible": False},
                                            ),
                                        ],
                                        className="demand-control slider-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Compania"),
                                            dcc.Dropdown(
                                                id="general-sales-companies",
                                                options=general_sales_company_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todas las companias",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Cliente"),
                                            dcc.Dropdown(
                                                id="general-sales-clients",
                                                options=general_sales_client_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los clientes",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Pais"),
                                            dcc.Dropdown(
                                                id="general-sales-countries",
                                                options=general_sales_country_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los paises",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Producto"),
                                            dcc.Dropdown(
                                                id="general-sales-products",
                                                options=general_sales_product_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los productos",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Color"),
                                            dcc.Dropdown(
                                                id="general-sales-colors",
                                                options=general_sales_color_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los colores",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Tipo operativo"),
                                            dcc.Dropdown(
                                                id="general-sales-types",
                                                options=general_sales_type_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los tipos",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                ],
                                id="general-sales-options",
                                className="demand-options",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Div("Controles de forecast", className="forecast-controls-title"),
                                                    html.Div("Selecciona el alcance, proyecta, valida y simula.", className="forecast-controls-subtitle"),
                                                ]
                                            ),
                                            html.Button("Limpiar filtros", id="forecast-clear-filters", n_clicks=0, type="button"),
                                        ],
                                        className="forecast-controls-header",
                                    ),
                                    html.Div(
                                        [
                                            html.Div("1. Alcance comercial", className="forecast-filter-title"),
                                            html.Div("Modifica la proyeccion, la validacion y los resumenes.", className="forecast-filter-effect"),
                                            html.Div(
                                                [
                                                    html.Div([html.Label("Mercado"), dcc.Dropdown(id="forecast-markets", options=forecast_market_options, value=[], multi=True, placeholder="Todos los mercados")], className="demand-control"),
                                                    html.Div([html.Label("Pais"), dcc.Dropdown(id="forecast-countries", options=forecast_country_options, value=[], multi=True, placeholder="Todos los paises")], className="demand-control"),
                                                    html.Div([html.Label("Cliente"), dcc.Dropdown(id="forecast-clients", options=forecast_client_options, value=[], multi=True, placeholder="Todos los clientes")], className="demand-control"),
                                                    html.Div([html.Label("Producto"), dcc.Dropdown(id="forecast-products", options=forecast_product_options, value=[], multi=True, placeholder="Todos los productos")], className="demand-control"),
                                                    html.Div([html.Label("Color"), dcc.Dropdown(id="forecast-colors", options=forecast_color_options, value=[], multi=True, placeholder="Todos los colores")], className="demand-control"),
                                                ],
                                                className="forecast-filter-grid forecast-filter-grid-5",
                                            ),
                                        ],
                                        className="forecast-filter-group scope",
                                    ),
                                    html.Div(
                                        [
                                            html.Div("2. Proyeccion futura", className="forecast-filter-title"),
                                            html.Div("Define cuantas semanas futuras se muestran en la linea, tarjetas y tablas proyectadas.", className="forecast-filter-effect"),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Label("Horizonte futuro"),
                                                            dcc.RadioItems(
                                                                id="forecast-horizon-weeks",
                                                                options=[{"label": "2 semanas", "value": 2}, {"label": "5 semanas", "value": 5}, {"label": "8 semanas", "value": 8}],
                                                                value=5,
                                                                inline=True,
                                                                inputStyle={"marginRight": "6px", "marginLeft": "12px"},
                                                                labelStyle={"display": "inline-flex", "alignItems": "center"},
                                                            ),
                                                        ],
                                                        className="demand-control",
                                                    ),
                                                ],
                                                className="forecast-filter-grid compact",
                                            ),
                                        ],
                                        className="forecast-filter-group projection",
                                    ),
                                    html.Div(
                                        [
                                            html.Div("3. Historia comparativa", className="forecast-filter-title"),
                                            html.Div("Cambia las lineas reales contra las que comparas el forecast; no cambia el modelo generado.", className="forecast-filter-effect"),
                                            html.Div(
                                                [
                                                    html.Div([html.Label("Periodo historico"), dcc.DatePickerRange(id="forecast-date-range", min_date_allowed=forecast_date_min, max_date_allowed=forecast_date_max, start_date=forecast_date_min, end_date=forecast_date_max, display_format="YYYY-MM-DD")], className="demand-control"),
                                                    html.Div([html.Label("Anios historicos"), dcc.Dropdown(id="forecast-years", options=forecast_year_options, value=forecast_default_years, multi=True, placeholder="Todos los anios")], className="demand-control"),
                                                    html.Div([html.Label("Semanas ISO historicas"), dcc.RangeSlider(id="forecast-week-range", min=1, max=53, step=1, value=[1, 53], marks={1: "1", 13: "13", 26: "26", 39: "39", 53: "53"}, allowCross=False, tooltip={"placement": "bottom", "always_visible": False})], className="demand-control slider-control"),
                                                ],
                                                className="forecast-filter-grid",
                                            ),
                                        ],
                                        className="forecast-filter-group history",
                                    ),
                                    html.Div(
                                        [
                                            html.Div("4. Validacion historica", className="forecast-filter-title"),
                                            html.Div("Mide WAPE y bias en una ventana pasada seleccionada y permite revisar el backtest final.", className="forecast-filter-effect"),
                                            html.Div(
                                                [
                                                    html.Div([html.Label("Ano evaluado"), dcc.Dropdown(id="forecast-validation-year", options=validation_year_options, value=validation_default_year, clearable=False, placeholder="Sin periodo comparable")], className="demand-control"),
                                                    html.Div([html.Label("Duracion evaluada"), dcc.RadioItems(id="forecast-validation-weeks", options=[{"label": "2 semanas", "value": 2}, {"label": "5 semanas", "value": 5}, {"label": "8 semanas", "value": 8}], value=validation_default_weeks, inline=True, inputStyle={"marginRight": "6px", "marginLeft": "12px"}, labelStyle={"display": "inline-flex", "alignItems": "center"})], className="demand-control"),
                                                    html.Div([html.Label("Inicio de ventana"), dcc.Dropdown(id="forecast-validation-start-week", options=validation_start_week_options, value=validation_default_start_week, clearable=False, placeholder="Sin ventana valida")], className="demand-control"),
                                                    html.Div([html.Label("Modelo en backtest final"), dcc.Dropdown(id="forecast-model", options=forecast_model_options, value=forecast_default_model, clearable=False)], className="demand-control"),
                                                ],
                                                className="forecast-filter-grid",
                                            ),
                                        ],
                                        className="forecast-filter-group validation",
                                    ),
                                    html.Div(
                                        [
                                            html.Div("5. Escenario comercial", className="forecast-filter-title"),
                                            html.Div("Simula una hipotesis sobre el forecast visible; no reentrena el modelo.", className="forecast-filter-effect"),
                                            html.Div(
                                                [
                                                    html.Div([html.Label("Cliente escenario"), dcc.Dropdown(id="forecast-scenario-client", options=forecast_client_options, value=None, clearable=True, placeholder="Selecciona cliente")], className="demand-control"),
                                                    html.Div([html.Label("Producto escenario"), dcc.Dropdown(id="forecast-scenario-product", options=forecast_product_options, value=None, clearable=True, placeholder="Cualquier producto")], className="demand-control"),
                                                    html.Div([html.Label("Color escenario"), dcc.Dropdown(id="forecast-scenario-color", options=forecast_color_options, value=None, clearable=True, placeholder="Cualquier color")], className="demand-control"),
                                                    html.Div([html.Label("Probabilidad de compra"), dcc.Slider(id="forecast-scenario-probability", min=50, max=150, step=5, value=100, marks={50: "50%", 100: "100%", 150: "150%"}, tooltip={"placement": "bottom", "always_visible": False})], className="demand-control slider-control"),
                                                    html.Div([html.Label("Volumen si compra"), dcc.Slider(id="forecast-scenario-volume", min=50, max=150, step=5, value=100, marks={50: "50%", 100: "100%", 150: "150%"}, tooltip={"placement": "bottom", "always_visible": False})], className="demand-control slider-control"),
                                                ],
                                                className="forecast-filter-grid",
                                            ),
                                        ],
                                        className="forecast-filter-group scenario",
                                    ),
                                ],
                                id="forecast-options",
                                className="forecast-options-panel",
                            ),
                            html.Div(id="tab-content", className="tab-content"),
                            dcc.Download(id="general-sales-report-download"),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Lectura demanda"),
                                            dcc.Dropdown(
                                                id="analysis-scope",
                                                options=[
                                                    {"label": "Solidos: color/caja/SKU", "value": "solidos"},
                                                    {"label": "Estructuras mixtas: receta/composicion", "value": "estructuras"},
                                                    {"label": "Bulk: producto/color base", "value": "bulk"},
                                                    {"label": "Todos los formatos", "value": "todos"},
                                                ],
                                                value="solidos",
                                                clearable=False,
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Producto"),
                                            dcc.Dropdown(
                                                id="solid-product",
                                                options=product_options,
                                                value=None,
                                                clearable=True,
                                                placeholder="Todos los productos",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Color"),
                                            dcc.Dropdown(
                                                id="color-filter",
                                                options=color_options,
                                                value=None,
                                                clearable=True,
                                                placeholder="Todos los colores",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Comparacion ano anterior"),
                                            dcc.RadioItems(
                                                id="compare-mode",
                                                options=[
                                                    {"label": "Sin comparacion", "value": "none"},
                                                    {"label": "Mismas fechas", "value": "same_dates"},
                                                    {"label": "Mismas semanas", "value": "same_weeks"},
                                                ],
                                                value="none",
                                                inputStyle={"marginRight": "8px"},
                                                labelStyle={"display": "block"},
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    dcc.Checklist(
                                        id="compare-last-year",
                                        options=[{"label": "Comparar demanda contra el mismo periodo del ano anterior", "value": "last_year"}],
                                        value=[],
                                        inputStyle={"marginRight": "8px"},
                                        labelStyle={"display": "block"},
                                        style={"display": "none"},
                                    )
                                ],
                                id="demand-options",
                                className="demand-options",
                            ),
                        ],
                        className="content",
                    ),
                ],
                id="app-shell",
                className="app-shell",
            ),
        ],
        className="page",
    )

    @app.callback(
        Output("tab-content", "children"),
        Input("tabs", "value"),
        Input("client", "value"),
        Input("top-n", "value"),
        Input("analysis-week", "value"),
        Input("client-lookback-weeks", "value"),
        Input("client-compare-last-year", "value"),
        Input("client-volume-metric", "value"),
        Input("client-product-filter", "value"),
        Input("client-color-filter", "value"),
        Input("client-program-filter", "value"),
        Input("visual-sales-years", "value"),
        Input("visual-week-range", "value"),
        Input("visual-tipo-filter", "value"),
        Input("selected-sku-operativo", "value"),
        Input("visual-sku-filter", "value"),
        Input("client-color-view", "value"),
        Input("client-internal-detail", "value"),
        Input("general-sales-years", "value"),
        Input("general-sales-base-year", "value"),
        Input("general-sales-compare-year", "value"),
        Input("general-sales-week-range", "value"),
        Input("general-sales-companies", "value"),
        Input("general-sales-clients", "value"),
        Input("general-sales-countries", "value"),
        Input("general-sales-products", "value"),
        Input("general-sales-colors", "value"),
        Input("general-sales-types", "value"),
        Input("compare-mode", "value"),
        Input("solid-product", "value"),
        Input("analysis-scope", "value"),
        Input("color-filter", "value"),
        Input("forecast-date-range", "start_date"),
        Input("forecast-date-range", "end_date"),
        Input("forecast-years", "value"),
        Input("forecast-week-range", "value"),
        Input("forecast-horizon-weeks", "value"),
        Input("forecast-validation-year", "value"),
        Input("forecast-validation-weeks", "value"),
        Input("forecast-validation-start-week", "value"),
        Input("forecast-markets", "value"),
        Input("forecast-countries", "value"),
        Input("forecast-clients", "value"),
        Input("forecast-products", "value"),
        Input("forecast-colors", "value"),
        Input("forecast-model", "value"),
        Input("forecast-scenario-client", "value"),
        Input("forecast-scenario-product", "value"),
        Input("forecast-scenario-color", "value"),
        Input("forecast-scenario-probability", "value"),
        Input("forecast-scenario-volume", "value"),
    )
    def render_tab(
        tab: str,
        client: list[str] | str | None,
        top_n: int,
        analysis_week: int,
        client_lookback_weeks: int,
        client_compare_last_year: list[str] | None,
        client_volume_metric: str,
        client_product_filter: list[str] | str | None,
        client_color_filter: list[str] | str | None,
        client_program_filter: str | None,
        visual_sales_years: list[int] | None,
        visual_week_range: list[int] | None,
        visual_tipo_filter: list[str] | None,
        selected_sku_operativo: str | None,
        visual_sku_filter: list[str] | None,
        client_color_view: str | None,
        client_internal_detail: str | None,
        general_sales_years: list[int] | None,
        general_sales_base_year: int | None,
        general_sales_compare_year: int | None,
        general_sales_week_range: list[int] | None,
        general_sales_companies: list[str] | None,
        general_sales_clients: list[str] | None,
        general_sales_countries: list[str] | None,
        general_sales_products: list[str] | None,
        general_sales_colors: list[str] | None,
        general_sales_types: list[str] | None,
        compare_mode: str | None,
        solid_product: str | None,
        analysis_scope: str | None,
        color_filter: str | None,
        forecast_start_date: str | None,
        forecast_end_date: str | None,
        forecast_years: list[int] | None,
        forecast_week_range: list[int] | None,
        forecast_horizon_weeks: int | None,
        forecast_validation_year: int | None,
        forecast_validation_weeks: int | None,
        forecast_validation_start_week: int | None,
        forecast_markets: list[str] | None,
        forecast_countries: list[str] | None,
        forecast_clients: list[str] | None,
        forecast_products: list[str] | None,
        forecast_colors: list[str] | None,
        forecast_model: str | None,
        forecast_scenario_client: str | None,
        forecast_scenario_product: str | None,
        forecast_scenario_color: str | None,
        forecast_scenario_probability: int | None,
        forecast_scenario_volume: int | None,
    ):
        filtered = data["perfil"]
        client_values = selected_values(client)
        primary_client = client_values[0] if len(client_values) == 1 else None
        selected = select_client(filtered, data["perfil"], primary_client)
        selected_code = None if selected is None else selected["cod_cliente"]
        visual_selected_code = client_values if client_values else None
        week_offset = 0
        visible_weeks = 4

        if tab == "cliente":
            return render_cliente_tab(
                data,
                filtered,
                selected,
                selected_code,
                top_n,
                client_lookback_weeks,
                analysis_week,
                "last_year" in (client_compare_last_year or []),
                selected_sku_operativo,
                client_volume_metric,
                client_product_filter,
                client_color_filter,
                client_program_filter,
                visual_sales_years,
                visual_week_range,
                visual_tipo_filter,
            )
        if tab == "visualizador_clientes_general":
            return render_visualizador_clientes_general(
                data,
                filtered,
                selected,
                visual_selected_code,
                top_n,
                client_lookback_weeks,
                analysis_week,
                "last_year" in (client_compare_last_year or []),
                client_volume_metric,
                client_product_filter,
                client_color_filter,
                client_program_filter,
                visual_sales_years,
                visual_week_range,
                visual_tipo_filter,
                visual_sku_filter,
                client_color_view or "period_total",
                client_internal_detail or "color",
            )
        if tab == "ventas_generales":
            return render_ventas_generales_tab_v2(
                data,
                general_sales_base_year,
                general_sales_compare_year,
                general_sales_years,
                general_sales_week_range,
                general_sales_companies,
                general_sales_clients,
                general_sales_countries,
                general_sales_products,
                general_sales_colors,
            )
        if tab == "fletes":
            return render_fletes_tab(
                general_sales_years,
                general_sales_week_range,
                general_sales_companies,
                general_sales_clients,
                general_sales_countries,
                general_sales_products,
                general_sales_colors,
                general_sales_types,
            )
        if tab == "comprador":
            return render_reserved_module("Comprador", "Este modulo queda reservado para la fase de proyeccion y cruce con inventario.")
        if tab == "demanda":
            return render_reserved_module("Demanda e inventario", "Este modulo queda reservado hasta incorporar la proyeccion de inventario.")
        if tab == "forecast_solidos":
            return render_forecast_solidos_tab(
                data,
                forecast_start_date,
                forecast_end_date,
                forecast_years,
                forecast_week_range,
                forecast_horizon_weeks,
                forecast_validation_year,
                forecast_validation_weeks,
                forecast_validation_start_week,
                forecast_markets,
                forecast_countries,
                forecast_clients,
                forecast_products,
                forecast_colors,
                forecast_model,
                forecast_scenario_client,
                forecast_scenario_product,
                forecast_scenario_color,
                forecast_scenario_probability,
                forecast_scenario_volume,
                top_n,
            )
        if tab == "administrador":
            return render_admin_tab()
        return render_visualizador_clientes_general(
            data, filtered, selected, visual_selected_code, top_n, client_lookback_weeks,
            analysis_week, "last_year" in (client_compare_last_year or []),
            client_volume_metric, client_product_filter, client_color_filter,
            client_program_filter, visual_sales_years, visual_week_range,
            visual_tipo_filter, visual_sku_filter, client_color_view or "period_total",
            client_internal_detail or "color",
        )

    @app.callback(
        Output("demand-options", "style"),
        Output("client-options", "style"),
        Output("client-program-filter-wrap", "style"),
        Output("selected-sku-operativo-wrap", "style"),
        Output("visual-sku-filter-wrap", "style"),
        Output("general-sales-options", "style"),
        Output("forecast-options", "style"),
        Output("global-client-filters", "style"),
        Output("app-shell", "style"),
        Input("tabs", "value"),
    )
    def toggle_context_options(tab: str):
        visible = {"display": "block"}
        hidden = {"display": "none"}
        if tab == "visualizador_clientes_general":
            return {"display": "none"}, {"display": "grid"}, hidden, hidden, visible, hidden, hidden, {}, {}
        if tab == "ventas_generales":
            return hidden, hidden, hidden, hidden, hidden, {"display": "grid"}, hidden, hidden, {"gridTemplateColumns": "1fr"}
        if tab == "fletes":
            return hidden, hidden, hidden, hidden, hidden, {"display": "grid"}, hidden, hidden, {"gridTemplateColumns": "1fr"}
        if tab == "forecast_solidos":
            return hidden, hidden, hidden, hidden, hidden, hidden, {"display": "block"}, {"display": "none"}, {"gridTemplateColumns": "1fr"}
        if tab == "administrador":
            return hidden, hidden, hidden, hidden, hidden, hidden, hidden, {"display": "none"}, {"gridTemplateColumns": "1fr"}
        return hidden, hidden, hidden, hidden, hidden, hidden, hidden, {"display": "none"}, {"gridTemplateColumns": "1fr"}

    @app.callback(
        Output("general-sales-companies", "options"),
        Output("general-sales-companies", "value"),
        Output("general-sales-clients", "options"),
        Output("general-sales-clients", "value"),
        Output("general-sales-countries", "options"),
        Output("general-sales-countries", "value"),
        Output("general-sales-products", "options"),
        Output("general-sales-products", "value"),
        Output("general-sales-colors", "options"),
        Output("general-sales-colors", "value"),
        Output("general-sales-types", "options"),
        Output("general-sales-types", "value"),
        Input("tabs", "value"),
        Input("general-sales-years", "value"),
        Input("general-sales-week-range", "value"),
        Input("general-sales-companies", "value"),
        Input("general-sales-clients", "value"),
        Input("general-sales-countries", "value"),
        Input("general-sales-products", "value"),
        Input("general-sales-colors", "value"),
        Input("general-sales-types", "value"),
    )
    def cascade_general_sales_filters(tab, years, week_range, companies, clients, countries, products, colors, order_types):
        sales = data.get("ventas_semana", pd.DataFrame())
        if sales.empty:
            return [], [], [], [], [], [], [], [], [], [], [], []
        latest_year = latest_selected_year(years, sales)
        scope = filter_general_sales_frame(
            sales,
            [latest_year] if latest_year is not None else years,
            week_range,
            None,
            None,
            None,
            None,
            None,
        )
        selected_companies = selected_values(companies)
        selected_clients = selected_values(clients)
        selected_countries = selected_values(countries)
        selected_products = selected_values(products)
        selected_colors = selected_values(colors)
        selected_types = selected_values(order_types)

        company_options, company_values = tallos_options_from_frame(scope, "NomCompania")
        selected_companies = [value for value in selected_companies if value in set(company_values)]
        if selected_companies and "NomCompania" in scope.columns:
            scope = scope[scope["NomCompania"].astype(str).isin(set(selected_companies))].copy()

        client_scope = scope.copy()
        if {"cod_cliente", "cliente"}.issubset(client_scope.columns):
            client_scope["cliente_label"] = client_scope["cliente"].astype(str) + " | " + client_scope["cod_cliente"].astype(str)
            client_options, client_values = tallos_options_from_frame(client_scope, "cod_cliente", "cliente_label")
        else:
            client_options, client_values = [], []
        selected_clients = [value for value in selected_clients if value in set(client_values)]
        if selected_clients and "cod_cliente" in scope.columns:
            scope = scope[scope["cod_cliente"].astype(str).isin(set(selected_clients))].copy()

        country_options, country_values = tallos_options_from_frame(scope, "pais")
        selected_countries = [value for value in selected_countries if value in set(country_values)]
        if selected_countries and "pais" in scope.columns:
            scope = scope[scope["pais"].astype(str).isin(set(selected_countries))].copy()

        product_options, product_values = tallos_options_from_frame(scope, "producto")
        selected_products = [value for value in selected_products if value in set(product_values)]
        if selected_products and "producto" in scope.columns:
            scope = scope[scope["producto"].astype(str).isin(set(selected_products))].copy()

        color_options, color_values = tallos_options_from_frame(scope, "color")
        selected_colors = [value for value in selected_colors if value in set(color_values)]
        if selected_colors and "color" in scope.columns:
            scope = scope[scope["color"].astype(str).isin(set(selected_colors))].copy()

        if tab == "fletes":
            type_options = get_fletes_type_options(
                years,
                week_range,
                selected_companies,
                selected_clients,
                selected_countries,
                selected_products,
                selected_colors,
            )
            type_values = [str(option["value"]) for option in type_options]
        else:
            type_options, type_values = tallos_options_from_frame(scope, "tipo_pedido_operativo")
        selected_types = [value for value in selected_types if value in set(type_values)]

        return (
            company_options,
            selected_companies,
            client_options,
            selected_clients,
            country_options,
            selected_countries,
            product_options,
            selected_products,
            color_options,
            selected_colors,
            type_options,
            selected_types,
        )

    @app.callback(
        Output("forecast-markets", "options"),
        Output("forecast-markets", "value"),
        Output("forecast-countries", "options"),
        Output("forecast-countries", "value"),
        Output("forecast-clients", "options"),
        Output("forecast-clients", "value"),
        Output("forecast-products", "options"),
        Output("forecast-products", "value"),
        Output("forecast-colors", "options"),
        Output("forecast-colors", "value"),
        Input("tabs", "value"),
        Input("forecast-markets", "value"),
        Input("forecast-countries", "value"),
        Input("forecast-clients", "value"),
        Input("forecast-products", "value"),
        Input("forecast-colors", "value"),
        Input("forecast-clear-filters", "n_clicks"),
    )
    def cascade_forecast_filters(tab, markets, countries, clients, products, colors, clear_clicks):
        base = data.get("solid_forecast_weekly", pd.DataFrame())
        if base.empty:
            return [], [], [], [], [], [], [], [], [], []
        reset = ctx.triggered_id == "forecast-clear-filters"
        selected_market = [] if reset else selected_values(markets)
        selected_country = [] if reset else selected_values(countries)
        selected_client = [] if reset else selected_values(clients)
        selected_product = [] if reset else selected_values(products)
        selected_color = [] if reset else selected_values(colors)

        market_values = sorted(base["mercado_cluster"].dropna().astype(str).unique())
        selected_market = [value for value in selected_market if value in set(market_values)]
        scope = base[base["mercado_cluster"].isin(selected_market)].copy() if selected_market else base.copy()

        country_values = sorted(scope["pais"].dropna().astype(str).unique())
        selected_country = [value for value in selected_country if value in set(country_values)]
        if selected_country:
            scope = scope[scope["pais"].isin(selected_country)].copy()

        client_rows = scope[["cod_cliente", "cliente"]].drop_duplicates().sort_values(["cliente", "cod_cliente"])
        client_values = set(client_rows["cod_cliente"].astype(str))
        selected_client = [value for value in selected_client if value in client_values]
        if selected_client:
            scope = scope[scope["cod_cliente"].astype(str).isin(selected_client)].copy()

        product_values = sorted(scope["producto"].dropna().astype(str).unique())
        selected_product = [value for value in selected_product if value in set(product_values)]
        if selected_product:
            scope = scope[scope["producto"].isin(selected_product)].copy()

        color_values = sorted(scope["color"].dropna().astype(str).unique())
        selected_color = [value for value in selected_color if value in set(color_values)]
        return (
            [{"label": value, "value": value} for value in market_values],
            selected_market,
            [{"label": value, "value": value} for value in country_values],
            selected_country,
            [{"label": f"{row.cliente} | {row.cod_cliente}", "value": str(row.cod_cliente)} for row in client_rows.itertuples(index=False)],
            selected_client,
            [{"label": value, "value": value} for value in product_values],
            selected_product,
            [{"label": value, "value": value} for value in color_values],
            selected_color,
        )

    @app.callback(
        Output("forecast-years", "value"),
        Output("forecast-week-range", "value"),
        Output("forecast-date-range", "start_date"),
        Output("forecast-date-range", "end_date"),
        Output("forecast-horizon-weeks", "value"),
        Output("forecast-validation-year", "value"),
        Output("forecast-validation-weeks", "value"),
        Output("forecast-scenario-client", "value"),
        Output("forecast-scenario-product", "value"),
        Output("forecast-scenario-color", "value"),
        Output("forecast-scenario-probability", "value"),
        Output("forecast-scenario-volume", "value"),
        Input("forecast-clear-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_forecast_secondary_filters(_clicks):
        return (
            forecast_default_years, [1, 53], forecast_date_min, forecast_date_max,
            5, validation_default_year, validation_default_weeks,
            None, None, None, 100, 100,
        )

    @app.callback(
        Output("forecast-validation-start-week", "options"),
        Output("forecast-validation-start-week", "value"),
        Input("forecast-validation-year", "value"),
        Input("forecast-validation-weeks", "value"),
        State("forecast-validation-start-week", "value"),
    )
    def update_forecast_validation_windows(year: int | None, weeks: int | None, current_week: int | None):
        weeks = int(weeks) if weeks in {2, 5, 8} else validation_default_weeks
        starts = valid_validation_window_starts(validation_source, year, weeks)
        options = [
            {"label": f"Semanas {week:02d} - {week + weeks - 1:02d}", "value": week}
            for week in starts
        ]
        value = int(current_week) if current_week in starts else (starts[0] if starts else None)
        return options, value

    @app.callback(
        Output("visual-tipo-filter", "options"),
        Output("visual-tipo-filter", "value"),
        Input("tabs", "value"),
        Input("visual-tipo-filter", "value"),
    )
    def update_visual_tipo_options(tab: str, current_value: list[str] | None):
        sales = data.get("ventas_semana", pd.DataFrame())
        if tab != "visualizador_clientes_general" or sales.empty or "tipo_pedido_operativo" not in sales.columns:
            return [], []
        tipos = sorted(sales["tipo_pedido_operativo"].dropna().astype(str).unique())
        options = [{"label": tipo, "value": tipo} for tipo in tipos]
        valid = set(tipos)
        value = [tipo for tipo in (current_value or []) if tipo in valid]
        return options, value

    @app.callback(
        Output("visual-sku-filter", "options"),
        Output("visual-sku-filter", "value"),
        Input("tabs", "value"),
        Input("client", "value"),
        Input("visual-sales-years", "value"),
        Input("visual-week-range", "value"),
        Input("visual-tipo-filter", "value"),
        Input("client-product-filter", "value"),
        Input("client-color-filter", "value"),
        Input("sku-select-all", "n_clicks"),
        Input("sku-clear", "n_clicks"),
        State("visual-sku-filter", "value"),
    )
    def update_visual_sku_options(
        tab: str,
        client: list[str] | str | None,
        visual_sales_years: list[int] | None,
        visual_week_range: list[int] | None,
        visual_tipo_filter: list[str] | None,
        product: list[str] | str | None,
        color: list[str] | str | None,
        sku_select_all_clicks: int | None,
        sku_clear_clicks: int | None,
        current_value: list[str] | None,
    ):
        if tab != "visualizador_clientes_general":
            return [], []
        base = filter_visual_operational_base(
            data,
            data["perfil"],
            selected_values(client) or None,
            visual_sales_years,
            visual_week_range,
            visual_tipo_filter,
            product,
            color,
            None,
        )
        if base.empty or "sku_operativo" not in base.columns:
            return [], []
        ranking = visual_sku_ranking(base, 300)
        if ranking.empty:
            return [], []
        ranking = ranking[~ranking["sku_operativo"].astype(str).str.lower().isin(["", "nan", "none", "sin_info"])].copy()
        ranking = ranking.sort_values(["ventas_usd", "tallos_confirmados"], ascending=False).head(300)
        options = []
        seen = set()
        for i, row in enumerate(ranking.to_dict("records"), start=1):
            sku = str(row.get("sku_operativo", ""))
            if not sku or sku in seen:
                continue
            seen.add(sku)
            label = row.get("sku_operativo_general") or operational_sku_filter_label(pd.Series(row))
            ventas = moneyless_number(row.get("ventas_usd", 0), 2)
            tallos = moneyless_number(row.get("tallos_confirmados", 0), 0)
            options.append({"label": f"{i}. {label} | USD {ventas} | {tallos} tallos", "value": sku})
        option_values = [str(opt["value"]) for opt in options]
        value = synced_multi_value(current_value, option_values, "sku-select-all", "sku-clear")
        return options, value

    @app.callback(
        Output("client-product-filter", "options"),
        Output("client-product-filter", "value"),
        Input("client", "value"),
        Input("visual-sales-years", "value"),
        Input("visual-week-range", "value"),
        Input("visual-tipo-filter", "value"),
        Input("product-select-all", "n_clicks"),
        Input("product-clear", "n_clicks"),
        State("client-product-filter", "value"),
    )
    def update_client_product_options(
        client: list[str] | str | None,
        visual_sales_years: list[int] | None,
        visual_week_range: list[int] | None,
        visual_tipo_filter: list[str] | None,
        product_select_all_clicks: int | None,
        product_clear_clicks: int | None,
        current_value: list[str] | str | None,
    ):
        sales = data.get("ventas_semana", pd.DataFrame())
        selected_clients = selected_values(client)
        if not selected_clients and not sales.empty and "producto" in sales.columns:
            work = filter_sales_visual(sales, None, [latest_selected_year(visual_sales_years, sales)] if latest_selected_year(visual_sales_years, sales) else None, visual_week_range, visual_tipo_filter, None, None)
            options, products = tallos_options_from_frame(work, "producto")
            value = synced_multi_value(current_value, products, "product-select-all", "product-clear")
            return options, value
        work = filter_visual_operational_base(
            data,
            data["perfil"],
            selected_clients,
            [latest_selected_year(visual_sales_years, sales)] if latest_selected_year(visual_sales_years, sales) else visual_sales_years,
            visual_week_range,
            visual_tipo_filter,
            None,
            None,
            None,
        )
        if work.empty or "producto" not in work.columns:
            return [], []
        options, products = tallos_options_from_frame(work, "producto")
        value = synced_multi_value(current_value, products, "product-select-all", "product-clear")
        return options, value

    @app.callback(
        Output("client-color-filter", "options"),
        Output("client-color-filter", "value"),
        Input("client", "value"),
        Input("client-product-filter", "value"),
        Input("visual-sales-years", "value"),
        Input("visual-week-range", "value"),
        Input("visual-tipo-filter", "value"),
        Input("color-select-all", "n_clicks"),
        Input("color-clear", "n_clicks"),
        State("client-color-filter", "value"),
    )
    def update_client_color_options(
        client: list[str] | str | None,
        product: list[str] | str | None,
        visual_sales_years: list[int] | None,
        visual_week_range: list[int] | None,
        visual_tipo_filter: list[str] | None,
        color_select_all_clicks: int | None,
        color_clear_clicks: int | None,
        current_value: list[str] | str | None,
    ):
        sales = data.get("ventas_semana", pd.DataFrame())
        selected_clients = selected_values(client)
        if not selected_clients and not sales.empty and "color" in sales.columns:
            work = filter_sales_visual(sales, None, [latest_selected_year(visual_sales_years, sales)] if latest_selected_year(visual_sales_years, sales) else None, visual_week_range, visual_tipo_filter, product, None)
            options, colors = tallos_options_from_frame(work, "color")
            value = synced_multi_value(current_value, colors, "color-select-all", "color-clear")
            return options, value
        work = filter_visual_operational_base(
            data,
            data["perfil"],
            selected_clients or None,
            [latest_selected_year(visual_sales_years, sales)] if latest_selected_year(visual_sales_years, sales) else visual_sales_years,
            visual_week_range,
            visual_tipo_filter,
            product,
            None,
            None,
        )
        if work.empty or "color" not in work.columns:
            return [], []
        options, colors = tallos_options_from_frame(work, "color")
        value = synced_multi_value(current_value, colors, "color-select-all", "color-clear")
        return options, value

    @app.callback(
        Output("client-program-filter", "options"),
        Output("client-program-filter", "value"),
        Input("client", "value"),
        Input("client-product-filter", "value"),
        Input("client-color-filter", "value"),
        State("client-program-filter", "value"),
    )
    def update_client_program_options(client: list[str] | str | None, product: list[str] | str | None, color: list[str] | str | None, current_value: str | None):
        summary = data.get("sku_resumen", pd.DataFrame())
        hist = data.get("historico_confirmado", pd.DataFrame())
        selected_clients = selected_values(client)
        if not summary.empty and "sku_operativo" in summary.columns and selected_clients:
            work = summary[summary["cod_cliente"].astype(str).isin(set(selected_clients))].copy()
            products = selected_values(product)
            colors = selected_values(color)
            if products and "producto" in work.columns:
                work = work[work["producto"].astype(str).isin(set(products))].copy()
            if colors:
                comp = data.get("sku_composicion", pd.DataFrame())
                if not comp.empty and "color" in comp.columns:
                    valid_skus = comp[
                        (comp["cod_cliente"].astype(str).isin(set(selected_clients)))
                        & (comp["color"].astype(str).isin(set(colors)))
                    ]["sku_operativo"].astype(str).unique()
                    work = work[work["sku_operativo"].astype(str).isin(set(valid_skus))].copy()
            sort_col = "tallos_promedio_semana_normal" if "tallos_promedio_semana_normal" in work.columns else None
            if sort_col:
                work = work.sort_values(sort_col, ascending=False)
            label_cols = [col for col in ["tipo_pedido_operativo", "producto", "empaque", "tipo_caja", "tallos_por_ramo"] if col in work.columns]
            options = []
            seen = set()
            for row in work.head(250).to_dict("records"):
                sku = str(row.get("sku_operativo", ""))
                if not sku or sku in seen:
                    continue
                seen.add(sku)
                label = operational_sku_filter_label(pd.Series(row))[:160]
                options.append({"label": label, "value": sku})
            value = current_value if current_value in {opt["value"] for opt in options} else None
            return options, value
        if hist.empty or "sku_operativo" not in hist.columns:
            return [], None
        work = hist[hist["cod_cliente"].astype(str).isin(set(selected_clients))].copy() if selected_clients and "cod_cliente" in hist.columns else hist.copy()
        if not selected_clients:
            work = hist.copy()
        products = selected_values(product)
        colors = selected_values(color)
        if products and "producto" in work.columns:
            work = work[work["producto"].astype(str).isin(set(products))].copy()
        if colors and "color" in work.columns:
            work = work[work["color"].astype(str).isin(set(colors))].copy()
        grouped = work.groupby("sku_operativo", as_index=False)["tallos_historicos"].sum().sort_values("tallos_historicos", ascending=False).head(250)
        skus = grouped["sku_operativo"].astype(str).tolist()
        options = [{"label": f"{i}. {operational_sku_filter_label(pd.Series(row._asdict()))[:140]} | {moneyless_number(row.tallos_historicos, 0)} tallos", "value": row.sku_operativo} for i, row in enumerate(grouped.itertuples(index=False), start=1)]
        value = current_value if current_value in set(skus) else None
        return options, value

    @app.callback(
        Output("selected-sku-operativo", "options"),
        Output("selected-sku-operativo", "value"),
        Input("client", "value"),
        Input("client-product-filter", "value"),
        Input("client-color-filter", "value"),
        Input("client-program-filter", "value"),
        State("selected-sku-operativo", "value"),
    )
    def update_selected_sku_options(client: list[str] | str | None, product: list[str] | str | None, color: list[str] | str | None, program: str | None, current_value: str | None):
        summary = data.get("sku_resumen", pd.DataFrame())
        hist = data.get("historico_confirmado", pd.DataFrame())
        selected_clients = selected_values(client)
        if not summary.empty and "sku_operativo" in summary.columns and selected_clients:
            work = summary[summary["cod_cliente"].astype(str).isin(set(selected_clients))].copy()
            products = selected_values(product)
            colors = selected_values(color)
            if products and "producto" in work.columns:
                work = work[work["producto"].astype(str).isin(set(products))].copy()
            if colors:
                comp = data.get("sku_composicion", pd.DataFrame())
                if not comp.empty and "color" in comp.columns:
                    valid_skus = comp[
                        (comp["cod_cliente"].astype(str).isin(set(selected_clients)))
                        & (comp["color"].astype(str).isin(set(colors)))
                    ]["sku_operativo"].astype(str).unique()
                    work = work[work["sku_operativo"].astype(str).isin(set(valid_skus))].copy()
            if program:
                work = work[work["sku_operativo"].astype(str).eq(str(program))].copy()
            if work.empty:
                return [], None
            work = work.sort_values(["tallos_promedio_semana_normal", "frecuencia_en_ventana"], ascending=False).head(300)
            options = []
            for i, row in enumerate(work.to_dict("records"), start=1):
                sku = str(row.get("sku_operativo", ""))
                metric = moneyless_number(row.get("tallos_promedio_semana_normal", 0), 0)
                pct = percent(row.get("porcentaje_semana_normal", 0))
                freq = moneyless_number(row.get("frecuencia_en_ventana", 0), 0)
                label = f"{i}. {operational_sku_filter_label(pd.Series(row))[:140]} | {metric} tallos/sem | {freq} sem"
                options.append({"label": label, "value": sku})
            valid = {opt["value"] for opt in options}
            value = current_value if current_value in valid else None
            return options, value
        if hist.empty or "sku_operativo" not in hist.columns:
            return [], None
        work = hist[hist["cod_cliente"].astype(str).isin(set(selected_clients))].copy() if selected_clients and "cod_cliente" in hist.columns else hist.copy()
        products = selected_values(product)
        colors = selected_values(color)
        if products and "producto" in work.columns:
            work = work[work["producto"].astype(str).isin(set(products))].copy()
        if colors and "color" in work.columns:
            work = work[work["color"].astype(str).isin(set(colors))].copy()
        if program:
            work = work[work["sku_operativo"].astype(str).eq(str(program))].copy()
        grouped = work.groupby("sku_operativo", as_index=False)["tallos_historicos"].sum().sort_values("tallos_historicos", ascending=False).head(300)
        options = [{"label": f"{i}. {operational_sku_filter_label(pd.Series(row._asdict()))[:140]} | {moneyless_number(row.tallos_historicos, 0)} tallos", "value": row.sku_operativo} for i, row in enumerate(grouped.itertuples(index=False), start=1)]
        value = current_value if current_value in {opt["value"] for opt in options} else None
        return options, value

    @app.callback(
        Output("general-sales-report-download", "data"),
        Input("general-sales-export-summary", "n_clicks"),
        Input("general-sales-export-full", "n_clicks"),
        Input("general-sales-export-raw", "n_clicks"),
        State("general-sales-base-year", "value"),
        State("general-sales-compare-year", "value"),
        State("general-sales-years", "value"),
        State("general-sales-week-range", "value"),
        State("general-sales-companies", "value"),
        State("general-sales-clients", "value"),
        State("general-sales-countries", "value"),
        State("general-sales-products", "value"),
        State("general-sales-colors", "value"),
        prevent_initial_call=True,
    )
    def export_general_sales_report(summary_clicks, full_clicks, raw_clicks, base_year, compare_year, years, week_range, companies, clients, countries, products, colors):
        if not summary_clicks and not full_clicks and not raw_clicks:
            return dash.no_update
        if ctx.triggered_id == "general-sales-export-raw":
            raw = sales_raw_export_frame(data, years, week_range, companies, clients, countries, products, colors)
            if raw.empty:
                return dash.no_update
            years_text = "_".join(map(str, selected_values(years))) if selected_values(years) else "todos"
            weeks_text = f"sem_{int(week_range[0])}_{int(week_range[1])}" if week_range and len(week_range) == 2 else "semanas_todas"
            return dcc.send_data_frame(
                raw.to_csv,
                f"ventas_base_cruda_{years_text}_{weeks_text}.csv",
                index=False,
                encoding="utf-8-sig",
            )
        sales = data.get("ventas_semana", pd.DataFrame())
        if sales.empty:
            return dash.no_update
        view = filter_general_sales_frame(sales, years, week_range, clients, products, countries, companies, colors)
        if view.empty:
            return dash.no_update
        context = build_sales_executive_context_v2(view, base_year, compare_year)
        if not context.get("ok"):
            return dash.no_update
        scope = sales_scope_summary(view, clients, products, countries, companies, colors)
        report_type = "full" if ctx.triggered_id == "general-sales-export-full" else "summary"
        weekly = summarize_sales_frame(view, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
        report_pdf = build_sales_report_pdf(context, scope, weekly=weekly, report_type=report_type, view=view)
        suffix = "completo" if report_type == "full" else "resumido_1_pagina"
        filename = f"informe_ventas_{suffix}_{context.get('base_year', 'base')}_vs_{context.get('compare_year', 'comp')}.pdf"
        return dcc.send_bytes(report_pdf, filename=filename)

    @app.callback(
        Output("admin-refresh-status", "children"),
        Output("client", "options"),
        Output("client", "value"),
        Input("admin-refresh-data", "n_clicks"),
        State("client", "value"),
        prevent_initial_call=True,
    )
    def refresh_dashboard_data(refresh_clicks, current_clients):
        if not refresh_clicks:
            return dash.no_update, dash.no_update, dash.no_update
        try:
            data.clear()
            data.update(load_data(data_dir, forecast_dir))
            options = build_client_dropdown_options(data.get("perfil", pd.DataFrame()))
            valid_values = {str(option["value"]) for option in options}
            selected_clients = [value for value in selected_values(current_clients) if str(value) in valid_values]
            stamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"Datos recargados desde SQL: {stamp}.", options, selected_clients
        except Exception as exc:
            return f"No se pudieron recargar los datos: {exc}", dash.no_update, dash.no_update

    @app.callback(
        Output("admin-run-job", "data"),
        Input("admin-dry-run", "n_clicks"),
        Input("admin-run-etl", "n_clicks"),
        State("admin-password", "value"),
        State("admin-date-range", "start_date"),
        State("admin-date-range", "end_date"),
        State("admin-split-by", "value"),
        State("admin-chunk-size", "value"),
        State("admin-extra-actions", "value"),
        State("admin-run-job", "data"),
        prevent_initial_call=True,
    )
    def start_admin_etl(dry_clicks, run_clicks, password, start_date, end_date, split_by, chunk_size, extra_actions, current_job):
        if not dry_clicks and not run_clicks:
            return dash.no_update
        if str(password or "").strip() != ADMIN_PASSWORD:
            return {"message": "Contrasena incorrecta."}
        if not start_date or not end_date:
            return {"message": "Selecciona fecha inicial y fecha final."}
        start = pd.to_datetime(start_date, errors="coerce")
        end = pd.to_datetime(end_date, errors="coerce")
        if pd.isna(start) or pd.isna(end):
            return {"message": "Rango de fechas invalido."}
        if start > end:
            return {"message": "La fecha inicial no puede ser mayor que la fecha final."}
        try:
            chunk = int(chunk_size or 5000)
        except (TypeError, ValueError):
            return {"message": "Filas por lote debe ser numerico."}
        if chunk <= 0:
            return {"message": "Filas por lote debe ser mayor que cero."}

        with ADMIN_ETL_JOB_LOCK:
            running_ids = [job_id for job_id, job in ADMIN_ETL_JOBS.items() if job.get("status") == "running"]
        if running_ids:
            current_job_id = current_job.get("job_id") if isinstance(current_job, dict) else None
            job_id = current_job_id if current_job_id in running_ids else running_ids[0]
            admin_job_append(job_id, "Ya hay una ejecucion en curso; se ignoro el nuevo clic.")
            return {"job_id": job_id}

        start_text = start.strftime("%Y-%m-%d")
        end_text = end.strftime("%Y-%m-%d")
        split = split_by or "none"
        triggered = ctx.triggered_id
        is_dry_run = triggered == "admin-dry-run"
        selected_actions = set(extra_actions or [])
        commands: list[tuple[str, list[str]]] = []
        load_command = [
            sys.executable,
            "cargar_op_sales_sql.py",
            "--from-cuadernillo",
            "--start-date",
            start_text,
            "--end-date",
            end_text,
            "--chunk-size",
            str(chunk),
            "--split-by",
            split,
        ]
        if is_dry_run:
            load_command.append("--dry-run")
        commands.append(("Validacion ETL sin escritura" if is_dry_run else "Carga ETL a SQL", load_command))
        if not is_dry_run:
            if "descriptivos" in selected_actions:
                commands.append(
                    (
                        "Regenerar descriptivos desde SQL",
                        [
                            sys.executable,
                            "run_descriptivos.py",
                            "--source",
                            "sql",
                            "--start-date",
                            start_text,
                            "--end-date",
                            end_text,
                            "--output",
                            str(data_dir),
                            "--no-cache",
                        ],
                    )
                )
            if "forecast" in selected_actions:
                commands.append(
                    (
                        "Regenerar forecast solidos",
                        [
                            sys.executable,
                            "run_forecast_solidos.py",
                            "--source",
                            "sql",
                            "--output",
                            str(forecast_dir or DEFAULT_FORECAST_DIR),
                            "--no-cache",
                        ],
                    )
                )
            if "materialize" in selected_actions:
                materialize_command = [
                    sys.executable,
                    "materializar_op_sales_resultados_sql.py",
                    "--start-date",
                    start_text,
                    "--end-date",
                    end_text,
                    "--descriptivos-dir",
                    str(data_dir),
                    "--forecast-dir",
                    str(forecast_dir or DEFAULT_FORECAST_DIR),
                ]
                if "descriptivos" not in selected_actions and "forecast" not in selected_actions:
                    materialize_command.append("--skip-results")
                commands.append(("Reconstruir agregados SQL del Dash", materialize_command))

        initial_lines = [
            f"[{admin_job_timestamp()}] Administrador iniciado",
            f"[{admin_job_timestamp()}] Rango: {start_text} a {end_text}",
            f"[{admin_job_timestamp()}] Modo: {'validacion sin escritura' if is_dry_run else 'carga real'}",
            f"[{admin_job_timestamp()}] Particion: {split}",
            f"[{admin_job_timestamp()}] Pasos programados: {len(commands)}",
            "",
        ]
        job_id = admin_job_create(initial_lines, [title for title, _command in commands])
        worker = threading.Thread(
            target=run_admin_etl_job,
            args=(job_id, commands, is_dry_run, data, data_dir, forecast_dir),
            daemon=True,
        )
        worker.start()
        return {"job_id": job_id}

    @app.callback(
        Output("admin-run-output", "children"),
        Output("admin-run-poll", "disabled"),
        Input("admin-run-job", "data"),
        Input("admin-run-poll", "n_intervals"),
        prevent_initial_call=True,
    )
    def refresh_admin_etl_console(job_data, _n_intervals):
        if isinstance(job_data, dict) and job_data.get("message"):
            return str(job_data["message"]), True
        job_id = job_data.get("job_id") if isinstance(job_data, dict) else None
        text, done = admin_job_snapshot(job_id)
        return text, done

    app.index_string = """
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <style>
                body { margin: 0; background: #f4f6f8; color: #17202a; font-family: Arial, sans-serif; }
                .app-header { display: flex; justify-content: space-between; gap: 24px; padding: 22px 28px; background: #800020; color: white; align-items: center; }
                .app-header h1 { margin: 0 0 6px; font-size: 28px; letter-spacing: 0; }
                .app-header p { margin: 0; color: #F3E8EC; max-width: 760px; }
                .header-meta { text-align: right; display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
                .source-line { color: #F3E8EC; font-size: 12px; max-width: 520px; overflow-wrap: anywhere; }
                .tech-pill { background: #4E79A7; padding: 6px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }
                .app-shell { display: grid; grid-template-columns: 420px minmax(0, 1fr); min-height: calc(100vh - 93px); }
                .filters { background: white; border-right: 1px solid #d8dee6; padding: 18px; display: flex; flex-direction: column; gap: 10px; max-height: calc(100vh - 93px); overflow-y: auto; }
                .filters label { font-size: 12px; color: #44505e; font-weight: 700; margin-top: 8px; text-transform: uppercase; }
                .filter-help { background: #f5f7fa; border: 1px solid #dfe5ec; border-radius: 8px; padding: 10px; color: #526070; font-size: 12px; line-height: 1.35; }
                .filter-actions { display: flex; gap: 8px; margin-top: 7px; }
                .filter-actions button { border: 1px solid #cfd8e3; background: #f8fafc; color: #23313f; border-radius: 6px; padding: 6px 9px; font-size: 12px; font-weight: 700; cursor: pointer; }
                .filter-actions button:hover { background: #F3E8EC; border-color: #800020; color: #800020; }
                .filter-actions button:active { background: #E8D2DA; }
                .demand-control .Select-value { background: #F3E8EC; border-color: #D7A8B8; color: #17202a; }
                .demand-control .Select-value-icon { border-right-color: #D7A8B8; color: #800020; }
                .demand-control .Select-value-icon:hover { background: #E8D2DA; color: #800020; }
                .demand-control .Select-value-label { color: #17202a; }
                .sku-picker-control { margin-top: 4px; }
                .sku-multiselect .Select-control,
                .sku-multiselect .select__control { min-height: 120px; align-items: flex-start; border-color: #cfd8e3; border-radius: 8px; background: #f8fafc; }
                .sku-multiselect .Select-multi-value-wrapper { padding: 6px; }
                .sku-multiselect .Select-value { max-width: calc(100% - 10px); margin: 4px; background: #F3E8EC; border-color: #D7A8B8; color: #17202a; }
                .sku-multiselect .Select-value-label { white-space: normal; line-height: 1.25; font-size: 12px; }
                .sku-multiselect .Select-menu-outer { max-height: 420px; border-color: #cfd8e3; }
                .sku-multiselect .VirtualizedSelectOption { white-space: normal; line-height: 1.3; padding: 10px 12px; font-size: 12px; }
                .content { min-width: 0; padding: 18px; }
                .tab-content { padding-top: 16px; }
                .metrics-grid { display: grid; grid-template-columns: repeat(4, minmax(170px, 1fr)); gap: 12px; margin-bottom: 14px; }
                .visual-metrics { grid-template-columns: repeat(6, minmax(150px, 1fr)); }
                .metric-card { background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%); border: 1px solid #dfe5ec; border-radius: 8px; padding: 14px; min-height: 84px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06); }
                .metric-card-accent { border-top: 4px solid #4E79A7; }
                .metric-card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
                .metric-card-comparison { min-height: 128px; }
                .metric-title { color: #667382; font-size: 12px; font-weight: 700; text-transform: uppercase; }
                .metric-value { font-size: 26px; line-height: 34px; font-weight: 800; color: #17202a; overflow-wrap: anywhere; }
                .metric-detail { color: #6f7c8a; font-size: 12px; }
                .delta-badge { border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 800; white-space: nowrap; }
                .delta-badge.positive { color: #006B4A; background: #E3F5EE; }
                .delta-badge.negative { color: #A5281B; background: #FCE8E6; }
                .delta-badge.neutral { color: #5b6775; background: #EEF2F6; }
                .sales-executive-panel { background: transparent; margin-top: 14px; }
                .sales-executive-header { display: flex; justify-content: space-between; gap: 18px; align-items: center; background: linear-gradient(135deg, #ffffff 0%, #f8fafc 62%, #f3e8ec 100%); border: 1px solid #dfe5ec; border-radius: 8px; padding: 18px 20px; margin-bottom: 12px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06); }
                .executive-logo { display: block; max-width: 168px; max-height: 54px; object-fit: contain; margin-bottom: 10px; }
                .executive-logo-text { color: #800020; font-size: 18px; font-weight: 800; margin-bottom: 8px; }
                .executive-kicker { color: #800020; font-size: 12px; font-weight: 800; text-transform: uppercase; margin-bottom: 4px; }
                .executive-title { color: #17202a; font-size: 24px; line-height: 30px; font-weight: 800; }
                .executive-subtitle { color: #667382; font-size: 13px; margin-top: 4px; }
                .executive-actions { display: flex; align-items: center; justify-content: flex-end; }
                .executive-button-group { display: flex; gap: 9px; flex-wrap: wrap; justify-content: flex-end; }
                .executive-button { border-radius: 6px; padding: 10px 14px; font-weight: 800; cursor: pointer; border: 1px solid #800020; }
                .executive-button.primary { background: #800020; color: white; }
                .executive-button.secondary { background: white; color: #800020; }
                .executive-button:hover { box-shadow: 0 8px 18px rgba(128, 0, 32, 0.16); }
                .admin-hero { background: linear-gradient(135deg, #ffffff 0%, #f8fafc 58%, #eef4fb 100%); border: 1px solid #dfe5ec; border-radius: 8px; padding: 18px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06); }
                .admin-hero-title { color: #17202a; font-size: 26px; line-height: 32px; font-weight: 800; }
                .admin-hero-subtitle { color: #667382; font-size: 13px; margin-top: 4px; }
                .admin-status-grid { display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 12px; margin-top: 16px; }
                .admin-status-card { background: white; border: 1px solid #dfe5ec; border-left: 4px solid #4E79A7; border-radius: 8px; padding: 13px 14px; min-height: 72px; }
                .admin-status-card-accent { border-left-color: #800020; }
                .admin-card-label { color: #667382; font-size: 11px; font-weight: 800; text-transform: uppercase; margin-bottom: 7px; }
                .admin-card-value { color: #17202a; font-size: 20px; line-height: 26px; font-weight: 800; overflow-wrap: anywhere; }
                .admin-guidance { background: #ffffff; border: 1px solid #dfe5ec; border-radius: 8px; padding: 16px; }
                .admin-guidance-list { display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 10px; margin-top: 10px; }
                .admin-guidance-item { background: #f8fafc; border: 1px solid #e5ebf2; border-radius: 8px; padding: 11px 12px; color: #344252; font-size: 13px; line-height: 1.35; }
                .admin-input { width: 100%; box-sizing: border-box; border: 1px solid #cfd8e3; border-radius: 6px; padding: 9px 10px; font-size: 13px; }
                .admin-output { margin-top: 14px; min-height: 180px; max-height: 520px; overflow: auto; background: #17202a; color: #f8fafc; border-radius: 8px; padding: 14px; font-size: 12px; line-height: 1.45; white-space: pre-wrap; }
                .scope-strip { display: grid; grid-template-columns: minmax(260px, 1.4fr) minmax(240px, 1.1fr) minmax(140px, 0.45fr) minmax(140px, 0.45fr); gap: 12px; margin-bottom: 14px; }
                .scope-card { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 12px 14px; box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04); min-height: 58px; }
                .scope-card-wide { border-left: 4px solid #4E79A7; }
                .scope-label { color: #667382; font-size: 11px; font-weight: 800; text-transform: uppercase; margin-bottom: 5px; }
                .scope-value { color: #17202a; font-size: 13px; line-height: 1.35; font-weight: 700; overflow-wrap: anywhere; }
                .scope-number { color: #17202a; font-size: 24px; line-height: 28px; font-weight: 800; }
                .executive-table-grid { display: grid; grid-template-columns: minmax(320px, 0.9fr) minmax(520px, 1.6fr); gap: 14px; align-items: start; }
                .strategic-layout { display: grid; grid-template-columns: minmax(340px, 0.78fr) minmax(560px, 1.35fr); gap: 14px; align-items: stretch; }
                .strategy-panel { background: #17202a; border: 1px solid #26323f; border-radius: 8px; padding: 10px 12px 14px; color: white; box-shadow: 0 14px 30px rgba(15, 23, 42, 0.14); min-width: 0; }
                .strategy-panel .panel-title { color: white; }
                .strategy-panel .panel-note { color: #cbd5e1; }
                .strategy-grid { display: grid; grid-template-columns: 1fr; gap: 9px; padding: 8px 6px 2px; }
                .strategy-card { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 10px; align-items: start; background: rgba(255, 255, 255, 0.07); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 10px; }
                .strategy-index { color: #F3E8EC; font-size: 12px; font-weight: 800; letter-spacing: 0; }
                .strategy-text { color: #f8fafc; font-size: 13px; line-height: 1.4; }
                .year-comparison { margin: 8px 0 6px; display: flex; flex-direction: column; gap: 5px; }
                .year-row { display: grid; grid-template-columns: 44px minmax(70px, 1fr) minmax(96px, auto); gap: 6px; align-items: baseline; font-size: 12px; }
                .year-label { font-weight: 700; color: #44505e; }
                .year-value { font-size: 16px; font-weight: 800; color: #17202a; text-align: right; overflow-wrap: anywhere; }
                .year-delta { text-align: right; font-weight: 700; font-size: 11px; }
                .year-delta.positive { color: #00875A; }
                .year-delta.negative { color: #C0392B; }
                .year-delta.neutral { color: #6f7c8a; }
                .grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
                .grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
                .panel { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 8px; min-width: 0; box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04); }
                .panel-feature { border-top: 4px solid #4E79A7; box-shadow: 0 12px 28px rgba(15, 23, 42, 0.07); }
                .panel-title { font-size: 15px; font-weight: 800; padding: 8px 10px 0; }
                .table-panel { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 12px; margin-top: 14px; box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04); }
                .no-top-margin { margin-top: 0; }
                .reading-panel { background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #dfe5ec; border-left: 5px solid #800020; border-radius: 8px; padding: 10px 14px 16px; margin-bottom: 14px; box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05); }
                .reading-text { color: #26323f; font-size: 16px; line-height: 1.48; padding: 8px 10px 0; max-width: 1200px; }
                .section-gap { margin-top: 14px; }
                .demand-options { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 10px 12px; margin-top: 12px; font-weight: 700; color: #334155; display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr)); gap: 16px; align-items: start; }
                .forecast-options-panel { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 16px; margin-top: 12px; color: #334155; }
                .forecast-controls-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 14px; }
                .forecast-controls-title { font-size: 20px; font-weight: 800; color: #17202a; }
                .forecast-controls-subtitle { font-size: 13px; font-weight: 400; color: #667382; margin-top: 4px; }
                .forecast-controls-header button { border: 1px solid #800020; background: white; color: #800020; border-radius: 6px; padding: 9px 14px; font-size: 13px; font-weight: 700; cursor: pointer; }
                .forecast-controls-header button:hover { background: #F3E8EC; }
                .forecast-filter-group { border: 1px solid #dfe5ec; border-radius: 8px; padding: 13px 14px 16px; margin-top: 12px; background: #fbfcfd; }
                .forecast-filter-group.scope { border-left: 4px solid #4E79A7; }
                .forecast-filter-group.projection { border-left: 4px solid #00875A; }
                .forecast-filter-group.history { border-left: 4px solid #9CA3AF; }
                .forecast-filter-group.validation { border-left: 4px solid #F28E2B; }
                .forecast-filter-group.scenario { border-left: 4px solid #800020; }
                .forecast-filter-title { font-size: 17px; font-weight: 800; color: #17202a; margin-bottom: 3px; }
                .forecast-filter-effect { font-size: 13px; font-weight: 400; color: #667382; margin-bottom: 14px; }
                .forecast-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 14px; align-items: start; }
                .forecast-filter-grid-5 { grid-template-columns: repeat(5, minmax(150px, 1fr)); }
                .forecast-filter-grid.compact { grid-template-columns: minmax(260px, 420px); }
                .report-step-title { font-size: 22px; font-weight: 800; color: #17202a; margin: 24px 0 10px; padding-bottom: 7px; border-bottom: 2px solid #e5eaf0; }
                .demand-control label { display: block; font-size: 12px; color: #44505e; font-weight: 700; margin-bottom: 6px; text-transform: uppercase; }
                @media (max-width: 1050px) {
                    .app-shell { grid-template-columns: 1fr; }
                    .filters { border-right: 0; border-bottom: 1px solid #d8dee6; }
                    .metrics-grid, .visual-metrics, .grid-2, .grid-3 { grid-template-columns: 1fr; }
                    .executive-table-grid, .scope-strip, .strategic-layout { grid-template-columns: 1fr; }
                    .sales-executive-header { flex-direction: column; align-items: flex-start; }
                    .forecast-filter-grid, .forecast-filter-grid-5, .forecast-filter-grid.compact { grid-template-columns: 1fr; }
                    .forecast-controls-header { flex-direction: column; align-items: flex-start; }
                    .app-header { flex-direction: column; align-items: flex-start; }
                    .header-meta { text-align: left; align-items: flex-start; }
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    """
    return app


def filter_profile(
    perfil: pd.DataFrame,
    recommendations: list[str] | None,
    segments: list[str] | None,
    min_score: int,
    max_inactive_weeks: int | None = None,
) -> pd.DataFrame:
    if perfil.empty:
        return perfil
    out = perfil.copy()
    if recommendations:
        out = out[out["recomendacion_compra"].isin(recommendations)]
    if segments:
        out = out[out["segmento_cliente"].isin(segments)]
    out = out[out["score_compra_terminada"].fillna(0) >= min_score]
    if max_inactive_weeks is not None and "dias_desde_ultima_compra" in out.columns:
        out = out[out["dias_desde_ultima_compra"].fillna(99999) <= max_inactive_weeks * 7]
    return out


def add_week_columns(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return df
    out = df.copy()
    dates = pd.to_datetime(out[date_col], errors="coerce")
    iso = dates.dt.isocalendar()
    out["anio_iso"] = iso.year.astype("Int64")
    out["semana_iso"] = iso.week.astype("Int64")
    out["semana_label"] = out["anio_iso"].astype(str) + "-W" + out["semana_iso"].astype(str).str.zfill(2)
    out["anio_semana"] = out["semana_label"]
    out["fecha_semana"] = dates.dt.strftime("%Y-%m-%d") + " | " + out["semana_label"]
    out["week_start"] = pd.to_datetime(
        out["anio_iso"].astype(str) + "-W" + out["semana_iso"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u",
        errors="coerce",
    )
    return out


def filter_solidos(df: pd.DataFrame, product: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "tipo_pedido_operativo" in out.columns:
        out = out[out["tipo_pedido_operativo"].astype(str).str.upper().eq("SOLIDO")].copy()
    if product and "producto" in out.columns:
        out = out[out["producto"].astype(str).eq(str(product))].copy()
    return out


def filter_operational_scope(df: pd.DataFrame, scope: str | None = "solidos", product: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    scope = scope or "solidos"
    if "tipo_pedido_operativo" in out.columns:
        tipo = out["tipo_pedido_operativo"].astype(str).str.upper()
        if scope == "solidos":
            out = out[tipo.eq("SOLIDO")].copy()
        elif scope == "estructuras":
            out = out[tipo.isin(["SURTIDO", "SURTIDO_M", "RAINBOW", "BQT", "BOUQUET", "COMBO"])].copy()
        elif scope == "bulk":
            out = out[tipo.eq("BULK")].copy()
    if product and "producto" in out.columns:
        out = out[out["producto"].astype(str).eq(str(product))].copy()
    return out


def scope_label(scope: str | None) -> tuple[str, str]:
    labels = {
        "solidos": ("Solidos color/caja", "color define SKU"),
        "estructuras": ("Estructuras mixtas", "color como componente"),
        "bulk": ("Bulk color/base", "volumen por producto-color"),
        "todos": ("Todos los formatos", "lectura por familia operativa"),
    }
    return labels.get(scope or "solidos", labels["solidos"])


def future_window_bounds(df: pd.DataFrame, week_offset: int, visible_weeks: int) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if df.empty or "fecha_forecast" not in df.columns:
        return None, None
    start_base = pd.to_datetime(df["fecha_forecast"], errors="coerce").min()
    if pd.isna(start_base):
        return None, None
    start = start_base + pd.Timedelta(weeks=int(week_offset or 0))
    end = start + pd.Timedelta(days=max(int(visible_weeks or 1), 1) * 7 - 1)
    return start.normalize(), end.normalize()


def apply_future_window(df: pd.DataFrame, week_offset: int, visible_weeks: int) -> pd.DataFrame:
    if df.empty or "fecha_forecast" not in df.columns:
        return df
    start, end = future_window_bounds(df, week_offset, visible_weeks)
    if start is None or end is None:
        return df
    dates = pd.to_datetime(df["fecha_forecast"], errors="coerce")
    return df[(dates >= start) & (dates <= end)].copy()


def window_detail(df: pd.DataFrame, week_offset: int, visible_weeks: int) -> str:
    start, end = future_window_bounds(df, week_offset, visible_weeks)
    if start is None or end is None:
        return "sin ventana de fechas"
    return f"{start:%Y-%m-%d} a {end:%Y-%m-%d}"


def select_client(filtered: pd.DataFrame, perfil: pd.DataFrame, client: str | None) -> pd.Series | None:
    if client is None:
        return None
    source = filtered if not filtered.empty else perfil
    if source.empty or client not in set(source["cod_cliente"]):
        return None
    return source[source["cod_cliente"] == client].iloc[0]


def render_segment_overview(data: dict[str, pd.DataFrame], filtered: pd.DataFrame, top_n: int):
    top = filtered.sort_values(["score_compra_terminada", "tallos_total"], ascending=False).head(top_n).copy()
    top["cliente_label"] = top["cod_cliente"] + " - " + top["cliente"].astype(str).str.slice(0, 34)
    top_fig = px.bar(
        top,
        x="score_compra_terminada",
        y="cliente_label",
        orientation="h",
        color="segmento_cliente",
        color_discrete_map=color_map_for(top, "segmento_cliente"),
        title="Clientes del segmento/filtro actual",
        hover_data=["recomendacion_compra", "tallos_total", "cumplimiento_tallos"],
    )
    top_fig.update_layout(yaxis={"categoryorder": "total ascending"})
    apply_common_layout(top_fig, 520)

    segment_summary = (
        filtered.groupby("segmento_cliente", dropna=False, as_index=False)
        .agg(
            clientes=("cod_cliente", "nunique"),
            tallos=("tallos_total", "sum"),
            score_promedio=("score_compra_terminada", "mean"),
            cumplimiento_promedio=("cumplimiento_tallos", "mean"),
        )
        .sort_values("tallos", ascending=False)
    )
    segment_fig = px.treemap(
        segment_summary,
        path=["segmento_cliente"],
        values="tallos",
        color="score_promedio",
        color_continuous_scale="Teal",
        title="Peso de los segmentos por tallos historicos",
    )
    apply_common_layout(segment_fig, 430)

    table_cols = [
        "cod_cliente",
        "cliente",
        "segmento_cliente",
        "recomendacion_compra",
        "score_compra_terminada",
        "tallos_total",
        "semanas_activas",
        "ultima_fecha_confirmada",
        "dias_desde_ultima_compra",
        "semanas_activas_ult_12w",
        "tallos_ult_12w",
        "cumplimiento_tallos",
        "share_top5_sku_terminado",
        "share_top3_color",
        "share_facil_compra",
        "share_rainbow",
        "score_facilidad_compra_operativa",
    ]
    table = filtered[[col for col in table_cols if col in filtered.columns]].sort_values("score_compra_terminada", ascending=False)

    return html.Div(
        [
            html.Div(
                [
                    make_card("Clientes", moneyless_number(filtered["cod_cliente"].nunique()), "filtro actual"),
                    make_card("Tallos", moneyless_number(filtered["tallos_total"].sum()), "historico confirmado"),
                    make_card("Score promedio", moneyless_number(filtered["score_compra_terminada"].mean(), 1), "compra terminada"),
                    make_card("Cumplimiento", percent(filtered["cumplimiento_tallos"].mean()), "promedio simple"),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div(dcc.Graph(figure=top_fig), className="panel"), html.Div(dcc.Graph(figure=segment_fig), className="panel")], className="grid-2"),
            html.Div([html.Div("Clientes del segmento/filtro", className="panel-title"), make_table(table.head(500), 18)], className="table-panel"),
        ]
    )


def _top_values(df: pd.DataFrame, col: str, value_col: str = "tallos_historicos", n: int = 3) -> list[str]:
    if df.empty or col not in df.columns:
        return []
    work = df.groupby(col, dropna=False)[value_col].sum().sort_values(ascending=False).head(n)
    return [str(idx) for idx in work.index if str(idx) and str(idx) != "nan"]


def build_client_summary_text(selected: pd.Series, hist: pd.DataFrame) -> str:
    if hist.empty:
        return "No hay historico confirmado suficiente para leer el comportamiento de este cliente."
    max_date = hist["fecha"].max()
    r12 = hist[hist["fecha"] >= max_date - pd.Timedelta(weeks=12)].copy()
    r4 = hist[hist["fecha"] >= max_date - pd.Timedelta(weeks=4)].copy()
    source = r12 if not r12.empty else hist
    products = ", ".join(_top_values(source, "producto", n=2)) or "sin producto dominante"
    colors = ", ".join(_top_values(source, "color", n=3)) or "sin color dominante"
    tipos = _top_values(source, "tipo_pedido_operativo", n=2)
    tipo_text = ", ".join(tipos) if tipos else "sin tipo dominante"
    r12_total = r12["tallos_historicos"].sum() if not r12.empty else 0
    r4_total = r4["tallos_historicos"].sum() if not r4.empty else 0
    r12_weekly = r12_total / max(r12["anio_semana"].nunique(), 1) if not r12.empty else 0
    r4_weekly = r4_total / max(r4["anio_semana"].nunique(), 1) if not r4.empty else 0
    if r4_weekly > r12_weekly * 1.15:
        trend = "viene subiendo en las ultimas semanas"
    elif r4_weekly < r12_weekly * 0.85:
        trend = "viene bajando en las ultimas semanas"
    else:
        trend = "se mantiene parecido al promedio reciente"
    solid_share = float(selected.get("share_solido", 0) or 0)
    mixed_share = float(selected.get("share_estructuras_mixtas", 0) or 0)
    if solid_share >= 0.55:
        recommendation = "prioriza revisar compra terminada en solidos recurrentes."
    elif mixed_share >= 0.45:
        recommendation = "maneja surtidos y recetas por mezcla de colores/composicion, no por SKU exacto."
    else:
        recommendation = "usa compra por color/base o revision manual segun estructura."
    return (
        f"Este cliente compra principalmente {products}. Su pedido se concentra en {tipo_text}. "
        f"Los colores principales recientes son {colors}. El volumen {trend}. "
        f"Para compra anticipada: {recommendation}"
    )


def build_historical_recent_table(hist: pd.DataFrame, include_historical: bool = True) -> pd.DataFrame:
    if hist.empty:
        return pd.DataFrame()
    max_date = hist["fecha"].max()
    windows = []
    if include_historical:
        windows.append(("Historico completo", hist))
    windows.extend([
        ("Ultimas 12 semanas", hist[hist["fecha"] >= max_date - pd.Timedelta(weeks=12)]),
        ("Ultimas 4 semanas", hist[hist["fecha"] >= max_date - pd.Timedelta(weeks=4)]),
    ])
    hist_weekly = hist["tallos_historicos"].sum() / max(hist["anio_semana"].nunique(), 1)
    rows = []
    for name, frame in windows:
        if frame.empty:
            rows.append({"ventana": name, "tallos_promedio_semana": 0, "producto_principal": "sin datos", "color_principal": "sin datos", "tipo_pedido_principal": "sin datos", "cambio_frente_historico": "sin datos"})
            continue
        avg = frame["tallos_historicos"].sum() / max(frame["anio_semana"].nunique(), 1)
        change = (avg - hist_weekly) / hist_weekly if hist_weekly else np.nan
        rows.append({
            "ventana": name,
            "tallos_promedio_semana": round(avg, 1),
            "producto_principal": (_top_values(frame, "producto", n=1) or ["sin datos"])[0],
            "color_principal": (_top_values(frame, "color", n=1) or ["sin datos"])[0],
            "tipo_pedido_principal": (_top_values(frame, "tipo_pedido_operativo", n=1) or ["sin datos"])[0],
            "cambio_frente_historico": "base" if name == "Historico completo" else (f"{change * 100:,.1f}%" if pd.notna(change) else "sin base"),
        })
    return pd.DataFrame(rows)


def build_score_explanation(selected: pd.Series) -> pd.DataFrame:
    rows = [
        ("Frecuencia", selected.get("score_frecuencia", 0), "Compra en muchas semanas activas; mejor si es recurrente."),
        ("Volumen", selected.get("score_volumen", 0), "Evalua estabilidad semanal, no total historico acumulado."),
        ("Color", selected.get("score_color", 0), "Mejor cuando pocos colores explican la compra y se repiten."),
        ("SKU terminado", selected.get("score_sku_terminado", 0), "Aplica fuerte para SOLIDO; en surtidos se lee con composicion."),
        ("Tipo de pedido", selected.get("score_tipo_pedido", 0), "Mejor cuando el formato operativo se mantiene."),
        ("Cumplimiento", selected.get("score_oportunidad_incumplimiento", 0), "Alto indica oportunidad por faltantes; no significa cliente estable por si solo."),
    ]
    out = pd.DataFrame(rows, columns=["Factor", "Resultado", "Lectura"])
    out["Resultado"] = pd.to_numeric(out["Resultado"], errors="coerce").fillna(0).round(1)
    return out


def build_structure_table(data: dict[str, pd.DataFrame], hist: pd.DataFrame, selected_code: str, top_n: int) -> pd.DataFrame:
    estructuras = data.get("estructuras", pd.DataFrame())
    if not estructuras.empty:
        work = estructuras[estructuras["cod_cliente"] == selected_code].copy()
        if not work.empty:
            return work.head(max(top_n, 15))
    if hist.empty:
        return pd.DataFrame()
    max_date = hist["fecha"].max()
    r12 = hist[hist["fecha"] >= max_date - pd.Timedelta(weeks=12)].copy()
    keys = ["cod_cliente", "cliente", "producto", "variedad", "color", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque", "tipo_pedido_operativo"]
    keys = [col for col in keys if col in hist.columns]
    base = hist.groupby(keys, dropna=False, as_index=False).agg(cumplimiento_num=("tallos_confirmados", "sum"), tallos_total=("tallos_historicos", "sum"))
    if not r12.empty:
        recent = r12.groupby(keys, dropna=False, as_index=False).agg(
            tallos_ultimas_12_semanas=("tallos_historicos", "sum"),
            frecuencia_ultimas_12_semanas=("anio_semana", "nunique"),
        )
        base = base.merge(recent, on=keys, how="left")
    for col in ["tallos_ultimas_12_semanas", "frecuencia_ultimas_12_semanas"]:
        if col not in base.columns:
            base[col] = 0
        base[col] = base[col].fillna(0)
    base["cumplimiento"] = (base["cumplimiento_num"] / base["tallos_total"].replace(0, np.nan)).fillna(0).clip(0, 1)
    tipo = base["tipo_pedido_operativo"].astype(str).str.upper()
    base["vigencia_estructura"] = np.where(base["frecuencia_ultimas_12_semanas"] > 0, "VIGENTE", "HISTORICA_NO_RECIENTE")
    base["recomendacion"] = np.select(
        [
            tipo.eq("SOLIDO") & base["frecuencia_ultimas_12_semanas"].ge(2),
            tipo.ne("SOLIDO") & base["frecuencia_ultimas_12_semanas"].ge(2),
            base["frecuencia_ultimas_12_semanas"].eq(0),
        ],
        ["PILOTO", "REVISAR_ESTRUCTURA_PEDIDO", "NO_ANTICIPAR"],
        default="REVISAR_MANUAL",
    )
    base = base.rename(columns={"tallos_x_ramo": "tallos_por_ramo"})
    cols = [col for col in STRUCTURE_COLS if col in base.columns]
    return base[cols].sort_values(["tallos_ultimas_12_semanas", "frecuencia_ultimas_12_semanas"], ascending=False).head(max(top_n, 15))


def build_typical_week_table(data: dict[str, pd.DataFrame], hist: pd.DataFrame, selected_code: str, week: int, top_n: int) -> pd.DataFrame:
    week_table = data.get("semana_tipica", pd.DataFrame())
    if not week_table.empty:
        work = week_table[(week_table["cod_cliente"] == selected_code) & (week_table["semana"].astype("Int64") == int(week))].copy()
        if not work.empty:
            return work.head(max(top_n, 15))
    if hist.empty:
        return pd.DataFrame()
    work = hist[hist["semana_iso"].astype(int) == int(week)].copy()
    if work.empty:
        return pd.DataFrame({"clasificacion_semana": ["SEMANA_SIN_HISTORIA"], "semana": [week]})
    keys = ["producto", "tipo_pedido_operativo", "color", "variedad", "tipo_caja", "tallos_x_ramo"]
    keys = [col for col in keys if col in work.columns]
    by_year = work.groupby(keys + ["anio_iso"], dropna=False, as_index=False)["tallos_historicos"].sum()
    out = by_year.groupby(keys, dropna=False, as_index=False).agg(
        tallos_mediana_historica_semana=("tallos_historicos", "median"),
        tallos_promedio_historico_semana=("tallos_historicos", "mean"),
        veces_aparece_en_misma_semana=("anio_iso", "nunique"),
    )
    out["semana"] = week
    out["comportamiento_reciente"] = 0
    out["confianza"] = np.where(out["veces_aparece_en_misma_semana"] >= 3, "ALTA", "MEDIA")
    out["clasificacion_semana"] = np.where(out["veces_aparece_en_misma_semana"] >= 2, "SEMANA_ESTABLE", "SEMANA_SIN_PATRON")
    out = out.rename(columns={"tallos_x_ramo": "tallos_por_ramo"})
    cols = [col for col in TYPICAL_WEEK_COLS if col in out.columns]
    return out[cols].sort_values("tallos_mediana_historica_semana", ascending=False).head(max(top_n, 15))


def client_analysis_windows(hist: pd.DataFrame, analysis_week: int, lookback_weeks: int) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if hist.empty:
        return hist, hist, "sin historico"
    work = hist.copy()
    dates = pd.to_datetime(work["fecha"], errors="coerce")
    max_date = dates.max()
    max_year = int(max_date.isocalendar().year)
    max_available_week = int(max_date.isocalendar().week)
    week = int(analysis_week or max_date.isocalendar().week)
    adjusted = False
    if week > max_available_week:
        week = max_available_week
        adjusted = True
    try:
        target = pd.to_datetime(f"{max_year}-W{week:02d}-7", format="%G-W%V-%u")
    except ValueError:
        target = max_date
    if pd.isna(target) or target > max_date:
        target = max_date
        adjusted = True
    start = target - pd.Timedelta(weeks=max(int(lookback_weeks or 12), 1)) + pd.Timedelta(days=1)
    current = work[(dates >= start) & (dates <= target)].copy()
    ly_start = start - pd.DateOffset(years=1)
    ly_end = target - pd.DateOffset(years=1)
    last_year = work[(dates >= ly_start) & (dates <= ly_end)].copy()
    suffix = " | ajustado a ultima semana disponible" if adjusted else ""
    label = f"{start:%Y-%m-%d} a {target:%Y-%m-%d} | semana {week}{suffix}"
    return current, last_year, label


def apply_client_detail_filters(df: pd.DataFrame, product: list[str] | str | None, color: list[str] | str | None, program: str | None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    products = selected_values(product)
    colors = selected_values(color)
    if products and "producto" in out.columns:
        out = out[out["producto"].astype(str).isin(set(products))].copy()
    if colors and "color" in out.columns:
        out = out[out["color"].astype(str).isin(set(colors))].copy()
    if program:
        if "sku_operativo" in out.columns:
            out = out[out["sku_operativo"].astype(str).eq(str(program))].copy()
        elif "llave_analisis_operativo" in out.columns:
            out = out[out["llave_analisis_operativo"].astype(str).eq(str(program))].copy()
    return out


def regular_week_window(df: pd.DataFrame) -> pd.DataFrame:
    """Return regular weeks for normal-week averages.

    Weeks very far above or below the median are kept visible in weekly history
    but excluded from "semana normal" averages. If too few regular weeks remain,
    fall back to the full selected window.
    """
    if df.empty or "anio_semana" not in df.columns:
        return df
    weekly = df.groupby("anio_semana", as_index=False)["tallos_historicos"].sum()
    if len(weekly) < 4:
        return df
    median = weekly["tallos_historicos"].median()
    q25 = weekly["tallos_historicos"].quantile(0.25)
    q75 = weekly["tallos_historicos"].quantile(0.75)
    iqr = q75 - q25
    if median <= 0:
        return df
    low = max(q25 - 1.5 * iqr, median * 0.45)
    high = min(q75 + 1.5 * iqr, median * 1.75)
    regular_weeks = weekly[weekly["tallos_historicos"].between(low, high)]["anio_semana"]
    if regular_weeks.nunique() < max(2, min(4, weekly["anio_semana"].nunique() // 2)):
        return df
    return df[df["anio_semana"].isin(set(regular_weeks))].copy()


def recent_line_figure(current: pd.DataFrame, last_year: pd.DataFrame, show_last_year: bool, volume_metric: str = "tallos_pedidos") -> go.Figure:
    if current.empty and (last_year.empty or not show_last_year):
        return empty_figure("Tallos y ventas recientes")
    value_col = "tallos_confirmados" if volume_metric == "tallos_confirmados" else "tallos_historicos"
    y_title = "Tallos confirmados" if volume_metric == "tallos_confirmados" else "Tallos pedidos"
    pieces = []
    for name, frame in [("Periodo seleccionado", current), ("Ano anterior", last_year if show_last_year else pd.DataFrame())]:
        if frame.empty:
            continue
        tmp = frame.copy()
        tmp["anio_linea"] = pd.to_datetime(tmp["fecha"], errors="coerce").dt.isocalendar().year.astype(int)
        tmp["semana_linea"] = pd.to_datetime(tmp["fecha"], errors="coerce").dt.isocalendar().week.astype(int)
        weekly = tmp.groupby(["anio_linea", "semana_linea"], as_index=False).agg(
            tallos=(value_col, "sum"),
            ventas_usd=("ventas_usd", "sum"),
        )
        weekly["serie"] = weekly["anio_linea"].astype(str)
        pieces.append(weekly)
    long = pd.concat(pieces, ignore_index=True)
    fig = go.Figure()
    for serie_name, tmp in long.groupby("serie"):
        tmp = tmp.sort_values("semana_linea")
        fig.add_trace(go.Scatter(x=tmp["semana_linea"], y=tmp["tallos"], mode="lines+markers", name=f"Tallos {serie_name}"))
    fig.update_layout(
        title=f"{y_title} por semana ISO: ano actual vs ano anterior",
        template="plotly_white",
        height=430,
        xaxis=dict(title="Semana del ano", dtick=1),
        yaxis=dict(title=y_title),
        margin=dict(l=24, r=24, t=56, b=40),
        legend_title_text="",
    )
    return fig


def ranked_recent_figure(df: pd.DataFrame, dimension: str, title: str, top_n: int) -> go.Figure:
    if df.empty or dimension not in df.columns:
        return empty_figure(title)
    active_weeks = max(df["anio_semana"].nunique(), 1)
    grouped = df.groupby(dimension, dropna=False, as_index=False).agg(tallos=("tallos_historicos", "sum"))
    grouped["tallos_promedio_semana_normal"] = grouped["tallos"] / active_weeks
    total_avg = grouped["tallos_promedio_semana_normal"].sum()
    grouped["porcentaje_semana_normal"] = grouped["tallos_promedio_semana_normal"] / total_avg if total_avg else 0
    grouped = grouped.sort_values("tallos_promedio_semana_normal", ascending=False).head(top_n)
    grouped["texto"] = (grouped["porcentaje_semana_normal"] * 100).round(1).astype(str) + "%"
    fig = px.bar(
        grouped,
        x="tallos_promedio_semana_normal",
        y=dimension,
        orientation="h",
        color="porcentaje_semana_normal",
        text="texto",
        title=title,
        color_continuous_scale=[CORPORATE_BURGUNDY, "#B07AA1", "#4E79A7", "#59A14F"],
    )
    fig.update_traces(textfont_color=GRAPH_TEXT)
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return apply_common_layout(fig, 340)


def build_recent_week_table(hist_window: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if hist_window.empty:
        return pd.DataFrame()
    weekly_total = hist_window.groupby("anio_semana", as_index=False)["tallos_historicos"].sum()
    median = weekly_total["tallos_historicos"].median()
    q75 = weekly_total["tallos_historicos"].quantile(0.75)
    q25 = weekly_total["tallos_historicos"].quantile(0.25)
    rows = []
    for week, tmp in hist_window.groupby("anio_semana"):
        tallos = tmp["tallos_historicos"].sum()
        cumplimiento = tmp["tallos_confirmados"].sum() / tallos if tallos else 0
        if tallos >= max(q75 * 1.35, median * 1.5):
            clasificacion = "PICO"
        elif tallos <= q25 * 0.65:
            clasificacion = "ATIPICA_BAJA"
        elif abs(tallos - median) / median <= 0.25 if median else True:
            clasificacion = "NORMAL"
        else:
            clasificacion = "VARIABLE"
        structures = tmp.groupby("sku_operativo" if "sku_operativo" in tmp.columns else "llave_analisis_operativo")["tallos_historicos"].sum().sort_values(ascending=False).head(4)
        rows.append({
            "semana": week,
            "tallos_pedidos": tallos,
            "ventas_usd": tmp["ventas_usd"].sum(),
            "productos": ", ".join(_top_values(tmp, "producto", n=4)),
            "tipo_pedido": ", ".join(_top_values(tmp, "tipo_pedido_operativo", n=4)),
            "principales_estructuras_skus": ", ".join([str(idx) for idx in structures.index]),
            "cumplimiento": cumplimiento,
            "clasificacion_semana": clasificacion,
        })
    return pd.DataFrame(rows).sort_values("semana", ascending=False).head(max(top_n, 6))


def build_recent_structure_table(hist_window: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if hist_window.empty:
        return pd.DataFrame()
    work = hist_window.copy()
    work["tipo_upper"] = work["tipo_pedido_operativo"].astype(str).str.upper()
    if "sku_operativo" not in work.columns:
        work["sku_operativo"] = work.get("llave_analisis_operativo", work.get("producto_color", work.get("sku_terminado", "sin_info")))
    work["estructura_lectura"] = np.select(
        [
            work["tipo_upper"].eq("SOLIDO"),
            work["tipo_upper"].ne("SOLIDO"),
        ],
        [
            work.get("producto_color", work.get("sku_terminado", work["sku_operativo"])),
            work["sku_operativo"],
        ],
        default=work.get("llave_analisis_operativo", "sin_info"),
    )
    keys = [
        "estructura_lectura",
        "tipo_pedido_operativo",
        "producto",
        "variedad",
        "tipo_caja",
        "tallos_x_ramo",
        "capuchon",
        "comida",
        "empaque",
    ]
    keys = [col for col in keys if col in work.columns]
    base = work.groupby(keys, dropna=False, as_index=False).agg(
        tallos=("tallos_historicos", "sum"),
        ventas_usd=("ventas_usd", "sum"),
        semanas=("anio_semana", "nunique"),
        cumplimiento_num=("tallos_confirmados", "sum"),
    )
    active_weeks = max(work["anio_semana"].nunique(), 1)
    base["tallos_promedio_semana_normal"] = base["tallos"] / active_weeks
    total_avg = base["tallos_promedio_semana_normal"].sum()
    base["porcentaje_semana_normal"] = base["tallos_promedio_semana_normal"] / total_avg if total_avg else 0
    base["cumplimiento"] = (base["cumplimiento_num"] / base["tallos"].replace(0, np.nan)).fillna(0).clip(0, 1)
    color_mix = work.groupby(keys + ["color"], dropna=False, as_index=False)["tallos_historicos"].sum()
    total = color_mix.groupby(keys, dropna=False, as_index=False)["tallos_historicos"].sum().rename(columns={"tallos_historicos": "total_estructura"})
    color_mix = color_mix.merge(total, on=keys, how="left")
    color_mix["share"] = color_mix["tallos_historicos"] / color_mix["total_estructura"].replace(0, np.nan)
    color_mix["mix_color"] = color_mix["color"].astype(str) + " " + (color_mix["share"] * 100).round(0).astype("Int64").astype(str) + "%"
    mix_text = color_mix.sort_values("tallos_historicos", ascending=False).groupby(keys, dropna=False)["mix_color"].apply(lambda s: ", ".join(s.head(6))).reset_index()
    base = base.merge(mix_text, on=keys, how="left")
    tipo = base["tipo_pedido_operativo"].astype(str).str.upper()
    base["lectura_operativa"] = np.select(
        [
            tipo.eq("SOLIDO"),
            tipo.ne("SOLIDO"),
        ],
        ["SKU terminado exacto", "Estructura de pedido"],
        default="Revision manual",
    )
    base["recomendacion"] = np.select(
        [
            tipo.eq("SOLIDO") & base["semanas"].ge(2) & base["cumplimiento"].ge(0.9),
            tipo.eq("SOLIDO") & base["semanas"].ge(1),
            tipo.ne("SOLIDO") & base["semanas"].ge(2),
        ],
        ["COMPRAR_TERMINADO", "PILOTO", "REVISAR_ESTRUCTURA_PEDIDO"],
        default="NO_ANTICIPAR",
    )
    base = base.rename(columns={"tallos_x_ramo": "tallos_por_ramo"})
    cols = [
        "tipo_pedido_operativo",
        "lectura_operativa",
        "producto",
        "variedad",
        "tipo_caja",
        "tallos_por_ramo",
        "capuchon",
        "comida",
        "empaque",
        "mix_color",
        "tallos_promedio_semana_normal",
        "porcentaje_semana_normal",
        "semanas",
        "cumplimiento",
        "recomendacion",
        "estructura_lectura",
    ]
    return base[[col for col in cols if col in base.columns]].sort_values(["tallos_promedio_semana_normal", "semanas"], ascending=False).head(max(top_n, 15))


def structure_table_from_outputs(data: dict[str, pd.DataFrame], selected_code: str, top_n: int) -> pd.DataFrame:
    summary = data.get("sku_resumen", pd.DataFrame())
    if summary.empty:
        return pd.DataFrame()
    work = summary[summary["cod_cliente"] == selected_code].copy()
    if work.empty:
        return pd.DataFrame()
    return work.sort_values(["tallos_promedio_semana_normal", "frecuencia_en_ventana"], ascending=False).head(max(top_n, 15))


def build_sku_composition_table(hist_window: pd.DataFrame, structure_table: pd.DataFrame, selected_sku: str | None) -> pd.DataFrame:
    if hist_window.empty or structure_table.empty:
        return pd.DataFrame()
    sku = selected_sku
    if not sku:
        sku = structure_table.iloc[0].get("sku_operativo") or structure_table.iloc[0].get("estructura_lectura")
    if not sku:
        return pd.DataFrame()
    work = hist_window.copy()
    if "sku_operativo" not in work.columns:
        work["sku_operativo"] = work.get("llave_analisis_operativo", work.get("producto_color", work.get("sku_terminado", "sin_info")))
    tipo = work["tipo_pedido_operativo"].astype(str).str.upper()
    work["estructura_lectura"] = np.select(
        [
            tipo.eq("SOLIDO"),
            tipo.ne("SOLIDO"),
        ],
        [
            work.get("producto_color", work.get("sku_terminado", work["sku_operativo"])),
            work["sku_operativo"],
        ],
        default=work["sku_operativo"],
    )
    work = work[work["estructura_lectura"].astype(str).eq(str(sku))].copy()
    if work.empty:
        return pd.DataFrame()
    active_weeks = max(work["anio_semana"].nunique(), 1)
    keys = ["producto", "color", "variedad", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque"]
    keys = [col for col in keys if col in work.columns]
    out = work.groupby(keys, dropna=False, as_index=False).agg(
        tallos=("tallos_historicos", "sum"),
        ramos=("ramos_pedidos", "sum") if "ramos_pedidos" in work.columns else ("tallos_historicos", "size"),
        semanas=("anio_semana", "nunique"),
    )
    out["tallos_promedio_semana_normal"] = out["tallos"] / active_weeks
    out["ramos_promedio_semana_normal"] = out["ramos"] / active_weeks
    total = out["tallos"].sum()
    out["porcentaje_color_sku"] = out["tallos"] / total if total else 0
    weekly_color = work.groupby(["anio_semana", "color"], dropna=False)["tallos_historicos"].sum().reset_index()
    totals = weekly_color.groupby("anio_semana", as_index=False)["tallos_historicos"].sum().rename(columns={"tallos_historicos": "total"})
    weekly_color = weekly_color.merge(totals, on="anio_semana", how="left")
    weekly_color["share"] = weekly_color["tallos_historicos"] / weekly_color["total"].replace(0, np.nan)
    stability = weekly_color.groupby("color", as_index=False)["share"].std().rename(columns={"share": "variacion_share_color"})
    out = out.merge(stability, on="color", how="left")
    out["estabilidad_composicion"] = np.select(
        [
            out["variacion_share_color"].fillna(0).le(0.08),
            out["variacion_share_color"].fillna(0).le(0.18),
        ],
        ["ESTABLE", "MEDIA"],
        default="VARIABLE",
    )
    return out.sort_values("tallos_promedio_semana_normal", ascending=False)


def sku_composition_from_outputs(data: dict[str, pd.DataFrame], selected_code: str, structure_table: pd.DataFrame, selected_sku: str | None) -> pd.DataFrame:
    comp = data.get("sku_composicion", pd.DataFrame())
    if comp.empty or structure_table.empty:
        return pd.DataFrame()
    sku = selected_sku
    if not sku:
        sku = structure_table.iloc[0].get("sku_operativo") or structure_table.iloc[0].get("estructura_lectura")
    if not sku:
        return pd.DataFrame()
    work = comp[(comp["cod_cliente"] == selected_code) & (comp["sku_operativo"].astype(str) == str(sku))].copy()
    return work.sort_values("tallos_promedio_semana_normal", ascending=False)


def render_cliente_tab(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected: pd.Series | None,
    selected_code: str | None,
    top_n: int,
    history_weeks: int = 12,
    analysis_week: int = 1,
    show_last_year: bool = True,
    selected_sku_operativo: str | None = None,
    volume_metric: str = "tallos_pedidos",
    product_filter: list[str] | str | None = None,
    color_filter: list[str] | str | None = None,
    program_filter: str | None = None,
):
    if selected is None or selected_code is None:
        if filtered.empty:
            return html.Div("No hay clientes para los filtros seleccionados.", className="table-panel")
        return render_segment_overview(data, filtered, top_n)

    hist = data.get("historico_visualizador_comercial", data.get("historico_confirmado", pd.DataFrame()))
    if hist.empty:
        hist = read_client_sku_week_from_sql(selected_code)
    hist_client = hist[hist["cod_cliente"] == selected_code].copy() if not hist.empty else pd.DataFrame()
    hist_filtered = apply_client_detail_filters(hist_client, product_filter, color_filter, program_filter)
    current_window, last_year_window, window_label = client_analysis_windows(hist_filtered, analysis_week, history_weeks)
    regular_window = regular_week_window(current_window)
    normal_note = "semanas regulares" if len(regular_window) < len(current_window) else "ventana completa"
    summary_text = build_client_summary_text(selected, hist_client)
    recent_week_table = build_recent_week_table(current_window, top_n)
    score_table = build_score_explanation(selected)
    structure_table = build_recent_structure_table(regular_window, top_n)
    fallback_structure_table = build_structure_table(data, hist_client, selected_code, top_n)
    if structure_table.empty:
        structure_table = fallback_structure_table
    trend = recent_line_figure(current_window, last_year_window, show_last_year, volume_metric)
    sku_composition = sku_composition_from_outputs(data, selected_code, structure_table, selected_sku_operativo)
    if sku_composition.empty:
        sku_composition = build_sku_composition_table(regular_window, structure_table, selected_sku_operativo)

    mix_product = ranked_recent_figure(regular_window, "producto", f"Producto reciente ({normal_note})", top_n)
    mix_color = ranked_recent_figure(regular_window, "color", f"Color reciente ({normal_note})", top_n)
    mix_tipo = ranked_recent_figure(regular_window, "tipo_pedido_operativo", f"Tipo de pedido reciente ({normal_note})", top_n)

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Lectura automatica del cliente", className="panel-title"),
                    html.Div(summary_text, className="reading-text"),
                ],
                className="reading-panel",
            ),
            html.Div(
                [
                    make_card("Cliente", f"{selected['cod_cliente']}", str(selected["cliente"])),
                    make_card("Promedio semanal", moneyless_number(selected.get("tallos_promedio_semana"), 1), "historico confirmado"),
                    make_card("Ultima compra", selected.get("ultima_fecha_confirmada").strftime("%Y-%m-%d") if pd.notna(selected.get("ultima_fecha_confirmada")) else "sin fecha", f"{moneyless_number(selected.get('dias_desde_ultima_compra'))} dias"),
                    make_card("Ventana", f"{history_weeks} semanas", window_label),
                    make_card("Filtro", selected_label(product_filter), f"color: {selected_label(color_filter)}" if selected_values(color_filter) else ("programa aplicado" if program_filter else "sin programa")),
                    make_card("Base promedio", normal_note, f"{regular_window['anio_semana'].nunique() if not regular_window.empty else 0} semanas"),
                ],
                className="metrics-grid",
            ),
            html.Div(
                [
                    html.Div([html.Div("Ultimas semanas del cliente", className="panel-title"), make_table(recent_week_table, max(min(top_n, 12), 6))], className="table-panel no-top-margin"),
                    html.Div([html.Div("Score explicado", className="panel-title"), make_table(score_table, 6)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div([html.Div(dcc.Graph(figure=trend), className="panel")], className="section-gap"),
            html.Div(
                [
                    html.Div(dcc.Graph(figure=mix_product), className="panel"),
                    html.Div(dcc.Graph(figure=mix_color), className="panel"),
                    html.Div(dcc.Graph(figure=mix_tipo), className="panel"),
                ],
                className="grid-3 section-gap",
            ),
            html.Div([html.Div("Estructuras/SKUs recientes segun la ventana seleccionada", className="panel-title"), make_table(structure_table, 12)], className="table-panel"),
            html.Div([html.Div("Composicion interna del SKU operativo seleccionado", className="panel-title"), make_table(sku_composition, 12)], className="table-panel"),
        ]
    )


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    numeric_values = pd.to_numeric(values, errors="coerce").fillna(0)
    numeric_weights = pd.to_numeric(weights, errors="coerce").fillna(0)
    total_weight = numeric_weights.sum()
    if total_weight <= 0:
        positive = numeric_values[numeric_values > 0]
        return float(positive.mean()) if not positive.empty else 0.0
    return float((numeric_values * numeric_weights).sum() / total_weight)


def price_summary_from_hist(hist: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if hist.empty:
        return pd.DataFrame()
    work = hist.copy()
    for col in ["tallos_historicos", "tallos_confirmados", "ventas_usd", "VALORUNITARIO", "VALORTOTAL"]:
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    if "NomMoneda" not in work.columns:
        work["NomMoneda"] = "SIN_MONEDA"
    if "pedido" not in work.columns:
        work["pedido"] = ""
    if "cod_cliente" not in work.columns:
        work["cod_cliente"] = ""

    rows = []
    for keys, frame in work.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        tallos = frame["tallos_historicos"].sum()
        tallos_confirmados = frame["tallos_confirmados"].sum()
        ventas_usd = frame["ventas_usd"].sum()
        original_total = frame["VALORTOTAL"].sum()
        moneda = frame["NomMoneda"].dropna().astype(str).mode()
        row.update(
            {
                "tallos": tallos,
                "tallos_confirmados": tallos_confirmados,
                "ventas_usd": ventas_usd,
                "precio_usd_tallo": ventas_usd / tallos if tallos else 0,
                "moneda_original": moneda.iloc[0] if not moneda.empty else "SIN_MONEDA",
                "precio_moneda_original": original_total / tallos if original_total > 0 and tallos else weighted_average(frame["VALORUNITARIO"], frame["tallos_historicos"]),
                "pedidos": frame["pedido"].nunique(),
                "clientes": frame["cod_cliente"].nunique(),
                "cumplimiento": tallos_confirmados / tallos if tallos else 0,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def format_visual_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in ["tallos", "tallos_confirmados", "ventas_usd"]:
        if col in out.columns:
            decimals = 2 if col == "ventas_usd" else 0
            out[col] = out[col].map(lambda value: moneyless_number(value, decimals))
    for col in ["precio_usd_tallo", "precio_moneda_original"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 4))
    if "cumplimiento" in out.columns:
        out["cumplimiento"] = out["cumplimiento"].map(percent)
    return out


def visual_client_reading(selected: pd.Series | None, hist: pd.DataFrame, product_table: pd.DataFrame, client_table: pd.DataFrame, window_label: str) -> str:
    if hist.empty:
        return "No hay historico suficiente para los filtros seleccionados. Selecciona otro cliente, producto, color o ventana."
    tallos = hist["tallos_historicos"].sum() if "tallos_historicos" in hist.columns else 0
    ventas = hist["ventas_usd"].sum() if "ventas_usd" in hist.columns else 0
    precio_usd = ventas / tallos if tallos else 0
    products = product_table.head(3)["producto"].astype(str).tolist() if not product_table.empty and "producto" in product_table.columns else []
    product_text = ", ".join(products) if products else "sin producto dominante"
    monedas = hist["NomMoneda"].dropna().astype(str).value_counts().head(2).index.tolist() if "NomMoneda" in hist.columns else []
    moneda_text = ", ".join(monedas) if monedas else "sin moneda registrada"
    if selected is not None:
        cliente = f"{selected.get('cod_cliente')} - {selected.get('cliente')}"
        return (
            f"{cliente} concentra {moneyless_number(tallos)} tallos en la ventana {window_label}. "
            f"Los productos que mas explican la compra son {product_text}. "
            f"El precio promedio en dolares es {moneyless_number(precio_usd, 4)} por tallo y las monedas originales visibles son {moneda_text}."
        )
    clientes = client_table["cod_cliente"].nunique() if not client_table.empty and "cod_cliente" in client_table.columns else 0
    return (
        f"El visualizador resume {moneyless_number(clientes)} clientes con {moneyless_number(tallos)} tallos en la ventana {window_label}. "
        f"Los productos lideres son {product_text}. Precio promedio USD por tallo: {moneyless_number(precio_usd, 4)}."
    )


def weekly_year_general_figure(hist: pd.DataFrame, volume_metric: str, title: str) -> go.Figure:
    if hist.empty:
        return empty_figure(title)
    value_col = "tallos_confirmados" if volume_metric == "tallos_confirmados" and "tallos_confirmados" in hist.columns else "tallos_historicos"
    work = hist.copy()
    work["anio_linea"] = pd.to_numeric(work["anio_iso"], errors="coerce").astype("Int64")
    work["semana_linea"] = pd.to_numeric(work["semana_iso"], errors="coerce").astype("Int64")
    weekly = (
        work.dropna(subset=["anio_linea", "semana_linea"])
        .groupby(["anio_linea", "semana_linea"], as_index=False)
        .agg(tallos=(value_col, "sum"), ventas_usd=("ventas_usd", "sum"))
    )
    if weekly.empty:
        return empty_figure(title)
    fig = px.line(
        weekly,
        x="semana_linea",
        y="tallos",
        color="anio_linea",
        markers=True,
        hover_data=["ventas_usd"],
        title=title,
    )
    fig.update_layout(xaxis_title="Semana", yaxis_title="Tallos", xaxis=dict(dtick=2))
    return apply_common_layout(fig, 430)


def price_year_figures(hist: pd.DataFrame) -> tuple[go.Figure, go.Figure]:
    if hist.empty:
        return empty_figure("Precio USD por ano"), empty_figure("Precio moneda original por ano")
    work = hist.copy()
    work["anio_precio"] = pd.to_numeric(work["anio_iso"], errors="coerce").astype("Int64")
    price_year = price_summary_from_hist(work.dropna(subset=["anio_precio"]), ["anio_precio"])
    if price_year.empty:
        usd_fig = empty_figure("Precio USD por ano")
    else:
        usd_fig = px.line(price_year.sort_values("anio_precio"), x="anio_precio", y="precio_usd_tallo", markers=True, title="Precio venta en USD por ano")
        usd_fig.update_traces(fill="tozeroy")
        usd_fig.update_layout(xaxis_title="Ano", yaxis_title="USD/tallo")
        apply_common_layout(usd_fig, 330)

    price_currency = price_summary_from_hist(work.dropna(subset=["anio_precio"]), ["anio_precio", "NomMoneda"])
    if price_currency.empty:
        original_fig = empty_figure("Precio moneda original por ano")
    else:
        original_fig = px.line(
            price_currency.sort_values("anio_precio"),
            x="anio_precio",
            y="precio_moneda_original",
            color="NomMoneda",
            markers=True,
            title="Precio en moneda original por ano",
        )
        original_fig.update_layout(xaxis_title="Ano", yaxis_title="Moneda original/tallo")
        apply_common_layout(original_fig, 330)
    return usd_fig, original_fig


def overview_cache_key(valid_codes: set[str]) -> int:
    if not valid_codes:
        return 0
    return int(pd.util.hash_pandas_object(pd.Index(sorted(valid_codes)), index=False).sum())


def build_visual_overview_summary(data: dict[str, pd.DataFrame], valid_codes: set[str]) -> dict[str, pd.DataFrame]:
    cache = data.setdefault("_overview_cache", {})
    key = overview_cache_key(valid_codes)
    if key in cache:
        return cache[key]

    serie = data.get("serie", pd.DataFrame())
    mix_producto = data.get("mix_producto", pd.DataFrame())
    mix_color = data.get("mix_color", pd.DataFrame())
    mix_sku = data.get("mix_sku", pd.DataFrame())

    if not serie.empty and valid_codes:
        weekly_source = serie[serie["cod_cliente"].astype(str).isin(valid_codes)].copy()
        weekly_source["anio_linea"] = pd.to_numeric(weekly_source["anio"], errors="coerce")
        weekly_source["semana_linea"] = pd.to_numeric(weekly_source["semana_iso"], errors="coerce")
        week_table = weekly_source.groupby(["anio_linea", "semana_linea"], dropna=False, as_index=False)["tallos"].sum()
    else:
        week_table = pd.DataFrame()

    if not mix_producto.empty and valid_codes:
        products = mix_producto[mix_producto["cod_cliente"].astype(str).isin(valid_codes)].copy()
        product_table = (
            products.groupby("producto", dropna=False, as_index=False)
            .agg(
                tallos=("tallos", "sum"),
                tallos_confirmados=("tallos_confirmados", "sum"),
                ventas_usd=("ventas_usd", "sum") if "ventas_usd" in products.columns else ("tallos", "sum"),
                faltante_tallos=("faltante_tallos", "sum") if "faltante_tallos" in products.columns else ("tallos", "sum"),
                clientes=("cod_cliente", "nunique"),
            )
            .sort_values("tallos", ascending=False)
        )
        product_table["cumplimiento"] = np.where(product_table["tallos"] > 0, product_table["tallos_confirmados"] / product_table["tallos"], 0)
    else:
        product_table = pd.DataFrame()

    if not mix_color.empty and valid_codes:
        colors = mix_color[mix_color["cod_cliente"].astype(str).isin(valid_codes)].copy()
        color_table = (
            colors.groupby("color", dropna=False, as_index=False)
            .agg(
                tallos=("tallos", "sum"),
                tallos_confirmados=("tallos_confirmados", "sum"),
                ventas_usd=("ventas_usd", "sum") if "ventas_usd" in colors.columns else ("tallos", "sum"),
                clientes=("cod_cliente", "nunique"),
            )
            .sort_values("tallos", ascending=False)
        )
        color_table["cumplimiento"] = np.where(color_table["tallos"] > 0, color_table["tallos_confirmados"] / color_table["tallos"], 0)
    else:
        color_table = pd.DataFrame()

    if not mix_sku.empty and valid_codes:
        skus = mix_sku[mix_sku["cod_cliente"].astype(str).isin(valid_codes)].copy()
        sku_table = (
            skus.groupby("sku_terminado", dropna=False, as_index=False)
            .agg(
                tallos=("tallos", "sum"),
                tallos_confirmados=("tallos_confirmados", "sum"),
                ventas_usd=("ventas_usd", "sum") if "ventas_usd" in skus.columns else ("tallos", "sum"),
                clientes=("cod_cliente", "nunique"),
                producto=("producto", lambda s: top_text(s, 2) if "producto" in skus.columns else ""),
                color=("color", lambda s: top_text(s, 2) if "color" in skus.columns else ""),
                variedad=("variedad", lambda s: top_text(s, 2) if "variedad" in skus.columns else ""),
                tipo_pedido_operativo=("tipo_pedido_operativo", lambda s: top_text(s, 2) if "tipo_pedido_operativo" in skus.columns else ""),
            )
            .sort_values("tallos", ascending=False)
        )
        sku_table["cumplimiento"] = np.where(sku_table["tallos"] > 0, sku_table["tallos_confirmados"] / sku_table["tallos"], 0)
    else:
        sku_table = pd.DataFrame()

    if valid_codes:
        perfil = data.get("perfil", pd.DataFrame())
        client_table = perfil[perfil["cod_cliente"].astype(str).isin(valid_codes)].copy()
        client_cols = [
            "cod_cliente",
            "cliente",
            "segmento_cliente",
            "recomendacion_compra",
            "tallos_total",
            "tallos_promedio_semana",
            "cumplimiento_tallos",
            "score_compra_terminada",
            "ultima_fecha_confirmada",
        ]
        client_table = client_table[[col for col in client_cols if col in client_table.columns]].sort_values("tallos_total", ascending=False)
    else:
        client_table = pd.DataFrame()

    summary = {
        "week_table": week_table,
        "product_table": product_table,
        "color_table": color_table,
        "sku_table": sku_table,
        "client_table": client_table,
    }
    cache[key] = summary
    return summary


def render_visualizador_clientes_general(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected: pd.Series | None,
    selected_code: str | list[str] | None,
    top_n: int,
    history_weeks: int,
    analysis_week: int,
    show_last_year: bool,
    volume_metric: str,
    product_filter: list[str] | str | None,
    color_filter: list[str] | str | None,
    program_filter: str | None,
):
    hist = data.get("historico_confirmado", pd.DataFrame())
    if selected_code is None:
        return render_visualizador_clientes_overview_lite(data, filtered, top_n)
    if hist.empty:
        return html.Div("No hay historico_confirmado.csv disponible para construir el visualizador de este cliente.", className="table-panel")

    work = hist.loc[hist["cod_cliente"].eq(selected_code)].copy()
    work = apply_client_detail_filters(work, product_filter, color_filter, program_filter)

    current_window, last_year_window, window_label = client_analysis_windows(work, analysis_week, history_weeks)
    if show_last_year and not last_year_window.empty:
        visual_hist = pd.concat([current_window, last_year_window], ignore_index=True)
    else:
        visual_hist = current_window
    if visual_hist.empty:
        return html.Div("No hay datos para los filtros seleccionados en esta ventana.", className="table-panel")

    product_table = price_summary_from_hist(visual_hist, ["producto"]).sort_values("tallos", ascending=False).head(max(top_n, 10))
    client_table = price_summary_from_hist(visual_hist, ["cod_cliente", "cliente"]).sort_values("tallos", ascending=False).head(max(top_n, 10))
    sku_cols = [col for col in ["producto", "color", "variedad", "tipo_caja", "sku_operativo", "tipo_pedido_operativo"] if col in visual_hist.columns]
    sku_table = price_summary_from_hist(visual_hist, sku_cols).sort_values("tallos", ascending=False).head(max(top_n, 12)) if sku_cols else pd.DataFrame()
    reading = visual_client_reading(selected, current_window, product_table, client_table, window_label)

    line_fig = weekly_year_general_figure(visual_hist, volume_metric, "Historico semanal por ano")
    product_fig = px.bar(
        product_table.head(max(top_n, 10)),
        x="tallos",
        y="producto",
        orientation="h",
        color="precio_usd_tallo",
        color_continuous_scale=[CORPORATE_BURGUNDY, "#B07AA1", "#4E79A7", "#59A14F"],
        title="Productos por tallos y precio USD",
    ) if not product_table.empty else empty_figure("Productos por tallos y precio USD")
    if not product_table.empty:
        product_fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Tallos", yaxis_title="Producto")
        apply_common_layout(product_fig, 430)
    usd_fig, original_fig = price_year_figures(visual_hist)

    tallos_total = visual_hist["tallos_historicos"].sum()
    ventas_total = visual_hist["ventas_usd"].sum() if "ventas_usd" in visual_hist.columns else 0
    precio_usd = ventas_total / tallos_total if tallos_total else 0
    monedas = visual_hist["NomMoneda"].dropna().astype(str).nunique() if "NomMoneda" in visual_hist.columns else 0
    clientes = visual_hist["cod_cliente"].nunique() if "cod_cliente" in visual_hist.columns else 0
    productos = visual_hist["producto"].nunique() if "producto" in visual_hist.columns else 0

    product_detail = format_visual_table(product_table[["producto", "tallos", "tallos_confirmados", "ventas_usd", "precio_usd_tallo", "moneda_original", "precio_moneda_original", "clientes", "pedidos", "cumplimiento"]])
    client_detail_cols = ["cod_cliente", "cliente", "tallos", "ventas_usd", "precio_usd_tallo", "moneda_original", "precio_moneda_original", "pedidos", "cumplimiento"]
    client_detail = format_visual_table(client_table[[col for col in client_detail_cols if col in client_table.columns]])
    sku_detail = format_visual_table(sku_table)

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Lectura descriptiva del negocio", className="panel-title"),
                    html.Div(reading, className="reading-text"),
                ],
                className="reading-panel",
            ),
            html.Div(
                [
                    make_card("Clientes", moneyless_number(clientes), "con compra en ventana"),
                    make_card("Productos", moneyless_number(productos), "portafolio comprado"),
                    make_card("Tallos", moneyless_number(tallos_total), "historico filtrado"),
                    make_card("Ventas USD", moneyless_number(ventas_total, 2), f"{moneyless_number(precio_usd, 4)} USD/tallo"),
                    make_card("Monedas", moneyless_number(monedas), "moneda original visible"),
                    make_card("Ventana", f"{history_weeks} semanas", window_label),
                ],
                className="metrics-grid visual-metrics",
            ),
            html.Div([html.Div(dcc.Graph(figure=line_fig), className="panel"), html.Div(dcc.Graph(figure=product_fig), className="panel")], className="grid-2"),
            html.Div([html.Div(dcc.Graph(figure=usd_fig), className="panel"), html.Div(dcc.Graph(figure=original_fig), className="panel")], className="grid-2 section-gap"),
            html.Div(
                [
                    html.Div([html.Div("Productos: tallos, ventas y precio", className="panel-title"), make_table(product_detail, 12)], className="table-panel no-top-margin"),
                    html.Div([html.Div("Clientes: lectura comercial general", className="panel-title"), make_table(client_detail, 12)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div([html.Div("Detalle producto / SKU operativo", className="panel-title"), make_table(sku_detail, 12)], className="table-panel"),
        ]
    )


def render_visualizador_clientes_overview(data: dict[str, pd.DataFrame], filtered: pd.DataFrame, top_n: int):
    if filtered.empty:
        return html.Div("No hay clientes para los filtros seleccionados.", className="table-panel")

    perfil = filtered.copy()
    serie = data.get("serie", pd.DataFrame())
    mix_producto = data.get("mix_producto", pd.DataFrame())
    mix_sku = data.get("mix_sku", pd.DataFrame())
    valid_codes = set(perfil["cod_cliente"].astype(str))

    if not serie.empty:
        weekly = serie[serie["cod_cliente"].isin(valid_codes)].copy()
        weekly["anio_linea"] = pd.to_numeric(weekly["anio"], errors="coerce")
        weekly["semana_linea"] = pd.to_numeric(weekly["semana_iso"], errors="coerce")
        week_fig = px.line(
            weekly.groupby(["anio_linea", "semana_linea"], dropna=False, as_index=False)["tallos"].sum(),
            x="semana_linea",
            y="tallos",
            color="anio_linea",
            markers=True,
            title="Historico semanal por ano",
        )
        week_fig.update_layout(xaxis_title="Semana", yaxis_title="Tallos", xaxis=dict(dtick=2))
        apply_common_layout(week_fig, 430)
    else:
        week_fig = empty_figure("Historico semanal por ano")

    if not mix_producto.empty:
        products = mix_producto[mix_producto["cod_cliente"].isin(valid_codes)].copy()
        product_table = (
            products.groupby("producto", dropna=False, as_index=False)
            .agg(
                tallos=("tallos", "sum"),
                tallos_confirmados=("tallos_confirmados", "sum"),
                faltante_tallos=("faltante_tallos", "sum"),
                clientes=("cod_cliente", "nunique"),
            )
            .sort_values("tallos", ascending=False)
            .head(max(top_n, 12))
        )
        product_table["cumplimiento"] = np.where(product_table["tallos"] > 0, product_table["tallos_confirmados"] / product_table["tallos"], 0)
        product_fig = px.bar(
            product_table,
            x="tallos",
            y="producto",
            orientation="h",
            color="cumplimiento",
            color_continuous_scale="Teal",
            title="Productos principales por tallos",
        )
        product_fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Tallos", yaxis_title="Producto")
        apply_common_layout(product_fig, 430)
    else:
        product_table = pd.DataFrame()
        product_fig = empty_figure("Productos principales por tallos")

    client_cols = [
        "cod_cliente",
        "cliente",
        "segmento_cliente",
        "recomendacion_compra",
        "tallos_total",
        "tallos_promedio_semana",
        "cumplimiento_tallos",
        "score_compra_terminada",
        "ultima_fecha_confirmada",
    ]
    client_table = perfil[[col for col in client_cols if col in perfil.columns]].sort_values("tallos_total", ascending=False).head(max(top_n, 15))

    if not mix_sku.empty:
        sku_table = (
            mix_sku[mix_sku["cod_cliente"].isin(valid_codes)]
            .sort_values("tallos", ascending=False)
            .head(max(top_n, 15))[
                [
                    col
                    for col in [
                        "cod_cliente",
                        "cliente",
                        "tipo_pedido_operativo",
                        "producto",
                        "variedad",
                        "color",
                        "tipo_caja",
                        "sku_terminado",
                        "tallos",
                        "tallos_confirmados",
                        "cumplimiento",
                    ]
                    if col in mix_sku.columns
                ]
            ]
        )
    else:
        sku_table = pd.DataFrame()

    top_products = product_table.head(3)["producto"].astype(str).tolist() if not product_table.empty and "producto" in product_table.columns else []
    reading = (
        f"Vista general de {moneyless_number(perfil['cod_cliente'].nunique())} clientes. "
        f"El portafolio lider por tallos es {', '.join(top_products) if top_products else 'sin producto dominante'}. "
        "Para ver precio en dolares y moneda original por cliente, selecciona un cliente en el filtro lateral."
    )

    product_display = product_table.copy()
    for col in ["tallos", "tallos_confirmados", "faltante_tallos"]:
        if col in product_display.columns:
            product_display[col] = product_display[col].map(lambda value: moneyless_number(value))
    if "cumplimiento" in product_display.columns:
        product_display["cumplimiento"] = product_display["cumplimiento"].map(percent)

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Lectura descriptiva general", className="panel-title"),
                    html.Div(reading, className="reading-text"),
                ],
                className="reading-panel",
            ),
            html.Div(
                [
                    make_card("Clientes", moneyless_number(perfil["cod_cliente"].nunique()), "universo filtrado"),
                    make_card("Tallos historicos", moneyless_number(perfil["tallos_total"].sum() if "tallos_total" in perfil.columns else 0), "perfil cliente"),
                    make_card("Promedio semanal", moneyless_number(perfil["tallos_promedio_semana"].sum() if "tallos_promedio_semana" in perfil.columns else 0), "suma promedios cliente"),
                    make_card("Productos", moneyless_number(product_table["producto"].nunique() if not product_table.empty and "producto" in product_table.columns else 0), "mix agregado"),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div(dcc.Graph(figure=week_fig), className="panel"), html.Div(dcc.Graph(figure=product_fig), className="panel")], className="grid-2"),
            html.Div(
                [
                    html.Div([html.Div("Productos agregados", className="panel-title"), make_table(product_display, 12)], className="table-panel no-top-margin"),
                    html.Div([html.Div("Clientes principales", className="panel-title"), make_table(client_table, 12)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div([html.Div("SKUs/productos principales", className="panel-title"), make_table(sku_table, 12)], className="table-panel"),
        ]
    )


def render_visualizador_clientes_overview_lite(data: dict[str, pd.DataFrame], filtered: pd.DataFrame, top_n: int):
    if filtered.empty:
        return html.Div("No hay clientes para los filtros seleccionados.", className="table-panel")

    perfil = filtered.copy()
    valid_codes = set(perfil["cod_cliente"].astype(str))
    summary = build_visual_overview_summary(data, valid_codes)

    week_table = summary["week_table"]
    if not week_table.empty:
        week_fig = px.line(
            week_table.sort_values(["anio_linea", "semana_linea"]),
            x="semana_linea",
            y="tallos",
            color="anio_linea",
            markers=True,
            title="Historico semanal por ano",
        )
        week_fig.update_layout(xaxis_title="Semana", yaxis_title="Tallos", xaxis=dict(dtick=2))
        apply_common_layout(week_fig, 400)
    else:
        week_fig = empty_figure("Historico semanal por ano")

    product_table = summary["product_table"].head(10).copy()
    color_table = summary["color_table"].head(10).copy()
    sku_table = summary["sku_table"].head(10).copy()
    client_table = summary["client_table"].head(10).copy()

    if not product_table.empty:
        product_fig = px.bar(
            product_table,
            x="tallos",
            y="producto",
            orientation="h",
            color="cumplimiento",
            color_continuous_scale=[CORPORATE_BURGUNDY, "#B07AA1", "#4E79A7", "#59A14F"],
            title="Productos top 10 por tallos",
        )
        product_fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Tallos", yaxis_title="Producto")
        apply_common_layout(product_fig, 400)
    else:
        product_fig = empty_figure("Productos top 10 por tallos")

    if not color_table.empty:
        color_fig = px.bar(
            color_table,
            x="tallos",
            y="color",
            orientation="h",
            color="color",
            color_discrete_map=color_map_for(color_table, "color"),
            hover_data=["tallos_confirmados", "ventas_usd", "clientes", "cumplimiento"],
            title="Colores top 10 por tallos",
        )
        color_fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Tallos", yaxis_title="Color")
        apply_common_layout(color_fig, 400)
    else:
        color_fig = empty_figure("Colores top 10 por tallos")

    if not sku_table.empty:
        sku_fig = px.bar(
            sku_table,
            x="tallos",
            y="sku_terminado",
            orientation="h",
            color="tipo_pedido_operativo",
            color_discrete_map=color_map_for(sku_table, "tipo_pedido_operativo"),
            hover_data=["producto", "color", "variedad", "tallos_confirmados", "ventas_usd", "cumplimiento"],
            title="SKUs top 10 por tallos",
        )
        sku_fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Tallos", yaxis_title="SKU terminado")
        apply_common_layout(sku_fig, 400)
    else:
        sku_fig = empty_figure("SKUs top 10 por tallos")

    top_products = product_table.head(3)["producto"].astype(str).tolist() if not product_table.empty and "producto" in product_table.columns else []
    reading = (
        f"Vista general de {moneyless_number(perfil['cod_cliente'].nunique())} clientes. "
        f"El portafolio lider por tallos es {', '.join(top_products) if top_products else 'sin producto dominante'}. "
        "Aqui se resumen productos, colores y SKUs top del universo filtrado."
    )

    def _fmt(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col in ["tallos", "tallos_confirmados", "ventas_usd"]:
            if col in out.columns:
                out[col] = out[col].map(lambda value: moneyless_number(value, 2 if col == "ventas_usd" else 0))
        if "cumplimiento" in out.columns:
            out["cumplimiento"] = out["cumplimiento"].map(percent)
        if "ultima_fecha_confirmada" in out.columns:
            out["ultima_fecha_confirmada"] = pd.to_datetime(out["ultima_fecha_confirmada"], errors="coerce").dt.strftime("%Y-%m-%d")
        return out

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Lectura descriptiva general", className="panel-title"),
                    html.Div(reading, className="reading-text"),
                ],
                className="reading-panel",
            ),
            html.Div(
                [
                    make_card("Clientes", moneyless_number(perfil["cod_cliente"].nunique()), "universo filtrado"),
                    make_card("Tallos historicos", moneyless_number(perfil["tallos_total"].sum() if "tallos_total" in perfil.columns else 0), "perfil cliente"),
                    make_card("Promedio semanal", moneyless_number(perfil["tallos_promedio_semana"].sum() if "tallos_promedio_semana" in perfil.columns else 0), "suma promedios cliente"),
                    make_card("Productos", moneyless_number(product_table["producto"].nunique() if not product_table.empty and "producto" in product_table.columns else 0), "mix agregado"),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div(dcc.Graph(figure=week_fig), className="panel"), html.Div(dcc.Graph(figure=product_fig), className="panel")], className="grid-2"),
            html.Div([html.Div(dcc.Graph(figure=color_fig), className="panel"), html.Div(dcc.Graph(figure=sku_fig), className="panel")], className="grid-2 section-gap"),
            html.Div(
                [
                    html.Div([html.Div("Productos top 10", className="panel-title"), make_table(_fmt(product_table), 10)], className="table-panel no-top-margin"),
                    html.Div([html.Div("Clientes principales", className="panel-title"), make_table(_fmt(client_table), 10)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
        ]
    )


def filter_sales_visual(
    sales: pd.DataFrame,
    selected_code: str | list[str] | None,
    years: list[int] | None,
    week_range: list[int] | None,
    tipo_filter: list[str] | None,
    product_filter: list[str] | str | None,
    color_filter: list[str] | str | None,
) -> pd.DataFrame:
    if sales.empty:
        return sales
    out = sales.copy()
    selected_codes = selected_values(selected_code)
    if selected_codes and "cod_cliente" in out.columns:
        out = out[out["cod_cliente"].astype(str).isin(set(selected_codes))].copy()
    if years and "anio" in out.columns:
        year_set = {int(year) for year in years if pd.notna(year)}
        out = out[pd.to_numeric(out["anio"], errors="coerce").astype("Int64").isin(year_set)].copy()
    if week_range and len(week_range) == 2 and "semana_iso" in out.columns:
        low, high = int(week_range[0]), int(week_range[1])
        weeks = pd.to_numeric(out["semana_iso"], errors="coerce")
        out = out[weeks.between(low, high)].copy()
    if tipo_filter and "tipo_pedido_operativo" in out.columns:
        out = out[out["tipo_pedido_operativo"].astype(str).isin(set(map(str, tipo_filter)))].copy()
    products = selected_values(product_filter)
    colors = selected_values(color_filter)
    if products and "producto" in out.columns:
        out = out[out["producto"].astype(str).isin(set(products))].copy()
    if colors and "color" in out.columns:
        out = out[out["color"].astype(str).isin(set(colors))].copy()
    return out


def summarize_sales_frame(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = df.groupby(group_cols, dropna=False, as_index=False).agg(
        tallos_confirmados=("tallos_confirmados", "sum"),
        ventas_usd=("ventas_usd", "sum"),
        valor_total_original=("valor_total_original", "sum"),
        pedidos=("pedidos", "sum") if "pedidos" in df.columns else ("tallos_confirmados", "size"),
        cajas_ids=("cajas_ids", "sum") if "cajas_ids" in df.columns else ("tallos_confirmados", "size"),
    )
    out["precio_usd_tallo"] = (out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)).fillna(0)
    out["precio_moneda_original_tallo"] = (out["valor_total_original"] / out["tallos_confirmados"].replace(0, np.nan)).fillna(0)
    return out


def format_sales_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    rename = {
        "anio": "Ano",
        "semana_iso": "Semana",
        "cod_cliente": "Cliente",
        "tipo_pedido_operativo": "Tipo",
        "producto": "Producto",
        "color": "Color",
        "moneda_original": "Moneda",
        "tallos_confirmados": "Tallos confirmados",
        "ventas_usd": "Ventas USD",
        "valor_total_original": "Venta moneda original",
        "precio_usd_tallo": "USD/tallo",
        "precio_moneda_original_tallo": "Moneda/tallo",
        "pedidos": "Pedidos",
        "cajas_ids": "Caja IDs",
        "caja_operativa": "Caja ID",
        "tipo_caja": "Tipo caja",
    }
    out = out.rename(columns={col: label for col, label in rename.items() if col in out.columns})
    for col in ["Tallos confirmados", "Pedidos", "Caja IDs"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 0))
    for col in ["Ventas USD", "Venta moneda original"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 2))
    for col in ["USD/tallo", "Moneda/tallo"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 4))
    return out


def sales_product_week_matrix_display(df: pd.DataFrame, selected_clients: list[str] | str | None) -> pd.DataFrame:
    """Build a product-by-week stems matrix for the current sales filters."""
    required = {"anio", "semana_iso", "producto", "tallos_confirmados"}
    if df.empty or not required.issubset(df.columns):
        return pd.DataFrame()

    work = df.copy()
    work["anio_num"] = pd.to_numeric(work["anio"], errors="coerce")
    work["semana_num"] = pd.to_numeric(work["semana_iso"], errors="coerce")
    work = work.dropna(subset=["anio_num", "semana_num"])
    if work.empty:
        return pd.DataFrame()

    work["anio_num"] = work["anio_num"].astype(int)
    work["semana_num"] = work["semana_num"].astype(int)
    single_year = work["anio_num"].nunique() == 1
    work["semana_col"] = np.where(
        single_year,
        "Semana " + work["semana_num"].astype(str).str.zfill(2),
        work["anio_num"].astype(str) + "-S" + work["semana_num"].astype(str).str.zfill(2),
    )
    row_cols = ["producto"]
    if len(selected_values(selected_clients)) != 1 and {"cod_cliente", "cliente"}.issubset(work.columns):
        row_cols = ["cod_cliente", "cliente", "producto"]

    grouped = (
        work.groupby(row_cols + ["semana_col", "anio_num", "semana_num"], dropna=False, as_index=False)["tallos_confirmados"]
        .sum()
        .sort_values(["anio_num", "semana_num"])
    )
    week_cols = grouped[["semana_col", "anio_num", "semana_num"]].drop_duplicates().sort_values(["anio_num", "semana_num"])["semana_col"].tolist()
    matrix = grouped.pivot_table(index=row_cols, columns="semana_col", values="tallos_confirmados", aggfunc="sum", fill_value=0).reset_index()
    matrix = matrix[row_cols + week_cols]
    matrix["Total"] = matrix[week_cols].sum(axis=1)
    matrix = matrix.sort_values("Total", ascending=False).head(250)

    rename = {"cod_cliente": "Cod cliente", "cliente": "Cliente", "producto": "Producto"}
    matrix = matrix.rename(columns=rename)
    for col in week_cols + ["Total"]:
        matrix[col] = pd.to_numeric(matrix[col], errors="coerce").map(lambda value: moneyless_number(value, 0))
    return matrix


def sales_raw_export_frame(data: dict[str, pd.DataFrame], years, week_range, companies, clients, countries, products, colors) -> pd.DataFrame:
    """Return the most detailed available sales frame filtered like Ventas generales."""
    source = data.get("ventas_caja", pd.DataFrame())
    if source.empty:
        source = data.get("ventas_semana", pd.DataFrame())
    if source.empty:
        return pd.DataFrame()
    out = filter_general_sales_frame(source, years, week_range, clients, products, countries, companies, colors)
    if out.empty:
        return out
    helper_cols = [col for col in ["week_start", "mes_num"] if col in out.columns]
    if helper_cols:
        out = out.drop(columns=helper_cols)
    preferred = [col for col in SALES_BOX_COLS if col in out.columns]
    extra = [col for col in out.columns if col not in preferred]
    return out[preferred + extra].copy()


NON_SOLID_TYPES = {"SURTIDO", "SURTIDO_M", "RAINBOW", "COMBO", "BOUQUET", "BQT", "BULK", "MIX", "ASSORTED"}


def selected_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def selected_label(value, default: str = "todos") -> str:
    values = selected_values(value)
    if not values:
        return default
    if len(values) <= 2:
        return ", ".join(values)
    return f"{len(values)} seleccionados"


BLANK_DISPLAY_VALUES = {"", "nan", "none", "sin_info", "sin caja", "sin tallos", "sin_caja", "sin_ramo", "sin_estructura", "0", "0.0"}


def is_blank_display_value(value) -> bool:
    return str(value).strip().lower() in BLANK_DISPLAY_VALUES


def synced_multi_value(current_value, ordered_values: list[str], select_all_id: str, clear_id: str) -> list[str]:
    trigger_id = ctx.triggered_id
    if trigger_id == clear_id:
        return []
    if trigger_id == select_all_id:
        return ordered_values
    valid = set(ordered_values)
    return [item for item in selected_values(current_value) if item in valid]


def latest_selected_year(years: list[int] | None, frame: pd.DataFrame) -> int | None:
    selected_years = [int(year) for year in selected_values(years) if str(year).strip().isdigit()]
    if selected_years:
        return max(selected_years)
    if frame.empty or "anio" not in frame.columns:
        return None
    available = pd.to_numeric(frame["anio"], errors="coerce").dropna()
    if available.empty:
        return None
    return int(available.max())


def frame_for_option_tallos(frame: pd.DataFrame, years: list[int] | None) -> pd.DataFrame:
    year = latest_selected_year(years, frame)
    if year is None or frame.empty or "anio" not in frame.columns:
        return frame.copy()
    return frame[pd.to_numeric(frame["anio"], errors="coerce").eq(year)].copy()


def tallos_options_from_frame(
    frame: pd.DataFrame,
    value_col: str,
    label_col: str | None = None,
    tallos_col: str = "tallos_confirmados",
) -> tuple[list[dict[str, str]], list[str]]:
    if frame.empty or value_col not in frame.columns or tallos_col not in frame.columns:
        return [], []
    label_col = label_col if label_col and label_col in frame.columns else value_col
    work = frame.copy()
    work["_option_value"] = work[value_col].astype(str)
    work["_option_label"] = work[label_col].astype(str)
    work = work[~work["_option_value"].str.strip().str.lower().isin({"", "nan", "none"})]
    if work.empty:
        return [], []
    grouped = (
        work.groupby("_option_value", as_index=False)
        .agg(label=("_option_label", "first"), tallos=(tallos_col, "sum"))
        .sort_values("tallos", ascending=False)
    )
    options = [
        {"label": f"{row['label']} | {moneyless_number(row['tallos'], 0)} tallos", "value": row["_option_value"]}
        for row in grouped.to_dict("records")
    ]
    return options, grouped["_option_value"].astype(str).tolist()


def normalize_operational_type(series: pd.Series) -> pd.Series:
    return series.fillna("SIN_TIPO").astype(str).str.upper().str.replace("Ã“", "O", regex=False).str.strip()


def ensure_visual_operational_sku(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    tipo = normalize_operational_type(out.get("tipo_pedido_operativo", pd.Series("SIN_TIPO", index=out.index)))
    fallback = out.get("sku_operativo", pd.Series("sin_info", index=out.index)).fillna("sin_info").astype(str)
    solid = out.get("producto_color", out.get("sku_terminado", fallback)).fillna(fallback).astype(str)
    recipe_structure = out.get("receta_programa_tamano_key", out.get("receta_programa_key", out.get("sku_composicion", pd.Series("", index=out.index)))).fillna("").astype(str)
    order_structure = out.get("sku_composicion", recipe_structure).fillna("").astype(str)
    nonsolid = recipe_structure.where(tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]), order_structure)
    receta = out.get("receta_estructura_key", fallback).fillna(fallback).astype(str)
    nonsolid = nonsolid.where(~nonsolid.str.lower().isin(["", "nan", "none", "sin_info"]), receta)
    out["sku_operativo"] = np.where(tipo.eq("SOLIDO"), solid, nonsolid)
    out["tipo_operativo_norm"] = tipo
    out["es_solido"] = tipo.eq("SOLIDO")
    return out


def enrich_visual_with_sku_summary(data: dict[str, pd.DataFrame], frame: pd.DataFrame) -> pd.DataFrame:
    summary = data.get("sku_resumen", pd.DataFrame())
    if frame.empty or summary.empty or "sku_operativo" not in frame.columns or "sku_operativo" not in summary.columns:
        return frame
    join_keys = [col for col in ["cod_cliente", "sku_operativo", "tipo_pedido_operativo"] if col in frame.columns and col in summary.columns]
    if not join_keys:
        return frame
    meta_cols = join_keys + [
        col for col in [
            "producto", "tipo_caja", "tallos_por_ramo", "tallos_programa_caja", "tallos_componentes_caja",
            "ramos_programa_caja_inferidos", "tallos_programa_ramo", "ramos_x_caja", "capuchon", "comida",
            "empaque", "receta", "caja_operativa", "productos_composicion", "colores_composicion",
            "variedades_composicion", "lineas_componentes", "composicion_versiones",
            "composicion_firma_principal", "tallos_promedio_estructura", "ramos_estimados_comercial",
        ] if col in summary.columns and col not in join_keys
    ]
    if len(meta_cols) == len(join_keys):
        return frame
    meta = summary[meta_cols].drop_duplicates(join_keys).copy()
    out = frame.merge(meta, on=join_keys, how="left", suffixes=("", "_sku_meta"))
    fill_pairs = [
        ("producto", "producto_sku_meta"),
        ("tipo_caja", "tipo_caja_sku_meta"),
        ("tallos_x_ramo", "tallos_por_ramo"),
        ("capuchon", "capuchon_sku_meta"),
        ("comida", "comida_sku_meta"),
        ("empaque", "empaque_sku_meta"),
        ("receta", "receta_sku_meta"),
        ("caja_operativa", "caja_operativa_sku_meta"),
    ]
    for target, source in fill_pairs:
        if target in out.columns and source in out.columns:
            mask = out[target].map(is_blank_display_value) & ~out[source].map(is_blank_display_value)
            if mask.any():
                out[target] = out[target].astype("object")
                out.loc[mask, target] = out.loc[mask, source].astype(str)
    drop_cols = [col for col in out.columns if col.endswith("_sku_meta")]
    return out.drop(columns=drop_cols)


def filter_visual_operational_base(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected_code: str | list[str] | None,
    years: list[int] | None,
    week_range: list[int] | None,
    tipo_filter: list[str] | None,
    product_filter: list[str] | str | None,
    color_filter: list[str] | str | None,
    sku_filter: str | list[str] | None,
) -> pd.DataFrame:
    hist = data.get("historico_visualizador_comercial", data.get("historico_confirmado", pd.DataFrame()))
    selected_codes = selected_values(selected_code)
    if hist.empty and selected_codes:
        hist = read_client_sku_week_many_from_sql(selected_codes)
    if hist.empty:
        return pd.DataFrame()
    needed = [
        "fecha", "cod_cliente", "cliente", "pedido", "anio", "anio_iso", "semana_iso", "anio_semana",
        "tipo_pedido_operativo", "producto", "familia_analisis_operativa", "variedad", "color",
        "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque", "caja_operativa",
        "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta", "codempaque", "bulkbouquet",
        "tallos_analisis", "tallos_pedidos", "tallos_historicos", "tallos_confirmados", "ventas_usd", "valor_total_original",
        "pedidos", "cajas",
        "moneda_original", "sku_operativo", "sku_terminado", "sku_composicion", "receta_estructura_key",
        "receta_programa_key", "receta_programa_tamano_key", "producto_color",
    ]
    out = hist[[col for col in needed if col in hist.columns]].copy()
    for text_col in ["variedad", "capuchon", "comida", "empaque", "tipo_caja", "tallos_x_ramo", "caja_operativa"]:
        if text_col not in out.columns:
            out[text_col] = ""
    if "anio" not in out.columns and "anio_iso" in out.columns:
        out["anio"] = out["anio_iso"]
    out = ensure_visual_operational_sku(out)
    if "tallos_pedidos" not in out.columns:
        pedidos_source = out.get("tallos_analisis", out.get("tallos_confirmados", pd.Series(0, index=out.index)))
        out["tallos_pedidos"] = pd.to_numeric(pedidos_source, errors="coerce").fillna(0)
    for col in ["tallos_confirmados", "ventas_usd", "valor_total_original"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    valid_codes = set(filtered["cod_cliente"].astype(str)) if not filtered.empty and "cod_cliente" in filtered.columns else set()
    if selected_codes and "cod_cliente" in out.columns:
        out = out[out["cod_cliente"].astype(str).isin(set(selected_codes))].copy()
    elif valid_codes and "cod_cliente" in out.columns:
        out = out[out["cod_cliente"].astype(str).isin(valid_codes)].copy()
    if years and "anio" in out.columns:
        year_set = {int(year) for year in years if pd.notna(year)}
        out = out[pd.to_numeric(out["anio"], errors="coerce").astype("Int64").isin(year_set)].copy()
    if week_range and len(week_range) == 2 and "semana_iso" in out.columns:
        weeks = pd.to_numeric(out["semana_iso"], errors="coerce")
        out = out[weeks.between(int(week_range[0]), int(week_range[1]))].copy()
    if tipo_filter and "tipo_pedido_operativo" in out.columns:
        valid_tipos = set(normalize_operational_type(pd.Series(tipo_filter)).tolist())
        out = out[out["tipo_operativo_norm"].isin(valid_tipos)].copy()
    products = selected_values(product_filter)
    colors = selected_values(color_filter)
    if products and "producto" in out.columns:
        out = out[out["producto"].astype(str).isin(set(products))].copy()
    if colors and "color" in out.columns:
        out = out[out["color"].astype(str).isin(set(colors))].copy()
    if sku_filter and "sku_operativo" in out.columns:
        sku_values = sku_filter if isinstance(sku_filter, list) else [sku_filter]
        valid_skus = {str(sku) for sku in sku_values if str(sku).strip()}
        if valid_skus:
            out = out[out["sku_operativo"].astype(str).isin(valid_skus)].copy()
    out = enrich_visual_with_sku_summary(data, out)
    return out


def summarize_visual_operational(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = df.groupby(group_cols, dropna=False, as_index=False).agg(
        tallos_confirmados=("tallos_confirmados", "sum"),
        tallos_pedidos=("tallos_pedidos", "sum"),
        ventas_usd=("ventas_usd", "sum"),
        pedidos=("pedido", "nunique") if "pedido" in df.columns else (("pedidos", "sum") if "pedidos" in df.columns else ("sku_operativo", "size")),
        cajas=("caja_operativa", "nunique") if "caja_operativa" in df.columns else (("cajas", "sum") if "cajas" in df.columns else ("sku_operativo", "size")),
        semanas_activas=("anio_semana", "nunique") if "anio_semana" in df.columns else ("sku_operativo", "size"),
    )
    out["precio_usd_tallo"] = (out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)).fillna(0)
    out["cumplimiento"] = (out["tallos_confirmados"] / out["tallos_pedidos"].replace(0, np.nan)).fillna(0).clip(0, 1)
    return out


def top_text(series: pd.Series, n: int = 3) -> str:
    values = series.dropna().astype(str)
    values = values[~values.str.strip().str.lower().isin(BLANK_DISPLAY_VALUES)]
    return ", ".join(values.value_counts().head(n).index)


def _first_non_empty(row: pd.Series, fields: list[str], default: str = "sin_info") -> str:
    for field in fields:
        value = row.get(field, "")
        text = str(value).strip()
        if not is_blank_display_value(text):
            return text
    return default


def _primary_value(value: str) -> str:
    text = str(value).strip()
    if is_blank_display_value(text):
        return "sin_info"
    return text.split(",")[0].split("|")[0].strip()


def _mean_numeric_text(series: pd.Series, decimals: int = 1) -> str:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return ""
    return moneyless_number(float(numeric.mean()), decimals)


def format_integerish_display(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if is_blank_display_value(text):
        return ""
    numeric = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.notna(numeric):
        numeric = float(numeric)
        if abs(numeric - round(numeric)) < 1e-9:
            return str(int(round(numeric)))
        return f"{numeric:g}"
    return text


def compact_label_parts(parts: list[str]) -> str:
    clean_parts = []
    seen = set()
    for part in parts:
        text = str(part).strip()
        key = text.lower()
        if not text or is_blank_display_value(text) or key == "sin_color" or key in seen:
            continue
        seen.add(key)
        clean_parts.append(text)
    return " | ".join(clean_parts)


def operational_sku_label(row: pd.Series, detail: bool = False) -> str:
    tipo = str(
        row.get("tipo_operativo_norm", row.get("tipo_pedido_operativo", "SIN_TIPO"))
    ).upper().replace("Ã“", "O").replace("Ãƒâ€œ", "O").strip()

    producto = _first_non_empty(
        row,
        ["familia_analisis_operativa", "producto_familia", "producto", "productos_composicion"],
        "sin_producto",
    )

    color = _primary_value(
        _first_non_empty(row, ["color", "colores_internos", "colores_composicion"], "")
    )

    tipo_caja = _first_non_empty(row, ["tipo_caja"], "")
    tallos_ramo = format_integerish_display(_first_non_empty(row, ["tallos_x_ramo", "tallos_por_ramo"], ""))
    tallos_programa = format_integerish_display(_first_non_empty(row, ["tallos_programa_ramo"], ""))
    tallos_caja_programa = format_integerish_display(_first_non_empty(row, ["tallos_programa_caja", "tallos_componentes_caja"], ""))
    subtipo = _first_non_empty(
        row,
        ["subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta", "sku_composicion", "receta_estructura_key"],
        "sin_estructura",
    )
    receta_programa = _first_non_empty(row, ["receta", "receta_programa_key", "receta_estructura_key"], "")

    # REGLA LGF:
    # SOLIDO: el color sÃ­ hace parte del SKU visible.
    # NO SOLIDO: surtidos, rainbow, combo, bouquet, bulk, etc. se leen como estructura del pedido.
    if tipo == "SOLIDO":
        parts = [tipo, producto, color]
        if tallos_ramo:
            parts.append(f"{tallos_ramo} tallos/ramo")

        if detail:
            if tipo_caja:
                parts.append(tipo_caja)

            variedad = _first_non_empty(row, ["variedad", "variedades_internas", "variedades_composicion"], "")
            if variedad:
                parts.append(variedad)

            ramos_caja = _first_non_empty(row, ["ramos_x_caja", "ramos_pedidos", "ramos_estimados"], "")
            if ramos_caja:
                parts.append(f"{ramos_caja} ramos/caja")

            caja_id = _first_non_empty(row, ["caja_operativa"], "")
            if caja_id:
                parts.append(f"Caja {caja_id}")

            capuchon = _first_non_empty(row, ["capuchon"], "")
            comida = _first_non_empty(row, ["comida"], "")
            empaque = _first_non_empty(row, ["empaque"], "")

            for extra in [capuchon, comida, empaque]:
                if extra:
                    parts.append(extra)

        return compact_label_parts(parts)

    # Para NO sÃ³lidos se vuelve a la estructura del pedido.
    # AquÃ­ NO se mete color en el SKU visible.
    parts = [tipo, producto]
    if receta_programa:
        parts.append(receta_programa)
    if tipo_caja:
        parts.append(tipo_caja)
    if tallos_ramo:
        parts.append(f"{tallos_ramo} tallos/ramo")
    if tallos_programa and not is_blank_display_value(tallos_programa):
        parts.append(f"{tallos_programa} tallos/ramo")
    if detail and tallos_caja_programa and not is_blank_display_value(tallos_caja_programa):
        parts.append(f"{tallos_caja_programa} tallos/caja")

    if detail:
        parts.append(subtipo)

        variedad = _first_non_empty(row, ["variedad", "variedades_internas", "variedades_composicion"], "")
        if variedad:
            parts.append(variedad)

        ramos_caja = _first_non_empty(row, ["ramos_x_caja", "ramos_pedidos", "ramos_estimados"], "")
        if ramos_caja:
            parts.append(f"{ramos_caja} ramos/caja")

        caja_id = _first_non_empty(row, ["caja_operativa"], "")
        if caja_id:
            parts.append(f"Caja {caja_id}")

        capuchon = _first_non_empty(row, ["capuchon"], "")
        comida = _first_non_empty(row, ["comida"], "")
        empaque = _first_non_empty(row, ["empaque"], "")

        for extra in [capuchon, comida, empaque]:
            if extra:
                parts.append(extra)

    return compact_label_parts(parts)


def operational_sku_filter_label(row: pd.Series) -> str:
    tipo = str(
        row.get("tipo_operativo_norm", row.get("tipo_pedido_operativo", "SIN_TIPO"))
    ).upper().replace("Ã“", "O").replace("Ãƒâ€œ", "O").strip()

    producto = _first_non_empty(
        row,
        ["familia_analisis_operativa", "producto_familia", "producto", "productos_composicion"],
        "",
    )

    color = _primary_value(
        _first_non_empty(row, ["color", "colores_internos", "colores_composicion"], "")
    )

    tipo_caja = _first_non_empty(row, ["tipo_caja"], "")
    tallos_ramo = format_integerish_display(_first_non_empty(row, ["tallos_x_ramo", "tallos_por_ramo"], ""))
    tallos_programa = format_integerish_display(_first_non_empty(row, ["tallos_programa_ramo"], ""))

    # SOLIDO: color sÃ­ identifica el SKU.
    if tipo == "SOLIDO":
        parts = [p for p in [tipo, producto, color] if p and not is_blank_display_value(p) and str(p).lower() != "sin_color"]
        tipo_caja = _first_non_empty(row, ["tipo_caja"], "")
        tallos_ramo = format_integerish_display(_first_non_empty(row, ["tallos_x_ramo", "tallos_por_ramo"], ""))
        if tipo_caja:
            parts.append(tipo_caja)
        if tallos_ramo:
            parts.append(f"{tallos_ramo} tallos/ramo")
        label = compact_label_parts(parts)
        return label if label else _first_non_empty(row, ["sku_operativo"], "sin_sku")

    # NO SOLIDO: se identifica por estructura general, no por color.
    structure = _first_non_empty(row, ["receta", "receta_programa_key", "receta_estructura_key", "sku_composicion"], "")
    parts = [p for p in [tipo, producto, structure or tipo_caja] if p and not is_blank_display_value(p) and str(p).lower() != "sin_color"]
    if tallos_programa and not is_blank_display_value(tallos_programa):
        parts.append(f"{tallos_programa} tallos/ramo")

    if not structure and tallos_ramo and not is_blank_display_value(tallos_ramo):
        parts.append(f"{tallos_ramo} tallos/ramo")

    if structure and tipo_caja:
        parts.append(tipo_caja)
    if structure and tallos_ramo and not is_blank_display_value(tallos_ramo):
        parts.append(f"{tallos_ramo} tallos/ramo")

    label = compact_label_parts(parts)
    return label if label else _first_non_empty(row, ["sku_operativo"], "sin_sku")


def operational_internal_label(row: pd.Series, mode: str = "color") -> str:
    color = _first_non_empty(row, ["color"], "sin_color")
    variedad = _first_non_empty(row, ["variedad"], "sin_variedad")
    if mode == "variedad":
        return variedad
    if mode == "color_variedad":
        return f"{color} | {variedad}" if variedad != "sin_variedad" else color
    return color


def visual_operational_reading(df: pd.DataFrame, selected: pd.Series | None, years: list[int] | None, week_range: list[int] | None) -> str:
    if df.empty:
        return "No hay historia comercial para los filtros seleccionados."
    total_stems = df["tallos_confirmados"].sum()
    total_usd = df["ventas_usd"].sum()
    price = total_usd / total_stems if total_stems else 0
    top_skus = summarize_visual_operational(df, ["sku_operativo"]).sort_values("tallos_confirmados", ascending=False).head(3)["sku_operativo"].astype(str).tolist()
    scope = f"Cliente {selected.get('cod_cliente')}" if selected is not None else f"{moneyless_number(df['cod_cliente'].nunique() if 'cod_cliente' in df.columns else 0)} clientes"
    years_text = ", ".join(map(str, sorted(set(map(int, years or []))))) if years else "todos los anos"
    weeks_text = f"semanas {week_range[0]}-{week_range[1]}" if week_range and len(week_range) == 2 else "todas las semanas"
    has_non_solid = not df[df["tipo_operativo_norm"].ne("SOLIDO")].empty
    note = " En surtidos o recetas, la variedad queda como un detalle adicional del SKU." if has_non_solid else ""
    separated_value_note = ""
    if selected is not None and str(selected.get("cod_cliente", "")).replace(".0", "") == "1070":
        separated_value_note = " Para este cliente, las ventas se registran en lineas separadas de los tallos; el precio promedio corresponde al alcance comercial filtrado."
    return (
        f"{scope} movio {moneyless_number(total_stems)} tallos confirmados en {years_text} y {weeks_text}. "
        f"El precio promedio fue {moneyless_number(price, 4)} USD por tallo. "
        f"Los SKU que mas pesan son {', '.join(top_skus) if top_skus else 'sin SKU dominante'}.{note}{separated_value_note}"
    )


def visual_week_figure(df: pd.DataFrame, metric: str, show_last_year: bool) -> go.Figure:
    title_metric = {
        "tallos_confirmados": "Tallos confirmados",
        "tallos_pedidos": "Tallos pedidos",
        "ventas_usd": "Ventas USD",
        "cajas_ids": "Cajas",
    }.get(metric, "Tallos confirmados")
    if df.empty:
        return empty_figure(f"Evolucion semanal - {title_metric}")
    metric_col = "cajas" if metric == "cajas_ids" else metric
    weekly = summarize_visual_operational(df, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    fig = px.line(
        weekly,
        x="semana_iso",
        y=metric_col if metric_col in weekly.columns else "tallos_confirmados",
        color="anio",
        markers=True,
        hover_data=["tallos_confirmados", "tallos_pedidos", "ventas_usd", "precio_usd_tallo", "pedidos"],
        title=f"Evolucion semanal por ano - {title_metric}" + (" vs ano anterior" if show_last_year else ""),
    )
    fig.update_layout(xaxis_title="Semana", yaxis_title=title_metric, xaxis=dict(dtick=2))
    return apply_common_layout(fig, 430)


def visual_price_figure(df: pd.DataFrame, show_last_year: bool) -> go.Figure:
    if df.empty:
        return empty_figure("Evolucion de precios")
    weekly = summarize_visual_operational(df, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    fig = px.line(
        weekly,
        x="semana_iso",
        y="precio_usd_tallo",
        color="anio",
        markers=True,
        hover_data=["tallos_confirmados", "ventas_usd", "tallos_pedidos", "cumplimiento"],
        title="Evolucion semanal del precio USD/tallo" + (" vs ano anterior" if show_last_year else ""),
    )
    fig.update_layout(xaxis_title="Semana", yaxis_title="USD/tallo", xaxis=dict(dtick=2))
    return apply_common_layout(fig, 360)


def visual_sku_ranking(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = summarize_visual_operational(df, ["sku_operativo", "tipo_pedido_operativo"])
    meta = df.groupby(["sku_operativo", "tipo_pedido_operativo"], dropna=False, as_index=False).agg(
        producto_familia=("producto", lambda s: top_text(s, 2)),
        colores_internos=("color", lambda s: top_text(s, 5)),
        variedades_internas=("variedad", lambda s: top_text(s, 5)),
        capuchon=("capuchon", lambda s: top_text(s, 1)),
        comida=("comida", lambda s: top_text(s, 1)),
        empaque=("empaque", lambda s: top_text(s, 1)),
        tipo_caja=("tipo_caja", lambda s: top_text(s, 1)),
        tallos_x_ramo=("tallos_x_ramo", lambda s: top_text(s, 1)),
        ramos_x_caja=("ramos_pedidos", _mean_numeric_text) if "ramos_pedidos" in df.columns else ("tallos_confirmados", lambda s: ""),
        caja_operativa=("caja_operativa", lambda s: top_text(s, 1)),
    )
    grouped = grouped.merge(meta, on=["sku_operativo", "tipo_pedido_operativo"], how="left")
    total = grouped["tallos_confirmados"].sum()
    grouped["participacion"] = grouped["tallos_confirmados"] / total if total else 0
    grouped["sku_operativo_general"] = grouped.apply(operational_sku_label, axis=1)
    grouped["sku_operativo_detalle"] = grouped.apply(lambda row: operational_sku_label(row, detail=True), axis=1)
    grouped["sku_operativo_visible"] = grouped["sku_operativo_general"]
    grouped["composicion_interna"] = np.where(normalize_operational_type(grouped["tipo_pedido_operativo"]).eq("SOLIDO"), "Color y variedad", "Ver colores y variedades")
    return grouped.sort_values(["tallos_confirmados", "ventas_usd"], ascending=False).head(max(top_n, 15))


def visual_color_composition(df: pd.DataFrame, ranking: pd.DataFrame, selected_sku: str | list[str] | None, color_view: str, analysis_week: int, internal_detail: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    multi_selected = isinstance(selected_sku, list) and len(selected_sku) > 1
    sku = selected_sku[0] if isinstance(selected_sku, list) and len(selected_sku) == 1 else selected_sku
    work = df[df["sku_operativo"].astype(str).eq(str(sku))].copy() if sku else df.copy()
    if color_view == "selected_week" and "semana_iso" in work.columns:
        week_work = work[pd.to_numeric(work["semana_iso"], errors="coerce").eq(int(analysis_week or 1))].copy()
        if not week_work.empty:
            work = week_work
    internal_detail = (internal_detail or "color").strip().lower()
    detail_cols = ["color"]
    if internal_detail in {"color_variedad", "variedad"} and "variedad" in work.columns:
        detail_cols.append("variedad")
    keys = ["sku_operativo"] + detail_cols
    if color_view == "period_average" and "anio_semana" in work.columns:
        weekly = work.groupby(keys + ["anio_semana"], dropna=False, as_index=False).agg(
            tallos_confirmados=("tallos_confirmados", "sum"),
            ventas_usd=("ventas_usd", "sum"),
        )
        out = weekly.groupby(keys, dropna=False, as_index=False).agg(
            tallos_confirmados=("tallos_confirmados", "mean"),
            ventas_usd=("ventas_usd", "mean"),
            semanas=("anio_semana", "nunique"),
        )
    else:
        out = work.groupby(keys, dropna=False, as_index=False).agg(
            tallos_confirmados=("tallos_confirmados", "sum"),
            ventas_usd=("ventas_usd", "sum"),
            semanas=("anio_semana", "nunique") if "anio_semana" in work.columns else ("color", "size"),
        )
    total = out["tallos_confirmados"].sum()
    out["participacion"] = out["tallos_confirmados"] / total if total else 0
    out["precio_usd_tallo"] = (out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)).fillna(0)
    out["color_interno"] = out["color"].astype(str) if "color" in out.columns else "sin_color"
    if "variedad" in out.columns:
        out["variedad_interna"] = out["variedad"].astype(str)
    out["detalle_interno"] = out.apply(lambda row: operational_internal_label(row, internal_detail), axis=1)
    out["alcance_composicion"] = "SKU seleccionado" if sku else ("SKUs seleccionados" if multi_selected else "Total general filtrado")
    return out.sort_values("tallos_confirmados", ascending=False)


def visual_composition_context(selected_sku: str | list[str] | None, ranking: pd.DataFrame) -> tuple[str, str, str | None]:
    values = selected_values(selected_sku)
    if len(values) == 1:
        sku = values[0]
        label = sku
        if not ranking.empty and "sku_operativo" in ranking.columns:
            match = ranking[ranking["sku_operativo"].astype(str).eq(str(sku))]
            if not match.empty:
                label = str(match.iloc[0].get("sku_operativo_visible") or match.iloc[0].get("sku_operativo_general") or sku)
        return f"Composicion de colores del SKU seleccionado: {label}", f"SKU seleccionado: {label}", sku
    if len(values) > 1:
        return "Composicion general de colores", f"{len(values)} SKUs seleccionados; composicion agregada de la seleccion.", None
    return "Composicion general de colores", "Sin SKU seleccionado; composicion agregada de todos los SKUs filtrados.", None


def visual_recent_history(df: pd.DataFrame, analysis_week: int, top_n: int, sku_view_mode: str = "general") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    week = int(analysis_week or pd.to_numeric(work["semana_iso"], errors="coerce").max() or 1)
    week_numbers = pd.to_numeric(work["semana_iso"], errors="coerce")
    recent_week_set = {week, max(1, week - 1)}
    recent = work[week_numbers.isin(recent_week_set)].copy()
    if recent.empty:
        recent = work.copy()
    grouped = recent.groupby(["sku_operativo", "tipo_pedido_operativo", "semana_iso"], dropna=False, as_index=False)["tallos_confirmados"].sum()
    pivot = grouped.pivot_table(index=["sku_operativo", "tipo_pedido_operativo"], columns="semana_iso", values="tallos_confirmados", aggfunc="sum", fill_value=0).reset_index()
    for offset in range(2):
        col = week - offset
        label = "Semana actual" if offset == 0 else f"Semana -{offset}"
        pivot[label] = pivot[col] if col in pivot.columns else 0
    avg = summarize_visual_operational(recent, ["sku_operativo"]).rename(columns={"tallos_confirmados": "promedio_ultimas_2"})
    avg["promedio_ultimas_2"] = avg["promedio_ultimas_2"] / max(recent["anio_semana"].nunique(), 1) if not recent.empty else 0
    total = recent["tallos_confirmados"].sum()
    total_sku = summarize_visual_operational(recent, ["sku_operativo"])[["sku_operativo", "tallos_confirmados", "precio_usd_tallo"]]
    sku_meta = recent.groupby(["sku_operativo"], dropna=False, as_index=False).agg(
        producto=("producto", lambda s: top_text(s, 4)),
        colores_internos=("color", lambda s: top_text(s, 5)),
        capuchon=("capuchon", lambda s: top_text(s, 1)),
        comida=("comida", lambda s: top_text(s, 1)),
        empaque=("empaque", lambda s: top_text(s, 1)),
        tipo_caja=("tipo_caja", lambda s: top_text(s, 1)),
        tallos_x_ramo=("tallos_x_ramo", lambda s: top_text(s, 1)),
        variedad=("variedad", lambda s: top_text(s, 3)),
        ramos_x_caja=("ramos_pedidos", _mean_numeric_text) if "ramos_pedidos" in work.columns else ("tallos_confirmados", lambda s: ""),
        caja_operativa=("caja_operativa", lambda s: top_text(s, 1)),
    )
    out = pivot.merge(avg[["sku_operativo", "promedio_ultimas_2"]], on="sku_operativo", how="left").merge(total_sku, on="sku_operativo", how="left").merge(sku_meta, on="sku_operativo", how="left")
    out["participacion"] = out["tallos_confirmados"] / total if total else 0
    out["variacion_vs_promedio"] = (out["Semana actual"] / out["promedio_ultimas_2"].replace(0, np.nan) - 1).fillna(0)
    out["sku_operativo_general"] = out.apply(lambda row: operational_sku_label(row, detail=False), axis=1)
    out["sku_operativo_detalle"] = out.apply(lambda row: operational_sku_label(row, detail=True), axis=1)
    out["sku_operativo_visible"] = out["sku_operativo_general"] if str(sku_view_mode or "general").lower() != "detalle" else out["sku_operativo_detalle"]
    cols = ["sku_operativo_visible", "sku_operativo_general", "sku_operativo_detalle", "tipo_pedido_operativo", "producto", "variedad", "capuchon", "comida", "empaque", "tipo_caja", "tallos_x_ramo", "ramos_x_caja", "caja_operativa", "Semana actual", "Semana -1", "promedio_ultimas_2", "participacion", "variacion_vs_promedio", "precio_usd_tallo"]
    out = out.sort_values("tallos_confirmados", ascending=False).head(max(top_n, 15))
    return out[[col for col in cols if col in out.columns]]


def format_operational_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    rename = {
        "sku_operativo_visible": "SKU visible",
        "sku_operativo_general": "SKU general",
        "sku_operativo_detalle": "SKU detalle",
        "sku_operativo": "SKU operativo",
        "tipo_pedido_operativo": "Tipo operativo",
        "producto_familia": "Producto/Familia",
        "producto": "Producto/Familia",
        "color_interno": "Color interno",
        "variedad_interna": "Variedad interna",
        "detalle_interno": "Detalle interno",
        "tallos_confirmados": "Tallos confirmados",
        "tallos_pedidos": "Tallos pedidos",
        "ventas_usd": "Ventas USD",
        "participacion": "Participacion %",
        "precio_usd_tallo": "USD/tallo",
        "pedidos": "Pedidos",
        "cajas": "Cajas",
        "semanas_activas": "Semanas activas",
        "cumplimiento": "Cumplimiento",
        "colores_internos": "Colores internos",
        "variedades_internas": "Variedades internas",
        "composicion_interna": "Composicion interna",
        "productos_composicion": "Productos composicion",
        "colores_composicion": "Colores composicion",
        "variedades_composicion": "Variedades composicion",
        "lineas_componentes": "Lineas componentes",
        "composicion_versiones": "Versiones composicion",
        "composicion_firma_principal": "Firma composicion",
        "promedio_ultimas_12": "Promedio ultimas 12 semanas",
        "promedio_ultimas_2": "Promedio ultimas 2 semanas",
        "variacion_vs_promedio": "Variacion vs promedio",
        "capuchon": "Capuchon",
        "comida": "Comida",
        "empaque": "Empaque",
        "tipo_caja": "Tipo caja",
        "tallos_x_ramo": "Tallos/ramo",
        "ramos_x_caja": "Ramos/caja",
        "caja_operativa": "Caja ID",
    }
    out = out.rename(columns={col: label for col, label in rename.items() if col in out.columns})
    for col in ["Tallos confirmados", "Tallos pedidos", "Pedidos", "Cajas", "Semanas activas", "Semana actual", "Semana -1", "Semana -2", "Semana -3", "Promedio ultimas 12 semanas", "Promedio ultimas 2 semanas"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 0))
    for col in ["Ventas USD"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 2))
    for col in ["USD/tallo"]:
        if col in out.columns:
            out[col] = out[col].map(lambda value: moneyless_number(value, 4))
    for col in ["Participacion %", "Cumplimiento", "Variacion vs promedio"]:
        if col in out.columns:
            out[col] = out[col].map(percent)
    return out


def sales_visual_reading(df: pd.DataFrame, selected: pd.Series | None, years: list[int] | None, week_range: list[int] | None) -> str:
    if df.empty:
        return "No hay ventas reales confirmadas para los filtros seleccionados."
    total_stems = df["tallos_confirmados"].sum()
    total_usd = df["ventas_usd"].sum()
    usd_price = total_usd / total_stems if total_stems else 0
    products = (
        df.groupby("producto", dropna=False)["tallos_confirmados"].sum().sort_values(ascending=False).head(3).index.astype(str).tolist()
        if "producto" in df.columns
        else []
    )
    years_text = ", ".join(map(str, sorted(set(map(int, years or []))))) if years else "todos los anios"
    weeks_text = f"semanas {week_range[0]}-{week_range[1]}" if week_range and len(week_range) == 2 else "todas las semanas"
    scope = f"cliente {selected.get('cod_cliente')}" if selected is not None else "todos los clientes"
    return (
        f"Ventas reales confirmadas para {scope}: {moneyless_number(total_stems)} tallos en {years_text}, {weeks_text}. "
        f"Precio promedio USD/tallo {moneyless_number(usd_price, 4)}. "
        f"Productos que mas pesan: {', '.join(products) if products else 'sin producto dominante'}."
    )


def sales_week_comparison_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("Ventas confirmadas por semana y ano")
    weekly = summarize_sales_frame(df, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    fig = px.line(
        weekly,
        x="semana_iso",
        y="tallos_confirmados",
        color="anio",
        markers=True,
        hover_data=["ventas_usd", "precio_usd_tallo", "precio_moneda_original_tallo"],
        title="Tallos confirmados por semana y ano",
    )
    fig.update_layout(xaxis_title="Semana", yaxis_title="Tallos confirmados", xaxis=dict(dtick=2))
    return apply_common_layout(fig, 430)


def sales_price_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("Precio promedio por semana")
    weekly = summarize_sales_frame(df, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    fig = px.line(
        weekly,
        x="semana_iso",
        y="precio_usd_tallo",
        color="anio",
        markers=True,
        hover_data=["tallos_confirmados", "ventas_usd"],
        title="Precio venta USD/tallo por semana",
    )
    fig.update_layout(xaxis_title="Semana", yaxis_title="USD/tallo", xaxis=dict(dtick=2))
    return apply_common_layout(fig, 330)


def filter_general_sales_frame(
    frame: pd.DataFrame,
    years: list[int] | None,
    week_range: list[int] | None,
    clients: list[str] | None,
    products: list[str] | None,
    countries: list[str] | None = None,
    companies: list[str] | None = None,
    colors: list[str] | None = None,
) -> pd.DataFrame:
    """Filter the pre-aggregated weekly sales source used by the fast view."""
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if years and "anio" in out.columns:
        out = out[pd.to_numeric(out["anio"], errors="coerce").isin([int(year) for year in years])].copy()
    if week_range and len(week_range) == 2 and "semana_iso" in out.columns:
        out = out[pd.to_numeric(out["semana_iso"], errors="coerce").between(int(week_range[0]), int(week_range[1]))].copy()
    selected_clients = selected_values(clients)
    if selected_clients and "cod_cliente" in out.columns:
        out = out[out["cod_cliente"].astype(str).isin(selected_clients)].copy()
    selected_countries = selected_values(countries)
    if selected_countries and "pais" in out.columns:
        out = out[out["pais"].astype(str).isin(selected_countries)].copy()
    selected_companies = selected_values(companies)
    if selected_companies and "NomCompania" in out.columns:
        out = out[out["NomCompania"].astype(str).isin(selected_companies)].copy()
    selected_products = selected_values(products)
    if selected_products and "producto" in out.columns:
        out = out[out["producto"].astype(str).isin(selected_products)].copy()
    selected_colors = selected_values(colors)
    if selected_colors and "color" in out.columns:
        out = out[out["color"].astype(str).isin(selected_colors)].copy()
    if "anio_semana" in out.columns and "week_start" not in out.columns and "semana_iso" in out.columns:
        out["week_start"] = pd.to_datetime(
            out["anio"].astype(str) + "-W" + pd.to_numeric(out["semana_iso"], errors="coerce").fillna(1).astype(int).astype(str).str.zfill(2) + "-1",
            format="%G-W%V-%u",
            errors="coerce",
        )
    if "week_start" not in out.columns and {"anio", "semana_iso"}.issubset(out.columns):
        out["week_start"] = pd.to_datetime(
            out["anio"].astype(str) + "-W" + pd.to_numeric(out["semana_iso"], errors="coerce").fillna(1).astype(int).astype(str).str.zfill(2) + "-1",
            format="%G-W%V-%u",
            errors="coerce",
        )
    if "week_start" in out.columns and "mes_num" not in out.columns:
        out["mes_num"] = pd.to_datetime(out["week_start"], errors="coerce").dt.month
    return out


def _month_label(month_num: int) -> str:
    labels = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
    }
    return labels.get(int(month_num), str(month_num))


def build_sales_executive_context(
    view: pd.DataFrame,
    base_year: int | None,
    compare_year: int | None,
) -> dict[str, object]:
    """Build a compact executive comparison for the two selected years."""
    context: dict[str, object] = {
        "ok": False,
        "message": "",
        "base_year": base_year,
        "compare_year": compare_year,
    }
    if view.empty:
        context["message"] = "No hay ventas para construir el informe ejecutivo."
        return context
    years_available = sorted(pd.to_numeric(view["anio"], errors="coerce").dropna().astype(int).unique().tolist())
    if not years_available:
        context["message"] = "No se encontraron anos validos en el alcance seleccionado."
        return context
    if base_year is None:
        base_year = years_available[-2] if len(years_available) >= 2 else years_available[-1]
    if compare_year is None:
        compare_year = years_available[-1]
    if int(base_year) == int(compare_year):
        context["message"] = "Selecciona dos anos diferentes para construir la comparacion ejecutiva."
        return context

    base_frame = view[pd.to_numeric(view["anio"], errors="coerce").eq(int(base_year))].copy()
    compare_frame = view[pd.to_numeric(view["anio"], errors="coerce").eq(int(compare_year))].copy()
    if base_frame.empty or compare_frame.empty:
        context["message"] = "No hay datos suficientes para uno de los anos seleccionados."
        return context

    def aggregate_year(frame: pd.DataFrame) -> dict[str, float]:
        return {
            "ventas_usd": float(frame["ventas_usd"].sum()),
            "tallos_confirmados": float(frame["tallos_confirmados"].sum()),
            "precio_usd_tallo": float(frame["ventas_usd"].sum() / frame["tallos_confirmados"].sum()) if frame["tallos_confirmados"].sum() > 0 else 0.0,
            "pedidos": float(frame["pedidos"].sum()) if "pedidos" in frame.columns else float(len(frame)),
        }

    base_metrics = aggregate_year(base_frame)
    compare_metrics = aggregate_year(compare_frame)
    compare_weeks = max(int(compare_frame["semana_iso"].nunique()), 1) if "semana_iso" in compare_frame.columns else 1
    monthly = pd.concat(
        [
            base_frame.assign(ano_tipo="AÃ±o base"),
            compare_frame.assign(ano_tipo="AÃ±o comparativo"),
        ],
        ignore_index=True,
    )
    monthly["mes_num"] = pd.to_numeric(monthly["mes_num"], errors="coerce").fillna(0).astype(int)
    monthly = summarize_sales_frame(monthly, ["ano_tipo", "mes_num"]).sort_values(["ano_tipo", "mes_num"])
    monthly["Mes"] = monthly["mes_num"].map(_month_label)
    monthly["AÃ±o"] = monthly["ano_tipo"]

    product_summary = pd.concat(
        [
            base_frame.groupby("producto", dropna=False, as_index=False).agg(
                tallos_base=("tallos_confirmados", "sum"),
                ventas_base=("ventas_usd", "sum"),
            ).assign(Ano="AÃ±o base"),
            compare_frame.groupby("producto", dropna=False, as_index=False).agg(
                tallos_compare=("tallos_confirmados", "sum"),
                ventas_compare=("ventas_usd", "sum"),
            ).assign(Ano="AÃ±o comparativo"),
        ],
        ignore_index=True,
        sort=False,
    )
    product_summary["producto"] = product_summary["producto"].astype(str)
    prod_base = base_frame.groupby("producto", as_index=False).agg(
        tallos_base=("tallos_confirmados", "sum"),
        ventas_base=("ventas_usd", "sum"),
    )
    prod_compare = compare_frame.groupby("producto", as_index=False).agg(
        tallos_compare=("tallos_confirmados", "sum"),
        ventas_compare=("ventas_usd", "sum"),
    )
    product_compare = prod_base.merge(prod_compare, on="producto", how="outer").fillna(0)
    product_compare["delta_tallos"] = product_compare["tallos_compare"] - product_compare["tallos_base"]
    product_compare["delta_tallos_pct"] = np.where(
        product_compare["tallos_base"] > 0,
        product_compare["delta_tallos"] / product_compare["tallos_base"],
        np.nan,
    )
    product_compare["delta_usd"] = product_compare["ventas_compare"] - product_compare["ventas_base"]
    product_compare["delta_usd_pct"] = np.where(
        product_compare["ventas_base"] > 0,
        product_compare["delta_usd"] / product_compare["ventas_base"],
        np.nan,
    )
    product_compare["share_compare"] = np.where(
        compare_metrics["tallos_confirmados"] > 0,
        product_compare["tallos_compare"] / compare_metrics["tallos_confirmados"],
        np.nan,
    )
    product_compare = product_compare.sort_values(["ventas_compare", "delta_usd"], ascending=[False, False])

    mix_donut = product_compare.sort_values("tallos_compare", ascending=False).head(8).copy()
    mix_donut["share"] = np.where(
        compare_metrics["tallos_confirmados"] > 0,
        mix_donut["tallos_compare"] / compare_metrics["tallos_confirmados"],
        0,
    )

    monthly_fig = go.Figure()
    if not monthly.empty:
        for year_name in ["AÃ±o base", "AÃ±o comparativo"]:
            subset = monthly[monthly["AÃ±o"].eq(year_name)]
            monthly_fig.add_trace(
                go.Bar(
                    x=subset["Mes"],
                    y=subset["ventas_usd"],
                    name=year_name,
                )
            )
        monthly_fig.update_layout(barmode="group", title="FacturaciÃ³n USD por mes")
        monthly_fig.update_yaxes(title="Ventas USD")
        monthly_fig.update_xaxes(title="Mes")
        apply_common_layout(monthly_fig, 360)
    else:
        monthly_fig = empty_figure("FacturaciÃ³n USD por mes")

    product_bar_fig = go.Figure()
    compare_top = product_compare.head(10).copy()
    if not compare_top.empty:
        product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_base"], name="AÃ±o base"))
        product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_compare"], name="AÃ±o comparativo"))
        product_bar_fig.update_layout(barmode="group", title="Tallos por producto: base vs comparativo")
        product_bar_fig.update_yaxes(title="Tallos confirmados")
        product_bar_fig.update_xaxes(title="Producto")
        apply_common_layout(product_bar_fig, 370)
    else:
        product_bar_fig = empty_figure("Tallos por producto")

    mix_fig = px.pie(
        mix_donut,
        names="producto",
        values="tallos_compare",
        hole=0.42,
        title=f"Mix de tallos del aÃ±o comparativo {compare_year}",
    ) if not mix_donut.empty else empty_figure("Mix por producto")
    if not mix_donut.empty:
        apply_pie_label_style(mix_fig)
        apply_common_layout(mix_fig, 360)

    consolidated_table = pd.DataFrame(
        [
            {"AÃ±o": f"AÃ±o base {base_year}", "Tipo de dato": "Real", "Total USD": base_metrics["ventas_usd"]},
            {"AÃ±o": f"AÃ±o comparativo {compare_year}", "Tipo de dato": "Real", "Total USD": compare_metrics["ventas_usd"]},
            {
                "AÃ±o": f"AÃ±o comparativo {compare_year}",
                "Tipo de dato": "ProyecciÃ³n simple",
                "Total USD": compare_projected_usd,
            },
        ]
    )
    consolidated_card_base = base_metrics["ventas_usd"]
    consolidated_card_compare = compare_projected_usd
    consolidated_delta = consolidated_card_compare - consolidated_card_base
    consolidated_delta_pct = consolidated_delta / consolidated_card_base if consolidated_card_base > 0 else np.nan

    product_leader = mix_donut.iloc[0] if not mix_donut.empty else None
    product_grower = product_compare.sort_values("delta_usd_pct", ascending=False).iloc[0] if not product_compare.empty else None
    product_decliner = product_compare.sort_values("delta_usd_pct", ascending=True).iloc[0] if not product_compare.empty else None
    compare_growth_pct = (compare_projected_usd - consolidated_card_base) / consolidated_card_base if consolidated_card_base > 0 else np.nan
    compare_growth_mult = compare_projected_usd / consolidated_card_base if consolidated_card_base > 0 else np.nan

    insights = []
    if pd.notna(compare_growth_pct):
        insights.append(f"La facturacion total cambia {percent(compare_growth_pct)} frente al ano base.")
    insights.append(
        f"Los tallos totales pasan de {moneyless_number(base_metrics['tallos_confirmados'])} a {moneyless_number(compare_metrics['tallos_confirmados'])} en el alcance filtrado."
    )
    if product_leader is not None:
        insights.append(
            f"El producto lider del mix en el ano comparativo es {product_leader['producto']} con {percent(product_leader['share'])} del total."
        )
    if product_grower is not None:
        insights.append(
            f"El producto con mayor crecimiento en USD es {product_grower['producto']} ({percent(product_grower['delta_usd_pct'])})."
        )
    if product_decliner is not None:
        insights.append(
            f"El producto con mayor caida relevante es {product_decliner['producto']} ({percent(product_decliner['delta_usd_pct'])})."
        )
    if pd.notna(consolidated_delta_pct):
        insights.append(
            f"La proyeccion del aÃ±o comparativo estima una diferencia de {moneyless_number(consolidated_delta, 2)} USD frente al aÃ±o base, equivalente a {percent(consolidated_delta_pct)} y {compare_growth_mult:.2f}x."
        )
    insights = insights[:6]

    context.update(
        {
            "ok": True,
            "message": "",
            "monthly_fig": monthly_fig,
            "monthly_data": monthly,
            "mix_fig": mix_fig,
            "mix_data": mix_donut,
            "product_bar_fig": product_bar_fig,
            "product_compare": product_compare,
            "consolidated_table": consolidated_table,
            "insights": insights,
            "base_metrics": base_metrics,
            "compare_metrics": compare_metrics,
            "compare_projected_usd": compare_projected_usd,
            "compare_projected_tallos": compare_projected_tallos,
            "compare_projected_price": compare_projected_price,
            "consolidated_card_base": consolidated_card_base,
            "consolidated_card_compare": consolidated_card_compare,
            "consolidated_delta": consolidated_delta,
            "consolidated_delta_pct": consolidated_delta_pct,
            "product_leader": product_leader,
            "product_grower": product_grower,
            "product_decliner": product_decliner,
            "compare_growth_mult": compare_growth_mult,
            "months_text": f"{int(monthly['mes_num'].min())}-{int(monthly['mes_num'].max())}" if not monthly.empty else "todas",
            "base_year": int(base_year),
            "compare_year": int(compare_year),
        }
    )
    return context


def build_sales_report_html(context: dict[str, object]) -> str:
    """Build a one-page HTML report suitable for printing or sharing."""
    if not context.get("ok"):
        return f"<html><body><h1>Informe ejecutivo de ventas</h1><p>{context.get('message', 'Sin datos')}</p></body></html>"
    base_year = context["base_year"]
    compare_year = context["compare_year"]
    base_metrics = context["base_metrics"]
    compare_metrics = context["compare_metrics"]
    consolidated_table = context["consolidated_table"].copy()
    consolidated_table["Total USD"] = consolidated_table["Total USD"].map(lambda value: moneyless_number(value, 2))
    product_table = context["product_compare"].copy()
    if not product_table.empty:
        product_table["tallos_base"] = product_table["tallos_base"].map(lambda value: moneyless_number(value, 0))
        product_table["tallos_compare"] = product_table["tallos_compare"].map(lambda value: moneyless_number(value, 0))
        product_table["delta_tallos_pct"] = product_table["delta_tallos_pct"].map(percent)
        product_table["ventas_base"] = product_table["ventas_base"].map(lambda value: moneyless_number(value, 2))
        product_table["ventas_compare"] = product_table["ventas_compare"].map(lambda value: moneyless_number(value, 2))
        product_table["delta_usd_pct"] = product_table["delta_usd_pct"].map(percent)
        product_table["share_compare"] = product_table["share_compare"].map(percent)
        product_table = product_table.head(8)[["producto", "tallos_base", "tallos_compare", "delta_tallos", "delta_tallos_pct", "ventas_base", "ventas_compare", "delta_usd", "delta_usd_pct", "share_compare"]]
        product_table["delta_tallos"] = product_table["delta_tallos"].map(lambda value: moneyless_number(value, 0))
        product_table["delta_usd"] = product_table["delta_usd"].map(lambda value: moneyless_number(value, 2))
    style = """
    <style>
    body { font-family: Arial, sans-serif; color: #17202a; margin: 24px; }
    h1, h2, h3 { margin: 0 0 12px; }
    .meta { color: #667382; margin-bottom: 12px; }
    .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 12px 0 18px; }
    .card { border: 1px solid #dfe5ec; border-left: 4px solid #800020; border-radius: 8px; padding: 10px 12px; background: #fff; }
    .label { font-size: 11px; text-transform: uppercase; color: #667382; font-weight: 700; }
    .value { font-size: 22px; font-weight: 800; }
    .sub { font-size: 12px; color: #667382; }
    .grid2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .panel { border: 1px solid #dfe5ec; border-radius: 8px; padding: 12px; margin-bottom: 14px; }
    table { border-collapse: collapse; width: 100%; font-size: 12px; }
    th, td { border: 1px solid #dfe5ec; padding: 6px 8px; text-align: left; }
    th { background: #f3e8ec; }
    .insights li { margin-bottom: 8px; }
    .page-break { page-break-after: always; }
    </style>
    """
    monthly_html = context["monthly_fig"].to_html(full_html=False, include_plotlyjs="cdn")
    mix_html = context["mix_fig"].to_html(full_html=False, include_plotlyjs=False)
    product_html = context["product_bar_fig"].to_html(full_html=False, include_plotlyjs=False)
    weekly_note = "Incluye lectura semanal detallada al final de la pestaÃ±a en el dashboard."
    return f"""
    <html><head><meta charset="utf-8">{style}</head><body>
    <h1>Informe ejecutivo de Ventas Generales</h1>
    <div class="meta">ComparaciÃ³n: aÃ±o base {base_year} vs aÃ±o comparativo {compare_year}</div>
    <div class="cards">
      <div class="card"><div class="label">FacturaciÃ³n aÃ±o base</div><div class="value">{moneyless_number(base_metrics['ventas_usd'], 2)}</div><div class="sub">USD</div></div>
      <div class="card"><div class="label">FacturaciÃ³n comparativa</div><div class="value">{moneyless_number(context['compare_projected_usd'], 2)}</div><div class="sub">USD proyectados / reales</div></div>
      <div class="card"><div class="label">Diferencia absoluta</div><div class="value">{moneyless_number(context['compare_real_delta'], 2)}</div><div class="sub">USD reales</div></div>
      <div class="card"><div class="label">Crecimiento</div><div class="value">{percent(context['consolidated_delta_pct'])}</div><div class="sub">{context['compare_growth_mult']:.2f}x</div></div>
    </div>
    <div class="grid2">
      <div class="panel"><h3>Resumen de facturaciÃ³n USD</h3>{monthly_html}</div>
      <div class="panel"><h3>Mix por producto</h3>{mix_html}</div>
    </div>
    <div class="grid2">
      <div class="panel"><h3>Tallos por producto</h3>{product_html}</div>
      <div class="panel"><h3>Consolidado y proyecciÃ³n</h3>{consolidated_table.to_html(index=False, escape=False)}</div>
    </div>
    <div class="panel">
      <h2>Insights automÃ¡ticos</h2>
      <ul class="insights">
        {''.join(f'<li>{item}</li>' for item in context['insights'])}
      </ul>
    </div>
    <div class="panel">
      <h2>Lectura semanal complementaria</h2>
      <p>{weekly_note}</p>
    </div>
    </body></html>
    """


def render_ventas_generales_tab(
    data: dict[str, pd.DataFrame],
    years: list[int] | None,
    week_range: list[int] | None,
    clients: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None = None,
) -> html.Div:
    """Present sales totals from the weekly aggregate without recipe-level detail."""
    sales = data.get("ventas_semana", pd.DataFrame())
    if sales.empty:
        return html.Div(
            "No existe ventas_semana_cliente_producto.csv. Ejecuta descriptivos para habilitar Ventas generales.",
            className="table-panel",
        )
    view = filter_general_sales_frame(sales, years, week_range, clients, products, colors=colors)
    if view.empty:
        return html.Div("No hay ventas para los filtros seleccionados.", className="table-panel")

    tallos = float(view["tallos_confirmados"].sum())
    ventas = float(view["ventas_usd"].sum())
    precio = ventas / tallos if tallos > 0 else 0.0
    weekly = summarize_sales_frame(view, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    annual = summarize_sales_frame(view, ["anio"]).sort_values("anio")

    tallos_fig = px.line(
        weekly,
        x="semana_iso",
        y="tallos_confirmados",
        color="anio",
        markers=True,
        title="Tallos confirmados por semana",
    )
    tallos_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="Tallos confirmados")
    apply_common_layout(tallos_fig, 370)

    ventas_fig = px.line(
        weekly,
        x="semana_iso",
        y="ventas_usd",
        color="anio",
        markers=True,
        title="Ventas USD por semana",
    )
    ventas_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="Ventas USD")
    apply_common_layout(ventas_fig, 370)

    precio_fig = px.line(
        weekly,
        x="semana_iso",
        y="precio_usd_tallo",
        color="anio",
        markers=True,
        title="Precio promedio USD/tallo por semana",
    )
    precio_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="USD/tallo")
    apply_common_layout(precio_fig, 345)

    annual_display = annual.rename(columns={
        "anio": "Ano",
        "tallos_confirmados": "Tallos confirmados",
        "ventas_usd": "Ventas USD",
        "precio_usd_tallo": "USD/tallo",
    })[["Ano", "Tallos confirmados", "Ventas USD", "USD/tallo"]].copy()
    annual_display["Tallos confirmados"] = annual_display["Tallos confirmados"].map(moneyless_number)
    annual_display["Ventas USD"] = annual_display["Ventas USD"].map(lambda value: moneyless_number(value, 2))
    annual_display["USD/tallo"] = annual_display["USD/tallo"].map(lambda value: moneyless_number(value, 4))
    weeks_text = f"{int(week_range[0])}-{int(week_range[1])}" if week_range and len(week_range) == 2 else "todas"

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Ventas generales", className="panel-title"),
                    panel_note(
                        "Vista rapida basada en ventas agregadas por semana, cliente y producto. "
                        "Muestra tallos, ventas USD y precio ponderado; para composicion detallada usa Visualizador clientes detallado."
                    ),
                    html.Div(
                        [
                            make_card("Tallos confirmados", moneyless_number(tallos), "periodo filtrado"),
                            make_card("Ventas USD", moneyless_number(ventas, 2), "periodo filtrado"),
                            make_card("Precio promedio", moneyless_number(precio, 4), "USD/tallo ponderado"),
                            make_card("Semanas ISO", weeks_text, "filtro activo"),
                            make_card("Clientes", selected_label(clients, "Todos"), "filtro activo"),
                            make_card("Productos", selected_label(products, "Todos"), "filtro activo"),
                            make_card("Colores", selected_label(colors, "Todos"), "filtro activo"),
                        ],
                        className="metrics-grid",
                    ),
                ],
                className="table-panel",
            ),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=tallos_fig), panel_note("Muestra el volumen confirmado por semana para comparar nivel y estacionalidad entre anos.")], className="panel"),
                    html.Div([dcc.Graph(figure=ventas_fig), panel_note("Muestra la facturacion en USD del mismo alcance; cambia al filtrar cliente o producto.")], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=precio_fig), panel_note("Precio promedio ponderado: ventas USD divididas por tallos confirmados en cada semana.")], className="panel"),
                    html.Div([html.Div("Resumen por ano", className="panel-title"), panel_note("Totales del periodo semanal seleccionado; el precio no es promedio simple, se pondera por tallos."), make_table(annual_display, 8)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
        ]
    )


def build_sales_executive_context_v2(
    view: pd.DataFrame,
    base_year: int | None,
    compare_year: int | None,
) -> dict[str, object]:
    """Build the executive year-over-year context used by Ventas generales."""
    context: dict[str, object] = {"ok": False, "message": "", "base_year": base_year, "compare_year": compare_year}
    if view.empty:
        context["message"] = "No hay ventas para construir el informe ejecutivo."
        return context

    years_available = sorted(pd.to_numeric(view["anio"], errors="coerce").dropna().astype(int).unique().tolist())
    context["years_available"] = years_available
    if not years_available:
        context["message"] = "No se encontraron anos validos en el alcance seleccionado."
        return context
    selected_compare = int(compare_year) if compare_year is not None and int(compare_year) in years_available else years_available[-1]
    selected_base = int(base_year) if base_year is not None and int(base_year) in years_available and int(base_year) != selected_compare else None
    if selected_base is None and len(years_available) >= 2:
        previous_years = [year for year in years_available if year != selected_compare]
        selected_base = previous_years[-1] if previous_years else None
    comparison_mode = selected_base is not None and selected_base != selected_compare

    year_series = pd.to_numeric(view["anio"], errors="coerce")
    base_frame = view[year_series.eq(int(selected_base))].copy() if comparison_mode else view.iloc[0:0].copy()
    compare_frame = view[year_series.eq(int(selected_compare))].copy()
    if compare_frame.empty:
        context["message"] = "No hay datos suficientes para el ano seleccionado."
        return context

    def aggregate(frame: pd.DataFrame) -> dict[str, float]:
        stems = float(frame["tallos_confirmados"].sum())
        usd = float(frame["ventas_usd"].sum())
        return {
            "ventas_usd": usd,
            "tallos_confirmados": stems,
            "precio_usd_tallo": usd / stems if stems > 0 else 0.0,
            "pedidos": float(frame["pedidos"].sum()) if "pedidos" in frame.columns else float(len(frame)),
        }

    base_metrics = aggregate(base_frame)
    compare_metrics = aggregate(compare_frame)
    base_weeks = int(base_frame["semana_iso"].nunique()) if comparison_mode and "semana_iso" in base_frame.columns else 0
    compare_weeks = max(int(compare_frame["semana_iso"].nunique()), 1) if "semana_iso" in compare_frame.columns else 1

    monthly_parts = [compare_frame.assign(ano_label=f"Ano seleccionado {int(selected_compare)}")]
    if comparison_mode:
        monthly_parts.insert(0, base_frame.assign(ano_label=f"Ano base {int(selected_base)}"))
    monthly = pd.concat(monthly_parts, ignore_index=True)
    if "mes_num" in monthly.columns:
        month_source = monthly["mes_num"]
    elif "week_start" in monthly.columns:
        month_source = pd.to_datetime(monthly["week_start"], errors="coerce").dt.month
    else:
        month_source = pd.Series([0] * len(monthly), index=monthly.index)
    monthly["mes_num"] = pd.to_numeric(month_source, errors="coerce").fillna(0).astype(int)
    monthly = summarize_sales_frame(monthly, ["ano_label", "mes_num"]).sort_values(["ano_label", "mes_num"])
    monthly["Mes"] = monthly["mes_num"].map(_month_label)

    prod_base = base_frame.groupby("producto", as_index=False).agg(tallos_base=("tallos_confirmados", "sum"), ventas_base=("ventas_usd", "sum"))
    prod_compare = compare_frame.groupby("producto", as_index=False).agg(tallos_compare=("tallos_confirmados", "sum"), ventas_compare=("ventas_usd", "sum"))
    product_compare = prod_base.merge(prod_compare, on="producto", how="outer").fillna(0)
    product_compare["delta_tallos"] = product_compare["tallos_compare"] - product_compare["tallos_base"]
    product_compare["delta_tallos_pct"] = np.where(product_compare["tallos_base"] > 0, product_compare["delta_tallos"] / product_compare["tallos_base"], np.nan)
    product_compare["delta_usd"] = product_compare["ventas_compare"] - product_compare["ventas_base"]
    product_compare["delta_usd_pct"] = np.where(product_compare["ventas_base"] > 0, product_compare["delta_usd"] / product_compare["ventas_base"], np.nan)
    product_compare["share_compare"] = np.where(compare_metrics["tallos_confirmados"] > 0, product_compare["tallos_compare"] / compare_metrics["tallos_confirmados"], np.nan)
    product_compare = product_compare.sort_values(["ventas_compare", "delta_usd"], ascending=[False, False]).reset_index(drop=True)

    mix_source = product_compare.sort_values("tallos_compare", ascending=False).copy()
    if len(mix_source) > 7:
        others = pd.DataFrame(
            [{"producto": "Otros", "tallos_compare": float(mix_source.iloc[7:]["tallos_compare"].sum()), "ventas_compare": float(mix_source.iloc[7:]["ventas_compare"].sum())}]
        )
        mix_donut = pd.concat([mix_source.head(7)[["producto", "tallos_compare", "ventas_compare"]], others], ignore_index=True)
    else:
        mix_donut = mix_source[["producto", "tallos_compare", "ventas_compare"]].copy()
    mix_donut["share"] = np.where(compare_metrics["tallos_confirmados"] > 0, mix_donut["tallos_compare"] / compare_metrics["tallos_confirmados"], 0)

    monthly_fig = go.Figure()
    month_labels = ([f"Ano base {int(selected_base)}"] if comparison_mode else []) + [f"Ano seleccionado {int(selected_compare)}"]
    for year_label in month_labels:
        subset = monthly[monthly["ano_label"].eq(year_label)]
        monthly_fig.add_trace(go.Bar(x=subset["Mes"], y=subset["ventas_usd"], name=year_label))
    monthly_fig.update_layout(barmode="group", title="Facturacion USD por mes")
    monthly_fig.update_yaxes(title="Ventas USD")
    monthly_fig.update_xaxes(title="Mes")
    apply_common_layout(monthly_fig, 360)
    monthly_fig.update_yaxes(tickformat=",.2f")

    mix_fig = px.pie(mix_donut, names="producto", values="tallos_compare", hole=0.42, title=f"Mix de tallos del ano seleccionado {selected_compare}")
    apply_pie_label_style(mix_fig)
    apply_common_layout(mix_fig, 360)

    compare_top = product_compare.head(10).copy()
    product_bar_fig = go.Figure()
    if comparison_mode:
        product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_base"], name=f"Ano base {selected_base}"))
    product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_compare"], name=f"Ano seleccionado {selected_compare}"))
    product_bar_fig.update_layout(barmode="group", title="Tallos por producto" + (": base vs comparativo" if comparison_mode else ""))
    product_bar_fig.update_yaxes(title="Tallos confirmados")
    product_bar_fig.update_xaxes(title="Producto")
    apply_common_layout(product_bar_fig, 370)
    product_bar_fig.update_yaxes(tickformat=",d")

    product_sales_bar_fig = go.Figure()
    if comparison_mode:
        product_sales_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["ventas_base"], name=f"Ano base {selected_base}"))
    product_sales_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["ventas_compare"], name=f"Ano seleccionado {selected_compare}"))
    product_sales_bar_fig.update_layout(barmode="group", title="Facturacion por producto" + (": base vs comparativo" if comparison_mode else ""))
    product_sales_bar_fig.update_yaxes(title="Ventas USD")
    product_sales_bar_fig.update_xaxes(title="Producto")
    apply_common_layout(product_sales_bar_fig, 370)
    product_sales_bar_fig.update_yaxes(tickformat=",.2f")

    consolidated_rows = []
    if comparison_mode:
        consolidated_rows.append({"Ano": f"Ano base {selected_base}", "Tipo de dato": "Real", "Total USD": base_metrics["ventas_usd"]})
    consolidated_rows.append({"Ano": f"Ano seleccionado {selected_compare}", "Tipo de dato": "Real", "Total USD": compare_metrics["ventas_usd"]})
    consolidated_table = pd.DataFrame(consolidated_rows)
    consolidated_fig = go.Figure()
    consolidated_fig.add_trace(go.Bar(x=consolidated_table["Ano"], y=consolidated_table["Total USD"], marker_color=["#800020", "#4E79A7"][: len(consolidated_table)]))
    consolidated_fig.update_layout(title="Consolidado real USD", showlegend=False)
    consolidated_fig.update_yaxes(title="USD")
    apply_common_layout(consolidated_fig, 330)
    consolidated_fig.update_yaxes(tickformat=",.2f")

    consolidated_delta = compare_metrics["ventas_usd"] - base_metrics["ventas_usd"]
    consolidated_delta_pct = consolidated_delta / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan
    compare_real_delta = compare_metrics["ventas_usd"] - base_metrics["ventas_usd"]
    compare_real_pct = compare_real_delta / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan
    compare_real_mult = compare_metrics["ventas_usd"] / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan
    annual_cards = pd.DataFrame(
        [
            *([{"anio": int(selected_base), **base_metrics}] if comparison_mode else []),
            {"anio": int(selected_compare), **compare_metrics},
        ]
    )

    product_leader = mix_donut.sort_values("share", ascending=False).iloc[0] if not mix_donut.empty else None
    product_grower = product_compare.sort_values("delta_usd_pct", ascending=False).iloc[0] if not product_compare.empty else None
    product_decliner = product_compare.sort_values("delta_usd_pct", ascending=True).iloc[0] if not product_compare.empty else None
    insights = [
        f"La comparacion usa {base_weeks} semanas del ano base y {compare_weeks} semanas del ano comparativo dentro del alcance filtrado."
        if comparison_mode
        else f"Solo hay un ano visible en el filtro: {selected_compare}. Las graficas muestran la tendencia real de ese ano."
    ]
    if pd.notna(consolidated_delta_pct):
        insights.append(f"La facturacion total cambia {percent(consolidated_delta_pct)} frente al ano base.")
    insights.append(f"Los tallos totales pasan de {moneyless_number(base_metrics['tallos_confirmados'])} a {moneyless_number(compare_metrics['tallos_confirmados'])} en el alcance filtrado.")
    if product_leader is not None:
        insights.append(f"El producto lider del mix en el ano comparativo es {product_leader['producto']} con {percent(product_leader['share'])} del total.")
    if product_grower is not None:
        insights.append(f"El producto con mayor crecimiento en USD es {product_grower['producto']} ({percent(product_grower['delta_usd_pct'])}).")
    if product_decliner is not None:
        insights.append(f"El producto con mayor caida relevante es {product_decliner['producto']} ({percent(product_decliner['delta_usd_pct'])}).")
    insights = insights[:6]

    context.update(
        {
            "ok": True,
            "message": "",
            "monthly_fig": monthly_fig,
            "monthly_data": monthly,
            "mix_fig": mix_fig,
            "mix_data": mix_donut,
            "product_bar_fig": product_bar_fig,
            "product_sales_bar_fig": product_sales_bar_fig,
            "consolidated_fig": consolidated_fig,
            "consolidated_table": consolidated_table,
            "product_compare": product_compare,
            "annual_cards": annual_cards,
            "base_metrics": base_metrics,
            "compare_metrics": compare_metrics,
            "consolidated_delta": consolidated_delta,
            "consolidated_delta_pct": consolidated_delta_pct,
            "compare_real_delta": compare_real_delta,
            "compare_real_pct": compare_real_pct,
            "compare_real_mult": compare_real_mult,
            "insights": insights,
            "base_year": int(selected_base) if comparison_mode else None,
            "compare_year": int(selected_compare),
            "comparison_mode": comparison_mode,
            "week_text": f"{int(view['semana_iso'].min())}-{int(view['semana_iso'].max())}" if "semana_iso" in view.columns else "todas",
        }
    )
    return context


def sales_metric_comparison_display(context: dict[str, object]) -> pd.DataFrame:
    if not context.get("ok"):
        return pd.DataFrame()
    base = context["base_metrics"]
    compare = context["compare_metrics"]
    rows = []
    specs = [
        ("Ventas USD", "ventas_usd", lambda value: moneyless_number(value, 2), lambda value: moneyless_number(value, 2)),
        ("Tallos confirmados", "tallos_confirmados", lambda value: moneyless_number(value), lambda value: moneyless_number(value)),
        ("Precio USD/tallo", "precio_usd_tallo", lambda value: moneyless_number(value, 4), lambda value: moneyless_number(value, 4)),
        ("Pedidos", "pedidos", lambda value: moneyless_number(value), lambda value: moneyless_number(value)),
    ]
    if not context.get("comparison_mode", True):
        return pd.DataFrame(
            [
                {
                    "Metrica": label,
                    f"Ano seleccionado {context['compare_year']}": formatter(float(compare.get(key, 0) or 0)),
                }
                for label, key, formatter, _ in specs
            ]
        )
    for label, key, formatter, delta_formatter in specs:
        base_value = float(base.get(key, 0) or 0)
        compare_value = float(compare.get(key, 0) or 0)
        delta = compare_value - base_value
        delta_pct = delta / base_value if base_value > 0 else np.nan
        rows.append(
            {
                "Metrica": label,
                f"Ano base {context['base_year']}": formatter(base_value),
                f"Ano comparativo {context['compare_year']}": formatter(compare_value),
                "Diferencia": delta_formatter(delta),
                "Variacion %": percent(delta_pct),
            }
        )
    return pd.DataFrame(rows)


def product_comparison_display(product_compare: pd.DataFrame, base_year: int, compare_year: int, rows: int = 18) -> pd.DataFrame:
    if product_compare.empty:
        return pd.DataFrame()
    if int(base_year) == int(compare_year):
        out = product_compare.head(rows).copy()
        out = out.rename(
            columns={
                "producto": "Producto",
                "ventas_compare": f"USD {compare_year}",
                "tallos_compare": f"Tallos {compare_year}",
                "share_compare": f"Share tallos {compare_year}",
            }
        )
        cols = ["Producto", f"USD {compare_year}", f"Tallos {compare_year}", f"Share tallos {compare_year}"]
        out = out[[col for col in cols if col in out.columns]]
        if f"USD {compare_year}" in out.columns:
            out[f"USD {compare_year}"] = pd.to_numeric(out[f"USD {compare_year}"], errors="coerce").map(lambda value: moneyless_number(value, 2))
        if f"Tallos {compare_year}" in out.columns:
            out[f"Tallos {compare_year}"] = pd.to_numeric(out[f"Tallos {compare_year}"], errors="coerce").map(lambda value: moneyless_number(value, 0))
        if f"Share tallos {compare_year}" in out.columns:
            out[f"Share tallos {compare_year}"] = pd.to_numeric(out[f"Share tallos {compare_year}"], errors="coerce").map(percent)
        return out
    out = product_compare.head(rows).copy()
    out = out.rename(
        columns={
            "producto": "Producto",
            "ventas_base": f"USD {base_year}",
            "ventas_compare": f"USD {compare_year}",
            "delta_usd": "Dif. USD",
            "delta_usd_pct": "Var. USD %",
            "tallos_base": f"Tallos {base_year}",
            "tallos_compare": f"Tallos {compare_year}",
            "delta_tallos": "Dif. tallos",
            "delta_tallos_pct": "Var. tallos %",
            "share_compare": f"Share tallos {compare_year}",
        }
    )
    cols = [
        "Producto",
        f"USD {base_year}",
        f"USD {compare_year}",
        "Dif. USD",
        "Var. USD %",
        f"Tallos {base_year}",
        f"Tallos {compare_year}",
        "Dif. tallos",
        "Var. tallos %",
        f"Share tallos {compare_year}",
    ]
    out = out[[col for col in cols if col in out.columns]]
    for col in [f"USD {base_year}", f"USD {compare_year}", "Dif. USD"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 2))
    for col in [f"Tallos {base_year}", f"Tallos {compare_year}", "Dif. tallos"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 0))
    for col in ["Var. USD %", "Var. tallos %", f"Share tallos {compare_year}"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(percent)
    return out


def client_sales_display(view: pd.DataFrame, rows: int = 30, ascending: bool = True) -> pd.DataFrame:
    if view.empty or "cod_cliente" not in view.columns:
        return pd.DataFrame()
    company_col = "NomCompania" if "NomCompania" in view.columns else ("cliente" if "cliente" in view.columns else None)
    group_cols = ["cod_cliente"] + ([company_col] if company_col else [])
    out = (
        view.groupby(group_cols, dropna=False, as_index=False)
        .agg(
            ventas_usd=("ventas_usd", "sum"),
            tallos_confirmados=("tallos_confirmados", "sum"),
            pedidos=("pedidos", "sum") if "pedidos" in view.columns else ("ventas_usd", "size"),
        )
        .sort_values(["ventas_usd", "tallos_confirmados"], ascending=[ascending, ascending])
        .head(rows)
    )
    out["precio_usd_tallo"] = (out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)).fillna(0)
    out = out.rename(
        columns={
            "cod_cliente": "Cod. cliente",
            "cliente": "Cliente",
            "NomCompania": "Compania",
            "ventas_usd": "Facturacion USD",
            "tallos_confirmados": "Tallos",
            "precio_usd_tallo": "Precio USD/tallo",
            "pedidos": "Pedidos",
        }
    )
    for col in ["Facturacion USD"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 2))
    for col in ["Tallos", "Pedidos"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 0))
    if "Precio USD/tallo" in out.columns:
        out["Precio USD/tallo"] = pd.to_numeric(out["Precio USD/tallo"], errors="coerce").map(lambda value: moneyless_number(value, 4))
    cols = ["Cod. cliente", "Compania", "Cliente", "Facturacion USD", "Tallos", "Precio USD/tallo", "Pedidos"]
    return out[[col for col in cols if col in out.columns]]


def growth_by_dimension_display(
    view: pd.DataFrame,
    base_year: int,
    compare_year: int,
    group_cols: list[str],
    label_cols: list[str],
    rows: int = 30,
) -> pd.DataFrame:
    if view.empty or not group_cols or any(col not in view.columns for col in group_cols):
        return pd.DataFrame()
    work = view[pd.to_numeric(view["anio"], errors="coerce").isin([int(base_year), int(compare_year)])].copy()
    if work.empty:
        return pd.DataFrame()
    grouped = work.groupby(["anio"] + group_cols, dropna=False, as_index=False).agg(
        ventas_usd=("ventas_usd", "sum"),
        tallos_confirmados=("tallos_confirmados", "sum"),
    )
    base = grouped[pd.to_numeric(grouped["anio"], errors="coerce").eq(int(base_year))].drop(columns=["anio"])
    comp = grouped[pd.to_numeric(grouped["anio"], errors="coerce").eq(int(compare_year))].drop(columns=["anio"])
    merged = base.merge(comp, on=group_cols, how="outer", suffixes=("_base", "_compare")).fillna(0)
    merged["delta_usd"] = merged["ventas_usd_compare"] - merged["ventas_usd_base"]
    merged["delta_usd_pct"] = np.where(merged["ventas_usd_base"] > 0, merged["delta_usd"] / merged["ventas_usd_base"], np.nan)
    merged["delta_tallos"] = merged["tallos_confirmados_compare"] - merged["tallos_confirmados_base"]
    merged["delta_tallos_pct"] = np.where(merged["tallos_confirmados_base"] > 0, merged["delta_tallos"] / merged["tallos_confirmados_base"], np.nan)
    merged["precio_compare"] = (merged["ventas_usd_compare"] / merged["tallos_confirmados_compare"].replace(0, np.nan)).fillna(0)
    merged = merged.sort_values(["ventas_usd_compare", "delta_usd"], ascending=[False, False]).head(rows)
    rename = {
        "pais": "Pais",
        "cod_cliente": "Cod. cliente",
        "cliente": "Cliente",
        "NomCompania": "Compania",
        "ventas_usd_base": f"USD {base_year}",
        "ventas_usd_compare": f"USD {compare_year}",
        "delta_usd": "Crecimiento USD",
        "delta_usd_pct": "Crecimiento %",
        "tallos_confirmados_base": f"Tallos {base_year}",
        "tallos_confirmados_compare": f"Tallos {compare_year}",
        "delta_tallos": "Crecimiento tallos",
        "delta_tallos_pct": "Crec. tallos %",
        "precio_compare": f"Precio {compare_year}",
    }
    out = merged.rename(columns=rename)
    cols = [rename.get(col, col) for col in label_cols] + [
        f"USD {base_year}",
        f"USD {compare_year}",
        "Crecimiento USD",
        "Crecimiento %",
        f"Tallos {base_year}",
        f"Tallos {compare_year}",
        "Crecimiento tallos",
        "Crec. tallos %",
        f"Precio {compare_year}",
    ]
    out = out[[col for col in cols if col in out.columns]]
    for col in [f"USD {base_year}", f"USD {compare_year}", "Crecimiento USD"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 2))
    for col in [f"Tallos {base_year}", f"Tallos {compare_year}", "Crecimiento tallos"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 0))
    for col in ["Crecimiento %", "Crec. tallos %"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(percent)
    if f"Precio {compare_year}" in out.columns:
        out[f"Precio {compare_year}"] = pd.to_numeric(out[f"Precio {compare_year}"], errors="coerce").map(lambda value: moneyless_number(value, 4))
    return out


def tallos_movers_display(
    view: pd.DataFrame,
    base_year: int,
    compare_year: int,
    group_cols: list[str],
    label_cols: list[str],
    rows: int = 10,
    direction: str = "up",
) -> pd.DataFrame:
    if view.empty or not group_cols or any(col not in view.columns for col in group_cols):
        return pd.DataFrame()
    work = view[pd.to_numeric(view["anio"], errors="coerce").isin([int(base_year), int(compare_year)])].copy()
    if work.empty:
        return pd.DataFrame()
    grouped = work.groupby(["anio"] + group_cols, dropna=False, as_index=False).agg(
        tallos_confirmados=("tallos_confirmados", "sum"),
        ventas_usd=("ventas_usd", "sum"),
    )
    base = grouped[pd.to_numeric(grouped["anio"], errors="coerce").eq(int(base_year))].drop(columns=["anio"])
    comp = grouped[pd.to_numeric(grouped["anio"], errors="coerce").eq(int(compare_year))].drop(columns=["anio"])
    merged = base.merge(comp, on=group_cols, how="outer", suffixes=("_base", "_compare")).fillna(0)
    merged["delta_tallos"] = merged["tallos_confirmados_compare"] - merged["tallos_confirmados_base"]
    merged["delta_tallos_pct"] = np.where(
        merged["tallos_confirmados_base"] > 0,
        merged["delta_tallos"] / merged["tallos_confirmados_base"],
        np.nan,
    )
    merged["delta_ventas_usd"] = merged["ventas_usd_compare"] - merged["ventas_usd_base"]
    ascending = str(direction).lower() == "down"
    ranked = merged.sort_values(["delta_tallos", "tallos_confirmados_compare"], ascending=[ascending, False]).head(rows)
    rename = {
        "producto": "Producto",
        "cod_cliente": "Cod. cliente",
        "cliente": "Cliente",
        "NomCompania": "Compania",
        "pais": "Pais",
        "tallos_confirmados_base": f"Tallos {base_year}",
        "tallos_confirmados_compare": f"Tallos {compare_year}",
        "delta_tallos": "Dif. tallos",
        "delta_tallos_pct": "Var. tallos %",
        "ventas_usd_compare": f"Ventas USD {compare_year}",
        "delta_ventas_usd": "Dif. ventas USD",
    }
    out = ranked.rename(columns=rename)
    cols = [rename.get(col, col) for col in label_cols] + [
        f"Tallos {base_year}",
        f"Tallos {compare_year}",
        "Dif. tallos",
        "Var. tallos %",
        f"Ventas USD {compare_year}",
        "Dif. ventas USD",
    ]
    out = out[[col for col in cols if col in out.columns]]
    for col in [f"Tallos {base_year}", f"Tallos {compare_year}", "Dif. tallos"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 0))
    for col in [f"Ventas USD {compare_year}", "Dif. ventas USD"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(lambda value: moneyless_number(value, 2))
    if "Var. tallos %" in out.columns:
        out["Var. tallos %"] = pd.to_numeric(out["Var. tallos %"], errors="coerce").map(percent)
    return out


def sales_scope_summary(
    view: pd.DataFrame,
    clients: list[str] | None,
    products: list[str] | None,
    countries: list[str] | None = None,
    companies: list[str] | None = None,
    colors: list[str] | None = None,
) -> dict[str, str]:
    client_count = view["cod_cliente"].nunique() if "cod_cliente" in view.columns else 0
    product_count = view["producto"].nunique() if "producto" in view.columns else 0
    color_count = view["color"].nunique() if "color" in view.columns else 0
    company_count = view["NomCompania"].nunique() if "NomCompania" in view.columns else 0
    selected_clients = selected_values(clients)
    selected_products = selected_values(products)
    selected_countries = selected_values(countries)
    selected_companies = selected_values(companies)
    selected_colors = selected_values(colors)
    if selected_clients and {"cod_cliente", "cliente"}.issubset(view.columns):
        names = (
            view[["cod_cliente", "cliente"]]
            .drop_duplicates()
            .sort_values(["cliente", "cod_cliente"])
            .head(4)
            .apply(lambda row: f"{row['cliente']} | {row['cod_cliente']}", axis=1)
            .tolist()
        )
        client_label = ", ".join(names)
        if len(selected_clients) > 4:
            client_label += f" + {len(selected_clients) - 4} mas"
    else:
        client_label = f"Todos los clientes visibles ({moneyless_number(client_count)})"
    product_label = selected_label(selected_products, f"Todos los productos visibles ({moneyless_number(product_count)})")
    color_label = selected_label(selected_colors, f"Todos los colores visibles ({moneyless_number(color_count)})")
    country_count = view["pais"].nunique() if "pais" in view.columns else 0
    country_label = selected_label(selected_countries, f"Todos los paises visibles ({moneyless_number(country_count)})")
    company_label = selected_label(selected_companies, f"Todas las companias visibles ({moneyless_number(company_count)})")
    return {
        "clientes": client_label,
        "companias": company_label,
        "productos": product_label,
        "colores": color_label,
        "paises": country_label,
        "clientes_count": moneyless_number(client_count),
        "companias_count": moneyless_number(company_count),
        "productos_count": moneyless_number(product_count),
        "colores_count": moneyless_number(color_count),
        "paises_count": moneyless_number(country_count),
    }


def _pdf_escape(text: object) -> str:
    clean = re.sub(r"\s+", " ", str(text)).strip()
    clean = clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return clean


def _pdf_text(content: list[str], x: int, y: int, text: object, size: int = 10, color: tuple[float, float, float] = (0.09, 0.13, 0.18), font: str = "F1") -> None:
    r, g, b = color
    content.append(f"{r:.3f} {g:.3f} {b:.3f} rg BT /{font} {size} Tf {x} {y} Td ({_pdf_escape(text)}) Tj ET")


def _pdf_rect(content: list[str], x: int, y: int, w: int, h: int, color: tuple[float, float, float]) -> None:
    r, g, b = color
    content.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x} {y} {w} {h} re f")


def _pdf_stroked_rect(
    content: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    fill: tuple[float, float, float],
    stroke: tuple[float, float, float] = (0.86, 0.89, 0.93),
    width: float = 0.8,
) -> None:
    fr, fg, fb = fill
    sr, sg, sb = stroke
    content.append(f"{width:.2f} w {fr:.3f} {fg:.3f} {fb:.3f} rg {sr:.3f} {sg:.3f} {sb:.3f} RG {x} {y} {w} {h} re B")


def _pdf_logo_image(path: Path | None = None) -> tuple[bytes, int, int, str] | None:
    path = path or resolve_logo_path()
    if path is None:
        return None
    if not path.exists():
        return None
    try:
        from PIL import Image

        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail((220, 90))
            header_bg = Image.new("RGBA", img.size, (128, 0, 32, 255))
            header_bg.alpha_composite(img)
            rgb = header_bg.convert("RGB")
            return zlib.compress(rgb.tobytes()), rgb.width, rgb.height, "FlateDecode"
    except Exception:
        return None


def _pdf_logo(content: list[str], x: int, y: int, w: int, h: int) -> None:
    content.append(f"q {w} 0 0 {h} {x} {y} cm /Logo Do Q")


def _pdf_line(content: list[str], x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float], width: float = 1.0) -> None:
    r, g, b = color
    content.append(f"{width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")


def _pdf_polygon(content: list[str], points: list[tuple[float, float]], color: tuple[float, float, float]) -> None:
    if not points:
        return
    r, g, b = color
    first = points[0]
    rest = " ".join(f"{px:.1f} {py:.1f} l" for px, py in points[1:])
    content.append(f"{r:.3f} {g:.3f} {b:.3f} rg {first[0]:.1f} {first[1]:.1f} m {rest} h f")


def _pdf_short_number(value: float) -> str:
    value = float(value or 0)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}{value / 1_000:.0f}K"
    if value >= 10:
        return f"{sign}{value:.0f}"
    return f"{sign}{value:.2f}"


def _pdf_panel(content: list[str], x: int, y: int, w: int, h: int, title: str, note: str = "") -> None:
    _pdf_stroked_rect(content, x, y, w, h, (1, 1, 1), (0.86, 0.89, 0.93), 0.9)
    _pdf_rect(content, x, y + h - 5, w, 5, (0.50, 0.00, 0.13))
    _pdf_text(content, x + 12, y + h - 22, title, 11, (0.09, 0.13, 0.18), "F2")
    if note:
        _pdf_text(content, x + 12, y + h - 36, note[:88], 7, (0.38, 0.43, 0.49))


def _pdf_table(
    content: list[str],
    x: int,
    y: int,
    w: int,
    headers: list[str],
    rows: list[dict[str, object]],
    widths: list[int],
    row_h: int = 15,
    font_size: int = 7,
) -> int:
    _pdf_rect(content, x, y - 3, w, row_h + 4, (0.94, 0.91, 0.92))
    cx = x
    for header, width in zip(headers, widths):
        _pdf_text(content, cx + 4, y + 1, header[:18], font_size, (0.09, 0.13, 0.18), "F2")
        cx += width
    y -= row_h
    for idx, row in enumerate(rows):
        if idx % 2 == 0:
            _pdf_rect(content, x, y - 3, w, row_h, (0.98, 0.99, 1.00))
        cx = x
        for header, width in zip(headers, widths):
            _pdf_text(content, cx + 4, y, str(row.get(header, ""))[: max(8, int(width / 5))], font_size, (0.18, 0.22, 0.28))
            cx += width
        y -= row_h
    _pdf_line(content, x, y + row_h - 2, x + w, y + row_h - 2, (0.86, 0.89, 0.93), 0.6)
    return y


def _pdf_comparison_cards(content: list[str], x: int, y: int, cards: list[dict[str, object]], base_year: int, compare_year: int) -> None:
    card_w = 124
    card_h = 78
    gap = 8
    for idx, card in enumerate(cards):
        cx = x + idx * (card_w + gap)
        delta = card.get("delta_pct")
        positive = pd.notna(delta) and float(delta) >= 0
        accent = (0.00, 0.53, 0.33) if positive else (0.73, 0.13, 0.16)
        if delta is None or pd.isna(delta):
            accent = (0.46, 0.50, 0.56)
            delta_text = "sin base"
        else:
            delta_text = f"{float(delta):+.1%}"
        _pdf_stroked_rect(content, cx, y - card_h, card_w, card_h, (0.97, 0.98, 0.99), (0.86, 0.89, 0.93), 0.8)
        _pdf_rect(content, cx, y - 5, card_w, 5, (0.50, 0.00, 0.13))
        _pdf_text(content, cx + 10, y - 20, str(card["title"]), 8, (0.38, 0.43, 0.49), "F2")
        _pdf_text(content, cx + 10, y - 36, f"{base_year}: {card['base']}", 8, (0.18, 0.22, 0.28))
        _pdf_text(content, cx + 10, y - 51, f"{compare_year}: {card['compare']}", 8, (0.09, 0.13, 0.18), "F2")
        _pdf_rect(content, cx + 10, y - 70, 46, 13, accent)
        _pdf_text(content, cx + 15, y - 67, delta_text, 7, (1, 1, 1), "F2")


def _pdf_bar_chart(
    content: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    labels: list[str],
    base_values: list[float],
    compare_values: list[float],
    title: str,
    base_year: int,
    compare_year: int,
    x_title: str = "",
    y_title: str = "",
) -> None:
    _pdf_panel(content, x, y, w, h, title)
    plot_x = x + 46
    plot_y = y + 32
    plot_w = w - 62
    plot_h = h - 76
    max_value = max(base_values + compare_values + [1])
    tick_max = max_value * 1.12
    for tick_idx in range(5):
        value = tick_max * tick_idx / 4
        ty = plot_y + plot_h * tick_idx / 4
        _pdf_line(content, plot_x, ty, plot_x + plot_w, ty, (0.91, 0.93, 0.95), 0.45)
        _pdf_text(content, x + 8, int(ty - 3), _pdf_short_number(value), 6, (0.38, 0.43, 0.49))
    _pdf_line(content, plot_x, plot_y, plot_x + plot_w, plot_y, (0.74, 0.78, 0.83), 0.8)
    _pdf_line(content, plot_x, plot_y, plot_x, plot_y + plot_h, (0.74, 0.78, 0.83), 0.8)
    if y_title:
        _pdf_text(content, plot_x, y + h - 49, y_title, 7, (0.38, 0.43, 0.49), "F2")
    if x_title:
        _pdf_text(content, plot_x + int(plot_w / 2) - 18, y + 11, x_title, 7, (0.38, 0.43, 0.49), "F2")
    group_w = plot_w / max(len(labels), 1)
    bar_w = min(14, max(5, group_w / 5))
    for idx, label in enumerate(labels):
        gx = plot_x + idx * group_w + group_w * 0.30
        bh = (base_values[idx] / tick_max) * plot_h
        ch = (compare_values[idx] / tick_max) * plot_h
        _pdf_rect(content, int(gx), int(plot_y), int(bar_w), int(bh), (0.50, 0.00, 0.13))
        _pdf_rect(content, int(gx + bar_w + 4), int(plot_y), int(bar_w), int(ch), (0.31, 0.47, 0.65))
        _pdf_text(content, int(plot_x + idx * group_w + 2), y + 20, label[:10], 6, (0.38, 0.43, 0.49))
    legend_y = y + h - 36
    _pdf_rect(content, x + w - 104, legend_y, 8, 8, (0.50, 0.00, 0.13))
    _pdf_text(content, x + w - 92, legend_y, str(base_year), 7, (0.38, 0.43, 0.49))
    _pdf_rect(content, x + w - 54, legend_y, 8, 8, (0.31, 0.47, 0.65))
    _pdf_text(content, x + w - 42, legend_y, str(compare_year), 7, (0.38, 0.43, 0.49))


def _pdf_line_chart(
    content: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    weekly: pd.DataFrame,
    metric: str,
    title: str,
    base_year: int,
    compare_year: int,
    x_title: str = "Semana ISO",
    y_title: str = "",
) -> None:
    _pdf_panel(content, x, y, w, h, title)
    plot_x = x + 46
    plot_y = y + 32
    plot_w = w - 62
    plot_h = h - 76
    frame = weekly[pd.to_numeric(weekly["anio"], errors="coerce").isin([base_year, compare_year])].copy() if not weekly.empty else pd.DataFrame()
    if frame.empty or metric not in frame.columns:
        _pdf_text(content, x + 20, y + h / 2, "Sin datos para la grafica", 8, (0.38, 0.43, 0.49))
        return
    max_value = max(float(frame[metric].max()), 1.0) * 1.12
    min_week = max(int(pd.to_numeric(frame["semana_iso"], errors="coerce").min()), 1)
    max_week = max(int(pd.to_numeric(frame["semana_iso"], errors="coerce").max()), min_week + 1)
    for tick_idx in range(5):
        value = max_value * tick_idx / 4
        ty = plot_y + plot_h * tick_idx / 4
        _pdf_line(content, plot_x, ty, plot_x + plot_w, ty, (0.91, 0.93, 0.95), 0.45)
        _pdf_text(content, x + 8, int(ty - 3), _pdf_short_number(value), 6, (0.38, 0.43, 0.49))
    _pdf_line(content, plot_x, plot_y, plot_x + plot_w, plot_y, (0.74, 0.78, 0.83), 0.8)
    _pdf_line(content, plot_x, plot_y, plot_x, plot_y + plot_h, (0.74, 0.78, 0.83), 0.8)
    if y_title:
        _pdf_text(content, plot_x, y + h - 49, y_title, 7, (0.38, 0.43, 0.49), "F2")
    _pdf_text(content, plot_x + int(plot_w / 2) - 18, y + 11, x_title, 7, (0.38, 0.43, 0.49), "F2")
    for tick_idx in range(5):
        week = int(round(min_week + (max_week - min_week) * tick_idx / 4))
        tx = plot_x + plot_w * tick_idx / 4
        _pdf_line(content, tx, plot_y, tx, plot_y - 3, (0.74, 0.78, 0.83), 0.6)
        _pdf_text(content, int(tx - 5), y + 21, str(week), 6, (0.38, 0.43, 0.49))
    colors = {base_year: (0.50, 0.00, 0.13), compare_year: (0.31, 0.47, 0.65)}
    for year in [base_year, compare_year]:
        subset = frame[pd.to_numeric(frame["anio"], errors="coerce").eq(year)].sort_values("semana_iso")
        points = []
        for row in subset.itertuples(index=False):
            week = int(getattr(row, "semana_iso"))
            value = float(getattr(row, metric))
            px_x = plot_x + ((week - min_week) / max(max_week - min_week, 1)) * plot_w
            px_y = plot_y + (value / max_value) * plot_h
            points.append((px_x, px_y))
        for left, right in zip(points, points[1:]):
            _pdf_line(content, left[0], left[1], right[0], right[1], colors[year], 1.6)
    legend_y = y + h - 36
    _pdf_rect(content, x + w - 104, legend_y, 8, 8, colors[base_year])
    _pdf_text(content, x + w - 92, legend_y, str(base_year), 7, (0.38, 0.43, 0.49))
    _pdf_rect(content, x + w - 54, legend_y, 8, 8, colors[compare_year])
    _pdf_text(content, x + w - 42, legend_y, str(compare_year), 7, (0.38, 0.43, 0.49))


def _pdf_monthly_bar_chart(
    content: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    monthly: pd.DataFrame,
    base_year: int,
    compare_year: int,
) -> None:
    _pdf_panel(content, x, y, w, h, "Facturacion USD por mes")
    plot_x = x + 46
    plot_y = y + 32
    plot_w = w - 62
    plot_h = h - 76
    frame = monthly.copy() if monthly is not None else pd.DataFrame()
    if frame.empty or "ventas_usd" not in frame.columns:
        _pdf_text(content, x + 20, y + h / 2, "Sin datos para la grafica", 8, (0.38, 0.43, 0.49))
        return
    base_label = f"Ano base {base_year}"
    compare_label = f"Ano comparativo {compare_year}"
    months = frame[["mes_num", "Mes"]].drop_duplicates().sort_values("mes_num").head(12)
    max_value = max(float(frame["ventas_usd"].max()), 1.0) * 1.12
    for tick_idx in range(5):
        value = max_value * tick_idx / 4
        ty = plot_y + plot_h * tick_idx / 4
        _pdf_line(content, plot_x, ty, plot_x + plot_w, ty, (0.91, 0.93, 0.95), 0.45)
        _pdf_text(content, x + 8, int(ty - 3), _pdf_short_number(value), 6, (0.38, 0.43, 0.49))
    _pdf_line(content, plot_x, plot_y, plot_x + plot_w, plot_y, (0.74, 0.78, 0.83), 0.8)
    _pdf_line(content, plot_x, plot_y, plot_x, plot_y + plot_h, (0.74, 0.78, 0.83), 0.8)
    _pdf_text(content, plot_x, y + h - 49, "Ventas USD", 7, (0.38, 0.43, 0.49), "F2")
    _pdf_text(content, plot_x + int(plot_w / 2) - 10, y + 11, "Mes", 7, (0.38, 0.43, 0.49), "F2")
    group_w = plot_w / max(len(months), 1)
    bar_w = min(9, max(4, group_w / 5))
    colors = {base_label: (0.50, 0.00, 0.13), compare_label: (0.31, 0.47, 0.65)}
    for idx, row in enumerate(months.itertuples(index=False)):
        gx = plot_x + idx * group_w + group_w * 0.24
        for offset, label in enumerate([base_label, compare_label]):
            subset = frame[(frame["ano_label"].eq(label)) & (frame["mes_num"].eq(int(row.mes_num)))]
            value = float(subset["ventas_usd"].sum()) if not subset.empty else 0.0
            bh = (value / max_value) * plot_h
            _pdf_rect(content, int(gx + offset * (bar_w + 3)), int(plot_y), int(bar_w), int(bh), colors[label])
        _pdf_text(content, int(plot_x + idx * group_w + 1), y + 20, str(row.Mes)[:3], 6, (0.38, 0.43, 0.49))
    legend_y = y + h - 36
    _pdf_rect(content, x + w - 118, legend_y, 8, 8, colors[base_label])
    _pdf_text(content, x + w - 106, legend_y, str(base_year), 7, (0.38, 0.43, 0.49))
    _pdf_rect(content, x + w - 64, legend_y, 8, 8, colors[compare_label])
    _pdf_text(content, x + w - 52, legend_y, str(compare_year), 7, (0.38, 0.43, 0.49))


def _pdf_pie_chart(content: list[str], x: int, y: int, w: int, h: int, mix: pd.DataFrame, compare_year: int) -> None:
    _pdf_panel(content, x, y, w, h, f"Mix de tallos {compare_year}")
    frame = mix.copy() if mix is not None else pd.DataFrame()
    if frame.empty or "tallos_compare" not in frame.columns:
        _pdf_text(content, x + 20, y + h / 2, "Sin datos para la torta", 8, (0.38, 0.43, 0.49))
        return
    frame = frame.sort_values("tallos_compare", ascending=False).copy()
    if len(frame) > 5:
        top = frame.head(5).copy()
        other = {
            "producto": "Otros",
            "tallos_compare": float(frame.iloc[5:]["tallos_compare"].sum()),
        }
        frame = pd.concat([top, pd.DataFrame([other])], ignore_index=True)
    else:
        frame = frame.head(5)
    total = float(frame["tallos_compare"].sum())
    if total <= 0:
        _pdf_text(content, x + 20, y + h / 2, "Sin tallos para la torta", 8, (0.38, 0.43, 0.49))
        return
    colors = [(0.50, 0.00, 0.13), (0.31, 0.47, 0.65), (0.35, 0.63, 0.31), (0.95, 0.56, 0.17), (0.69, 0.48, 0.63), (0.60, 0.64, 0.69), (0.88, 0.34, 0.35), (0.46, 0.72, 0.70)]
    cx = x + 70
    cy = y + 76
    radius = min(42, h / 3)
    start = -math.pi / 2
    for idx, row in enumerate(frame.itertuples(index=False)):
        value = float(getattr(row, "tallos_compare"))
        angle = (value / total) * math.tau
        steps = max(4, int(angle / math.tau * 42))
        points = [(cx, cy)]
        for step in range(steps + 1):
            a = start + angle * step / steps
            points.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
        _pdf_polygon(content, points, colors[idx % len(colors)])
        start += angle
    legend_x = x + 126
    legend_y = y + h - 46
    for idx, row in enumerate(frame.itertuples(index=False)):
        product = str(getattr(row, "producto"))[:13]
        share = float(getattr(row, "tallos_compare")) / total
        yy = legend_y - idx * 11
        _pdf_rect(content, legend_x, yy, 7, 7, colors[idx % len(colors)])
        _pdf_text(content, legend_x + 10, yy, f"{product} {percent(share)}", 6, (0.18, 0.22, 0.28))


def build_sales_report_pdf(
    context: dict[str, object],
    scope: dict[str, str],
    weekly: pd.DataFrame | None = None,
    report_type: str = "summary",
    view: pd.DataFrame | None = None,
) -> bytes:
    """Generate a compact native PDF without external dependencies."""
    metric_table = sales_metric_comparison_display(context)
    product_table = product_comparison_display(context["product_compare"], context["base_year"], context["compare_year"], rows=10)
    weekly = weekly if weekly is not None else pd.DataFrame()
    base_year = int(context["base_year"])
    compare_year = int(context["compare_year"])
    pages: list[str] = []

    def new_page() -> list[str]:
        c: list[str] = []
        _pdf_rect(c, 0, 770, 595, 72, (0.50, 0.00, 0.13))
        if _pdf_logo_image() is not None:
            _pdf_logo(c, 456, 789, 104, 28)
        _pdf_text(c, 36, 808, "Informe ejecutivo de Ventas Generales", 18, (1, 1, 1), "F2")
        _pdf_text(c, 36, 790, f"Ano base {context['base_year']} vs ano comparativo {context['compare_year']}", 10, (0.94, 0.91, 0.92))
        return c

    c = new_page()
    y = 735
    _pdf_text(c, 36, y, f"Companias: {scope.get('companias', 'todas')} | Clientes: {scope['clientes']}", 10, (0.18, 0.22, 0.28), "F2")
    y -= 16
    _pdf_text(c, 36, y, f"Paises: {scope.get('paises', 'todos')} | Productos: {scope['productos']} | Semanas: {context.get('week_text', 'todas')}", 9, (0.38, 0.43, 0.49))
    y -= 34

    top_products = context["product_compare"].head(6).copy()
    _pdf_bar_chart(
        c,
        36,
        y - 160,
        174,
        150,
        ["Ventas"],
        [float(context["base_metrics"]["ventas_usd"])],
        [float(context["compare_metrics"]["ventas_usd"])],
        "Ventas generales USD",
        base_year,
        compare_year,
        "Ano",
        "Ventas USD",
    )
    if not top_products.empty:
        _pdf_bar_chart(
            c,
            248,
            y - 160,
            294,
            150,
            top_products["producto"].astype(str).str.slice(0, 10).tolist(),
            top_products["ventas_base"].astype(float).tolist(),
            top_products["ventas_compare"].astype(float).tolist(),
            "Ventas por producto",
            base_year,
            compare_year,
            "Producto",
            "Ventas USD",
    )
    y -= 190

    _pdf_monthly_bar_chart(c, 36, y - 154, 248, 144, context.get("monthly_data", pd.DataFrame()), base_year, compare_year)
    _pdf_pie_chart(c, 308, y - 154, 248, 144, context.get("mix_data", pd.DataFrame()), compare_year)
    y -= 184

    base_metrics = context["base_metrics"]
    compare_metrics = context["compare_metrics"]
    card_specs = [
        ("Ventas USD", "ventas_usd", lambda value: moneyless_number(value, 2)),
        ("Tallos confirmados", "tallos_confirmados", lambda value: moneyless_number(value)),
        ("Precio promedio", "precio_usd_tallo", lambda value: moneyless_number(value, 4)),
        ("Pedidos", "pedidos", lambda value: moneyless_number(value)),
    ]
    comparison_cards = []
    for title, metric, formatter in card_specs:
        base_value = float(base_metrics.get(metric, 0) or 0)
        compare_value = float(compare_metrics.get(metric, 0) or 0)
        comparison_cards.append(
            {
                "title": title,
                "base": formatter(base_value),
                "compare": formatter(compare_value),
                "delta_pct": (compare_value - base_value) / base_value if base_value > 0 else np.nan,
            }
        )
    _pdf_comparison_cards(c, 36, y, comparison_cards, base_year, compare_year)
    y -= 104

    _pdf_text(c, 36, y, "Comparativo general", 13, (0.09, 0.13, 0.18), "F2")
    y -= 20
    headers = metric_table.columns.tolist()
    widths = [112, 104, 116, 92, 72]
    x0 = 36
    y = _pdf_table(c, x0, y, 520, headers, metric_table.to_dict("records"), widths, row_h=16, font_size=7)

    if report_type == "summary":
        y -= 18
        _pdf_stroked_rect(c, 36, y - 76, 520, 92, (1, 1, 1))
        _pdf_rect(c, 36, y + 11, 520, 5, (0.50, 0.00, 0.13))
        _pdf_text(c, 50, y - 6, "Lectura estrategica", 13, (0.09, 0.13, 0.18), "F2")
        y -= 24
        for item in context.get("insights", [])[:4]:
            _pdf_text(c, 52, y, f"- {item}", 8, (0.18, 0.22, 0.28))
            y -= 14
        pages.append("\n".join(c))
        return _assemble_pdf_pages(pages, logo=_pdf_logo_image())

    y -= 18
    _pdf_text(c, 36, y, "Top productos por comparativo", 13, (0.09, 0.13, 0.18), "F2")
    y -= 20
    prod_cols = product_table.columns.tolist()[:6]
    prod_widths = [92, 82, 82, 82, 58, 82]
    y = _pdf_table(c, x0, y, 520, prod_cols, product_table.to_dict("records"), prod_widths, row_h=15, font_size=7)

    pages.append("\n".join(c))
    c = new_page()
    y = 735
    _pdf_line_chart(c, 36, y - 130, 500, 130, weekly, "tallos_confirmados", "Tallos confirmados por semana", base_year, compare_year, "Semana ISO", "Tallos confirmados")
    y -= 180
    _pdf_line_chart(c, 36, y - 130, 500, 130, weekly, "precio_usd_tallo", "Precio USD/tallo por semana", base_year, compare_year, "Semana ISO", "USD/tallo")
    y -= 176

    _pdf_text(c, 36, y, "Insights", 13, (0.09, 0.13, 0.18), "F2")
    y -= 18
    for item in context.get("insights", [])[:5]:
        _pdf_text(c, 48, y, f"- {item}", 8, (0.18, 0.22, 0.28))
        y -= 14
    pages.append("\n".join(c))

    if view is not None and not view.empty:
        c = new_page()
        y = 735
        _pdf_text(c, 36, y, "Tablas ejecutivas del dashboard", 13, (0.09, 0.13, 0.18), "F2")
        y -= 22
        client_table = client_sales_display(view, rows=10, ascending=False)
        client_cols = [col for col in ["Compania", "Cliente", "Facturacion USD", "Tallos", "Precio USD/tallo"] if col in client_table.columns]
        if client_cols:
            _pdf_panel(c, 36, y - 172, 520, 178, "Clientes/companias por facturacion", "Orden descendente segun filtros activos.")
            _pdf_table(c, 48, y - 36, 496, client_cols, client_table[client_cols].to_dict("records"), [110, 136, 92, 82, 76][: len(client_cols)], row_h=13, font_size=6)
            y -= 204
        country_table = growth_by_dimension_display(view, base_year, compare_year, ["pais"], ["pais"], rows=8)
        country_cols = country_table.columns.tolist()[:5]
        if country_cols:
            _pdf_panel(c, 36, y - 148, 248, 154, "Crecimiento por pais", "Facturacion y variacion.")
            _pdf_table(c, 48, y - 36, 224, country_cols, country_table[country_cols].to_dict("records"), [54, 48, 48, 42, 32][: len(country_cols)], row_h=13, font_size=6)
        company_cols_group = ["NomCompania"] if "NomCompania" in view.columns else ["cod_cliente", "cliente"]
        company_table = growth_by_dimension_display(view, base_year, compare_year, company_cols_group, company_cols_group, rows=8)
        company_cols = company_table.columns.tolist()[:5]
        if company_cols:
            _pdf_panel(c, 308, y - 148, 248, 154, "Crecimiento por compania", "Comparativo base vs actual.")
            _pdf_table(c, 320, y - 36, 224, company_cols, company_table[company_cols].to_dict("records"), [70, 44, 44, 38, 28][: len(company_cols)], row_h=13, font_size=6)
        pages.append("\n".join(c))

    return _assemble_pdf_pages(pages, logo=_pdf_logo_image())


def _assemble_pdf_pages(pages: list[str], logo: tuple[bytes, int, int, str] | None = None) -> bytes:

    objects: list[bytes] = []
    pages_kids = []
    bold_font_obj = len(pages) * 2 + 4
    logo_obj = bold_font_obj + 1 if logo is not None else None
    for i, page_content in enumerate(pages):
        stream = page_content.encode("latin-1", errors="replace")
        content_obj = 5 + i * 2
        page_obj = 4 + i * 2
        pages_kids.append(f"{page_obj} 0 R")
        xobject = f" /XObject << /Logo {logo_obj} 0 R >>" if logo_obj is not None else ""
        objects.append(f"{page_obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 {bold_font_obj} 0 R >>{xobject} >> /Contents {content_obj} 0 R >> endobj\n".encode("latin-1"))
        objects.append(f"{content_obj} 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n")
    base_objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        f"2 0 obj << /Type /Pages /Kids [{' '.join(pages_kids)}] /Count {len(pages)} >> endobj\n".encode("latin-1"),
        b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"{bold_font_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj\n".encode("latin-1"),
    ]
    extra_objects = []
    if logo is not None and logo_obj is not None:
        img_bytes, img_w, img_h, img_filter = logo
        extra_objects.append(
            f"{logo_obj} 0 obj << /Type /XObject /Subtype /Image /Width {img_w} /Height {img_h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /{img_filter} /Length {len(img_bytes)} >> stream\n".encode("latin-1")
            + img_bytes
            + b"\nendstream endobj\n"
        )
    all_objects = base_objects[:3] + objects + [base_objects[3]] + extra_objects
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in all_objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(all_objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer << /Size {len(all_objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1"))
    return bytes(pdf)


def build_sales_report_html_v2(context: dict[str, object]) -> str:
    """Build a one-page HTML report for the sales executive export."""
    if not context.get("ok"):
        return f"<html><body><h1>Informe ejecutivo de ventas</h1><p>{context.get('message', 'Sin datos')}</p></body></html>"

    style = """
    <style>
    @page { size: A4 portrait; margin: 14mm; }
    body { font-family: Arial, sans-serif; color: #17202a; margin: 18px; }
    h1, h2, h3 { margin: 0 0 12px; }
    .meta { color: #667382; margin-bottom: 12px; }
    .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 12px 0 18px; }
    .card { border: 1px solid #dfe5ec; border-left: 4px solid #800020; border-radius: 8px; padding: 10px 12px; background: #fff; }
    .label { font-size: 11px; text-transform: uppercase; color: #667382; font-weight: 700; }
    .value { font-size: 22px; font-weight: 800; }
    .sub { font-size: 12px; color: #667382; }
    .grid2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .panel { border: 1px solid #dfe5ec; border-radius: 8px; padding: 12px; margin-bottom: 14px; }
    table { border-collapse: collapse; width: 100%; font-size: 12px; }
    th, td { border: 1px solid #dfe5ec; padding: 6px 8px; text-align: left; }
    th { background: #f3e8ec; }
    .insights li { margin-bottom: 8px; }
    .note { color: #5b6775; font-size: 12px; line-height: 1.45; }
    </style>
    """
    monthly_html = context["monthly_fig"].to_html(full_html=False, include_plotlyjs="cdn")
    mix_html = context["mix_fig"].to_html(full_html=False, include_plotlyjs=False)
    product_html = context["product_bar_fig"].to_html(full_html=False, include_plotlyjs=False)
    consolidated_html = context["consolidated_fig"].to_html(full_html=False, include_plotlyjs=False)
    insights_html = "".join(f"<li>{item}</li>" for item in context["insights"])
    metric_table = sales_metric_comparison_display(context)
    product_table = product_comparison_display(context["product_compare"], context["base_year"], context["compare_year"], rows=14)

    return f"""
    <html><head><meta charset="utf-8">{style}</head><body>
    <h1>Informe ejecutivo de Ventas Generales</h1>
    <div class="meta">Comparacion: ano base {context['base_year']} vs ano comparativo {context['compare_year']}</div>
    <div class="cards">
      <div class="card"><div class="label">Facturacion ano base</div><div class="value">{moneyless_number(context['base_metrics']['ventas_usd'], 2)}</div><div class="sub">USD reales</div></div>
      <div class="card"><div class="label">Facturacion ano comparativo</div><div class="value">{moneyless_number(context['compare_metrics']['ventas_usd'], 2)}</div><div class="sub">USD reales</div></div>
      <div class="card"><div class="label">Diferencia absoluta</div><div class="value">{moneyless_number(context['consolidated_delta'], 2)}</div><div class="sub">USD</div></div>
      <div class="card"><div class="label">Crecimiento</div><div class="value">{percent(context['compare_real_pct'])}</div><div class="sub">{context['compare_real_mult']:.2f}x</div></div>
    </div>
    <div class="grid2">
      <div class="panel"><h3>Resumen de facturacion USD</h3>{monthly_html}</div>
      <div class="panel"><h3>Mix por producto</h3>{mix_html}</div>
    </div>
    <div class="grid2">
      <div class="panel"><h3>Tallos por producto</h3>{product_html}</div>
      <div class="panel"><h3>Consolidado real</h3>{consolidated_html}</div>
    </div>
    <div class="panel">
      <h2>Comparativo general</h2>
      {metric_table.to_html(index=False, escape=False)}
    </div>
    <div class="panel">
      <h2>Comparativo por producto</h2>
      {product_table.to_html(index=False, escape=False)}
    </div>
    <div class="panel">
      <h2>Insights automaticos</h2>
      <ul class="insights">{insights_html}</ul>
    </div>
    <div class="panel">
      <h2>Lectura semanal complementaria</h2>
      <div class="note">El reporte conserva la lectura semanal en el dashboard con los filtros activos para validar estacionalidad, aunque aqui se resume en formato ejecutivo.</div>
    </div>
    </body></html>
    """


def render_ventas_generales_tab_v2(
    data: dict[str, pd.DataFrame],
    base_year: int | None,
    compare_year: int | None,
    years: list[int] | None,
    week_range: list[int] | None,
    companies: list[str] | None,
    clients: list[str] | None,
    countries: list[str] | None,
    products: list[str] | None,
    colors: list[str] | None,
) -> html.Div:
    """Executive sales tab with yearly comparison and weekly context."""
    sales = data.get("ventas_semana", pd.DataFrame())
    if sales.empty:
        return html.Div("No existe ventas_semana_cliente_producto.csv. Ejecuta descriptivos para habilitar Ventas generales.", className="table-panel")

    view = filter_general_sales_frame(sales, years, week_range, clients, products, countries, companies, colors)
    if view.empty:
        available_years = sorted(pd.to_numeric(sales["anio"], errors="coerce").dropna().astype(int).unique().tolist()) if "anio" in sales.columns else []
        years_text = ", ".join(map(str, available_years)) if available_years else "sin anos disponibles"
        return html.Div(
            [
                html.Div("Ventas generales", className="panel-title"),
                panel_note(
                    f"No hay ventas para los filtros seleccionados. AÃ±os disponibles en esta base: {years_text}. "
                    "Revisa el rango de semanas, cliente, producto o color seleccionado."
                ),
            ],
            className="table-panel",
        )

    context = build_sales_executive_context_v2(view, base_year, compare_year)

    tallos = float(view["tallos_confirmados"].sum())
    ventas = float(view["ventas_usd"].sum())
    precio = ventas / tallos if tallos > 0 else 0.0
    weekly = summarize_sales_frame(view, ["anio", "semana_iso"]).sort_values(["anio", "semana_iso"])
    annual = summarize_sales_frame(view, ["anio"]).sort_values("anio")

    tallos_fig = px.line(weekly, x="semana_iso", y="tallos_confirmados", color="anio", markers=True, title="Tallos confirmados por semana")
    tallos_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="Tallos confirmados")
    apply_common_layout(tallos_fig, 370)
    tallos_fig.update_yaxes(tickformat=",d")

    precio_fig = px.line(weekly, x="semana_iso", y="precio_usd_tallo", color="anio", markers=True, title="Precio promedio USD/tallo por semana")
    precio_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="USD/tallo")
    apply_common_layout(precio_fig, 345)
    precio_fig.update_yaxes(tickformat=",.4f")

    annual_display = annual.rename(columns={"anio": "Ano", "tallos_confirmados": "Tallos confirmados", "ventas_usd": "Ventas USD", "precio_usd_tallo": "USD/tallo"})[["Ano", "Tallos confirmados", "Ventas USD", "USD/tallo"]].copy()
    annual_display["Tallos confirmados"] = annual_display["Tallos confirmados"].map(moneyless_number)
    annual_display["Ventas USD"] = annual_display["Ventas USD"].map(lambda value: moneyless_number(value, 2))
    annual_display["USD/tallo"] = annual_display["USD/tallo"].map(lambda value: moneyless_number(value, 4))
    weeks_text = f"{int(week_range[0])}-{int(week_range[1])}" if week_range and len(week_range) == 2 else "todas"

    export_buttons = html.Div(
        [
            html.Button(
                "PDF 1 pagina",
                id="general-sales-export-summary",
                n_clicks=0,
                type="button",
                className="executive-button secondary",
            ),
            html.Button(
                "PDF completo",
                id="general-sales-export-full",
                n_clicks=0,
                type="button",
                className="executive-button primary",
            ),
            html.Button(
                "Base cruda CSV",
                id="general-sales-export-raw",
                n_clicks=0,
                type="button",
                className="executive-button secondary",
            ),
        ],
        className="executive-button-group",
    )

    annual_cards = context["annual_cards"] if context.get("ok") else annual.copy()
    executive_metrics = [
        make_year_comparison_card("Ventas USD", annual_cards, "ventas_usd", lambda value: moneyless_number(value, 2), "real por ano"),
        make_year_comparison_card("Tallos confirmados", annual_cards, "tallos_confirmados", lambda value: moneyless_number(value), "misma ventana"),
        make_year_comparison_card("Precio promedio", annual_cards, "precio_usd_tallo", lambda value: moneyless_number(value, 4), "USD/tallo"),
        make_year_comparison_card("Pedidos", annual_cards, "pedidos", lambda value: moneyless_number(value), "ordenes agregadas"),
    ]
    metric_compare_table = sales_metric_comparison_display(context)
    active_compare_year = context.get("compare_year") or compare_year or (int(annual["anio"].max()) if not annual.empty else 0)
    active_base_year = context.get("base_year") or base_year or active_compare_year
    product_compare_table = product_comparison_display(
        context["product_compare"] if context.get("ok") else pd.DataFrame(),
        active_base_year,
        active_compare_year,
        rows=20,
    )
    comparison_mode = bool(context.get("comparison_mode"))
    scope = sales_scope_summary(view, clients, products, countries, companies, colors)
    logo_uri = logo_data_uri()
    strategic_items = context["insights"] if context.get("ok") else ["No hay suficientes datos para construir la comparacion ejecutiva."]
    strategic_cards = [
        html.Div(
            [
                html.Div(f"{idx:02d}", className="strategy-index"),
                html.Div(item, className="strategy-text"),
            ],
            className="strategy-card",
        )
        for idx, item in enumerate(strategic_items[:4], start=1)
    ]
    selected_clients = selected_values(clients)
    client_table_title = "Companias de mayor a menor facturacion" if not selected_clients else "Companias seleccionadas"
    client_table_note = "Orden descendente por facturacion dentro del filtro actual. La tabla tambien permite ordenar manualmente." if not selected_clients else "Resumen de las companias seleccionadas dentro del filtro actual."
    client_table = client_sales_display(view, rows=30, ascending=False)
    product_week_matrix = sales_product_week_matrix_display(view, selected_clients)
    product_week_note = (
        "Cliente seleccionado: productos en filas y semanas en columnas, con tallos confirmados."
        if len(selected_clients) == 1
        else "Sin un unico cliente seleccionado se separa por cliente y producto para evitar mezclar portafolios."
    )
    country_growth_table = (
        growth_by_dimension_display(view, active_base_year, active_compare_year, ["pais"], ["pais"], rows=25)
        if comparison_mode
        else pd.DataFrame()
    )
    company_group_cols = ["NomCompania"] if "NomCompania" in view.columns else ["cod_cliente", "cliente"]
    company_growth_table = (
        growth_by_dimension_display(view, active_base_year, active_compare_year, company_group_cols, company_group_cols, rows=30)
        if comparison_mode
        else pd.DataFrame()
    )
    client_growth_table = (
        growth_by_dimension_display(
            view,
            active_base_year,
            active_compare_year,
            ["cod_cliente", "cliente"] if {"cod_cliente", "cliente"}.issubset(view.columns) else ["cod_cliente"],
            ["cod_cliente", "cliente"] if {"cod_cliente", "cliente"}.issubset(view.columns) else ["cod_cliente"],
            rows=30,
        )
        if comparison_mode
        else pd.DataFrame()
    )
    mover_group_cols = ["cod_cliente", "cliente"] if {"cod_cliente", "cliente"}.issubset(view.columns) else ["cod_cliente"]
    tallos_growth_up = (
        tallos_movers_display(view, active_base_year, active_compare_year, mover_group_cols, mover_group_cols, rows=10, direction="up")
        if comparison_mode
        else pd.DataFrame()
    )
    tallos_growth_down = (
        tallos_movers_display(view, active_base_year, active_compare_year, mover_group_cols, mover_group_cols, rows=10, direction="down")
        if comparison_mode
        else pd.DataFrame()
    )

    report_panel = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Img(src=logo_uri, className="executive-logo") if logo_uri else html.Div("La Gaitana", className="executive-logo-text"),
                            html.Div("Ventas generales", className="executive-kicker"),
                            html.Div("Informe ejecutivo comercial", className="executive-title"),
                            html.Div(
                                (
                                    f"Ano base {active_base_year} vs ano comparativo {active_compare_year} | semanas {weeks_text}"
                                    if context.get("comparison_mode")
                                    else f"Ano seleccionado {active_compare_year} | semanas {weeks_text}"
                                ),
                                className="executive-subtitle",
                            ),
                        ]
                    ),
                    html.Div(export_buttons, className="executive-actions"),
                ],
                className="sales-executive-header",
            ),
            html.Div(
                [
                    html.Div([html.Div("Companias", className="scope-label"), html.Div(scope["companias"], className="scope-value")], className="scope-card scope-card-wide"),
                    html.Div([html.Div("Clientes", className="scope-label"), html.Div(scope["clientes"], className="scope-value")], className="scope-card scope-card-wide"),
                    html.Div([html.Div("Paises", className="scope-label"), html.Div(scope["paises"], className="scope-value")], className="scope-card scope-card-wide"),
                    html.Div([html.Div("Productos", className="scope-label"), html.Div(scope["productos"], className="scope-value")], className="scope-card scope-card-wide"),
                    html.Div([html.Div("Clientes visibles", className="scope-label"), html.Div(scope["clientes_count"], className="scope-number")], className="scope-card"),
                ],
                className="scope-strip",
            ),
            html.Div(executive_metrics, className="metrics-grid"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Ventas generales USD", className="panel-title"),
                            panel_note("Comparacion directa de facturacion real entre anos; si solo hay un ano visible, muestra su total real."),
                            dcc.Graph(figure=context["consolidated_fig"] if context.get("ok") else empty_figure("Ventas generales USD")),
                        ],
                        className="panel panel-feature",
                    ),
                    html.Div(
                        [
                            html.Div("Facturacion por producto", className="panel-title"),
                            panel_note("Barras por producto ordenadas por facturacion del ano seleccionado."),
                            dcc.Graph(figure=context["product_sales_bar_fig"] if context.get("ok") else empty_figure("Facturacion por producto")),
                        ],
                        className="panel panel-feature",
                    ),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([html.Div("Tallos por producto", className="panel-title"), panel_note("Volumen por producto; compara anos cuando existe base visible."), dcc.Graph(figure=context["product_bar_fig"] if context.get("ok") else empty_figure("Tallos por producto"))], className="panel panel-feature"),
                    html.Div([html.Div("Tallos confirmados por semana", className="panel-title"), panel_note("Evolucion semanal de tallos reales para comparar nivel y estacionalidad entre anos."), dcc.Graph(figure=tallos_fig)], className="panel panel-feature"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([html.Div("Evolucion del precio", className="panel-title"), panel_note("Precio promedio ponderado semanal: ventas USD divididas por tallos confirmados."), dcc.Graph(figure=precio_fig)], className="panel panel-feature"),
                    html.Div([html.Div("Resumen mensual USD", className="panel-title"), panel_note("Tendencia mensual del ano seleccionado y comparacion cuando existe base visible."), dcc.Graph(figure=context["monthly_fig"] if context.get("ok") else empty_figure("Facturacion USD por mes"))], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([html.Div("Mix por producto", className="panel-title"), panel_note("Producto dominante del ano seleccionado y su participacion en tallos."), dcc.Graph(figure=context["mix_fig"] if context.get("ok") else empty_figure("Mix por producto"))], className="panel"),
                    html.Div(
                        [
                            html.Div("Lectura estratÃ©gica", className="panel-title"),
                            panel_note("Resumen ejecutivo calculado con los filtros actuales."),
                            html.Div(strategic_cards, className="strategy-grid"),
                        ],
                        className="strategy-panel",
                    ),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Top 10 aumento de tallos", className="panel-title"),
                            panel_note("Ordenado solo por diferencia de tallos; ventas USD se muestran como contexto."),
                            make_table(
                                tallos_growth_up,
                                10,
                                sort_by=[{"column_id": "Dif. tallos", "direction": "desc"}],
                                table_id="ventas-top-tallos-crecimiento",
                            ),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Top 10 caida de tallos", className="panel-title"),
                            panel_note("Ordenado solo por diferencia de tallos; ventas USD se muestran como contexto."),
                            make_table(
                                tallos_growth_down,
                                10,
                                sort_by=[{"column_id": "Dif. tallos", "direction": "asc"}],
                                table_id="ventas-top-tallos-caida",
                            ),
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
                            html.Div("Crecimiento por pais", className="panel-title"),
                            panel_note("Ordenado por facturacion del ano comparativo de mayor a menor. La tabla permite reordenar y reiniciar filtros."),
                            make_table(
                                country_growth_table,
                                12,
                                sort_by=[{"column_id": f"USD {active_compare_year}", "direction": "desc"}],
                                table_id="ventas-crecimiento-pais",
                            ),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Crecimiento por compania", className="panel-title"),
                            panel_note("Ordenado por facturacion del ano comparativo de mayor a menor. La tabla permite reordenar y reiniciar filtros."),
                            make_table(
                                company_growth_table,
                                12,
                                sort_by=[{"column_id": f"USD {active_compare_year}", "direction": "desc"}],
                                table_id="ventas-crecimiento-compania",
                            ),
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
                            html.Div("Crecimiento por cliente", className="panel-title"),
                            panel_note("Clientes ordenados por facturacion del ano comparativo de mayor a menor."),
                            make_table(
                                client_growth_table,
                                12,
                                sort_by=[{"column_id": f"USD {active_compare_year}", "direction": "desc"}],
                                table_id="ventas-crecimiento-cliente",
                            ),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Comparativo general", className="panel-title"),
                            panel_note("Valores reales de los dos anos seleccionados, diferencia absoluta y variacion porcentual."),
                            make_table(metric_compare_table, 8, table_id="ventas-comparativo-general"),
                        ],
                        className="table-panel no-top-margin",
                    ),
                    html.Div(
                        [
                            html.Div("Comparativo por producto", className="panel-title"),
                            panel_note("Productos ordenados por USD del ano comparativo. Incluye ventas, tallos, diferencias y participacion."),
                            make_table(
                                product_compare_table,
                                12,
                                sort_by=[{"column_id": f"USD {active_compare_year}", "direction": "desc"}],
                                table_id="ventas-comparativo-producto",
                            ),
                        ],
                        className="table-panel no-top-margin",
                    ),
                ],
                className="executive-table-grid section-gap",
            ),
            html.Div(
                [
                    html.Div(client_table_title, className="panel-title"),
                    panel_note(client_table_note),
                    make_table(client_table, 15, sort_by=[{"column_id": "Facturacion USD", "direction": "desc"}], table_id="ventas-clientes-facturacion"),
                ],
                className="table-panel section-gap",
            ),
            html.Div(
                [
                    html.Div("Tallos confirmados por producto y semana", className="panel-title"),
                    panel_note(product_week_note),
                    make_table(product_week_matrix, 15, sort_by=[{"column_id": "Total", "direction": "desc"}], table_id="ventas-producto-semana-matriz"),
                ],
                className="table-panel section-gap",
            ),
        ],
        className="sales-executive-panel",
    )

    weekly_panel = html.Div(
        [
            html.Div("Resumen anual complementario", className="panel-title"),
            panel_note("Totales del periodo semanal seleccionado; el precio no es promedio simple, se pondera por tallos."),
            html.Div(
                [
                    html.Div([html.Div("Resumen por ano", className="panel-title"), make_table(annual_display, 8)], className="table-panel no-top-margin"),
                    html.Div([html.Div("Consolidado real", className="panel-title"), panel_note("Real del ano seleccionado y comparacion cuando existe base visible. No incluye proyecciones anualizadas."), dcc.Graph(figure=context["consolidated_fig"] if context.get("ok") else empty_figure("Consolidado real USD"))], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
        ],
        className="section-gap",
    )

    return html.Div([report_panel, weekly_panel])


def render_visualizador_clientes_general(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected: pd.Series | None,
    selected_code: str | None,
    top_n: int,
    history_weeks: int,
    analysis_week: int,
    show_last_year: bool,
    volume_metric: str,
    product_filter: list[str] | str | None,
    color_filter: list[str] | str | None,
    program_filter: str | None,
    visual_sales_years: list[int] | None = None,
    visual_week_range: list[int] | None = None,
    visual_tipo_filter: list[str] | None = None,
    selected_sku_operativo: str | list[str] | None = None,
    color_view: str = "period_total",
    internal_detail: str = "color",
):
    selected_codes = selected_values(selected_code)
    if not selected_codes:
        return html.Div(
            "Selecciona uno o varios clientes para cargar el visualizador detallado.",
            className="table-panel",
        )

    sku_filter = selected_sku_operativo
    view = filter_visual_operational_base(
        data, filtered, selected_code, visual_sales_years, visual_week_range,
        visual_tipo_filter, product_filter, color_filter, sku_filter
    )
    if view.empty:
        return html.Div("No hay historia comercial para los filtros seleccionados.", className="table-panel")

    trend_years = visual_sales_years
    if show_last_year and visual_sales_years:
        trend_years = sorted(set([int(year) for year in visual_sales_years] + [int(year) - 1 for year in visual_sales_years]))
    trend_view = filter_visual_operational_base(
        data, filtered, selected_code, trend_years, visual_week_range,
        visual_tipo_filter, product_filter, color_filter, sku_filter
    )

    reading = visual_operational_reading(view, selected, visual_sales_years, visual_week_range)
    total_stems = view["tallos_confirmados"].sum()
    total_requested = view["tallos_pedidos"].sum()
    total_usd = view["ventas_usd"].sum()
    usd_price = total_usd / total_stems if total_stems else 0
    pedidos = view["pedido"].nunique() if "pedido" in view.columns else len(view)
    cajas = view["caja_operativa"].nunique() if "caja_operativa" in view.columns else 0
    sku_count = view["sku_operativo"].nunique() if "sku_operativo" in view.columns else 0
    fulfillment = total_stems / total_requested if total_requested else 0
    annual = summarize_visual_operational(view, ["anio"]).sort_values("anio") if "anio" in view.columns else pd.DataFrame()
    if not annual.empty:
        annual_skus = (
            view.groupby("anio", dropna=False)["sku_operativo"].nunique().rename("skus_activos").reset_index()
            if "sku_operativo" in view.columns
            else annual[["anio"]].assign(skus_activos=0)
        )
        annual = annual.merge(annual_skus, on="anio", how="left")
    compare_year_cards = annual["anio"].nunique() > 1 if not annual.empty else False
    if compare_year_cards:
        reading += " Las tarjetas siguientes separan cada ano y muestran la variacion contra el ano seleccionado anterior."
        metric_cards = [
            make_year_comparison_card("Tallos confirmados", annual, "tallos_confirmados", lambda value: moneyless_number(value), "misma ventana semanal"),
            make_year_comparison_card("Ventas USD", annual, "ventas_usd", lambda value: moneyless_number(value, 2), "ventas confirmadas"),
            make_year_comparison_card("Precio promedio", annual, "precio_usd_tallo", lambda value: moneyless_number(value, 4), "USD/tallo"),
            make_year_comparison_card("Pedidos", annual, "pedidos", lambda value: moneyless_number(value), "pedidos unicos"),
            make_year_comparison_card("SKUs activos", annual, "skus_activos", lambda value: moneyless_number(value), "SKU operativo"),
            make_year_comparison_card("Cajas", annual, "cajas", lambda value: moneyless_number(value), "cajas IDs"),
        ]
        if volume_metric == "tallos_pedidos":
            metric_cards.append(
                make_year_comparison_card("% cumplimiento", annual, "cumplimiento", lambda value: percent(value), "confirmados vs pedidos")
            )
    else:
        metric_cards = [
            make_card("Tallos confirmados", moneyless_number(total_stems), "metrica principal"),
            make_card("Ventas USD", moneyless_number(total_usd, 2), f"{moneyless_number(usd_price, 4)} USD/tallo"),
            make_card("Precio promedio", moneyless_number(usd_price, 4), "USD/tallo"),
            make_card("Pedidos", moneyless_number(pedidos), "pedidos unicos"),
            make_card("SKUs activos", moneyless_number(sku_count), "SKU operativo"),
            make_card("Cajas", moneyless_number(cajas), "cajas IDs"),
            make_card("% cumplimiento", percent(fulfillment), "confirmados vs pedidos") if volume_metric == "tallos_pedidos" else html.Div(),
        ]

    week_fig = visual_week_figure(trend_view, volume_metric or "tallos_confirmados", show_last_year)
    price_fig = visual_price_figure(trend_view, show_last_year)
    sku_table = visual_sku_ranking(view, top_n)
    sku_fig = px.bar(
        sku_table,
        x="tallos_confirmados",
        y="sku_operativo_visible" if "sku_operativo_visible" in sku_table.columns else "sku_operativo",
        color="tipo_pedido_operativo",
        color_discrete_map=color_map_for(sku_table, "tipo_pedido_operativo"),
        orientation="h",
        hover_data=["sku_operativo_general", "sku_operativo_detalle", "producto_familia", "capuchon", "comida", "empaque", "participacion", "ventas_usd", "precio_usd_tallo", "pedidos", "cajas"],
        title="Ranking de SKUs operativos",
    )
    sku_fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Tallos confirmados", yaxis_title="SKU operativo")
    apply_common_layout(sku_fig, 520)

    composition = visual_color_composition(view, sku_table, sku_filter, color_view or "period_total", analysis_week, internal_detail or "color")
    composition_title, composition_note, _ = visual_composition_context(sku_filter, sku_table)
    if composition.empty:
        comp_fig = empty_figure(composition_title)
    else:
        comp_fig = px.bar(
            composition,
            x="color_interno",
            y="participacion",
            color="color_interno",
            color_discrete_map=color_map_for(composition, "color_interno"),
            hover_data=["sku_operativo", "tallos_confirmados", "ventas_usd", "precio_usd_tallo"],
            title=composition_title,
        )
        comp_fig.update_layout(xaxis_title="Color interno", yaxis_title="Participacion", showlegend=False)
        apply_common_layout(comp_fig, 420)

    tipo_mix = summarize_visual_operational(view, ["tipo_pedido_operativo"]).sort_values("tallos_confirmados", ascending=False)
    if not tipo_mix.empty:
        tipo_total = tipo_mix["tallos_confirmados"].sum()
        tipo_mix["participacion"] = tipo_mix["tallos_confirmados"] / tipo_total if tipo_total else 0
        tipo_fig = px.pie(
            tipo_mix,
            names="tipo_pedido_operativo",
            values="tallos_confirmados",
            color="tipo_pedido_operativo",
            color_discrete_map=color_map_for(tipo_mix, "tipo_pedido_operativo"),
            hover_data=["participacion", "ventas_usd", "pedidos"],
            title="Mix por tipo operativo",
            hole=0.35,
        )
        apply_pie_label_style(tipo_fig)
        apply_common_layout(tipo_fig, 420)
    else:
        tipo_fig = empty_figure("Mix por tipo operativo")

    recent_history = visual_recent_history(view, analysis_week, top_n, sku_view_mode="detalle" if str(internal_detail).lower() == "variedad" else "general")
    client_table = summarize_visual_operational(view, ["cod_cliente", "cliente"]).sort_values(["tallos_confirmados", "ventas_usd"], ascending=False).head(max(top_n, 15))
    detail_cols = [col for col in ["anio", "semana_iso", "cod_cliente", "cliente", "sku_operativo", "tipo_pedido_operativo", "producto", "color", "tipo_caja", "tallos_x_ramo"] if col in view.columns]
    week_detail = summarize_visual_operational(view, detail_cols).sort_values(["anio", "semana_iso", "tallos_confirmados"], ascending=[True, True, False]).head(500) if detail_cols else pd.DataFrame()

    tipo_selected = set(normalize_operational_type(pd.Series(visual_tipo_filter or [])).tolist())
    if tipo_selected == {"SOLIDO"}:
        view_note = "Vista solidos: el color participa en la identidad del SKU operativo."
    elif tipo_selected and "SOLIDO" not in tipo_selected:
        view_note = "Vista de estructuras: el ranking prioriza el tipo real del pedido; el color queda como composicion interna."
    else:
        view_note = "Vista todos los tipos: SOLIDO se lee como SKU producto/color; los demas tipos conservan su estructura de pedido."
    internal_note = {
        "color": "Detalle interno por color.",
        "color_variedad": "Detalle interno por color y variedad.",
        "variedad": "Detalle interno por variedad.",
    }.get(str(internal_detail), "Detalle interno por color.")

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Lectura operativa de ventas", className="panel-title"),
                    html.Div([html.Div(reading), html.Div(view_note, className="metric-detail"), html.Div(internal_note, className="metric-detail")], className="reading-text"),
                ],
                className="reading-panel",
            ),
            html.Div(
                metric_cards,
                className="metrics-grid visual-metrics",
            ),
            html.Div([html.Div(dcc.Graph(figure=week_fig), className="panel"), html.Div(dcc.Graph(figure=price_fig), className="panel")], className="grid-2"),
            html.Div([html.Div(dcc.Graph(figure=sku_fig), className="panel"), html.Div(dcc.Graph(figure=comp_fig), className="panel")], className="grid-2 section-gap"),
            html.Div([html.Div(dcc.Graph(figure=tipo_fig), className="panel")], className="section-gap"),
            html.Div(
                [
                    html.Div([html.Div("Ranking de SKUs operativos", className="panel-title"), make_table(format_operational_display(sku_table), 12)], className="table-panel no-top-margin"),
                    html.Div([html.Div(composition_title, className="panel-title"), panel_note(composition_note), make_table(format_operational_display(composition), 12)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div([html.Div("Historia reciente por SKU", className="panel-title"), make_table(format_operational_display(recent_history), 14)], className="table-panel"),
            html.Div(
                [
                    html.Div([html.Div("Detalle por cliente", className="panel-title"), make_table(format_operational_display(client_table), 10)], className="table-panel no-top-margin"),
                    html.Div([html.Div("Detalle por semana / SKU / color interno", className="panel-title"), make_table(format_operational_display(week_detail), 10)], className="table-panel no-top-margin"),
                ],
                className="grid-2 section-gap",
            ),
        ]
    )


def ranked_mix_figure(df: pd.DataFrame, selected_code: str, dimension: str, top_n: int, title: str) -> go.Figure:
    if df.empty or dimension not in df.columns:
        return empty_figure(title)
    work = df[df["cod_cliente"] == selected_code].copy()
    if work.empty:
        return empty_figure(title)
    work = work.sort_values("tallos", ascending=False).head(top_n)
    fig = px.bar(work, x="tallos", y=dimension, orientation="h", color="participacion_cliente", title=title, color_continuous_scale=[CORPORATE_BURGUNDY, "#B07AA1", "#4E79A7", "#59A14F"])
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return apply_common_layout(fig, 360)


def sku_treemap(df: pd.DataFrame, selected_code: str, top_n: int) -> go.Figure:
    if df.empty:
        return empty_figure("Top SKUs terminados")
    work = df[df["cod_cliente"] == selected_code].sort_values("tallos", ascending=False).head(top_n).copy()
    if work.empty:
        return empty_figure("Top SKUs terminados")
    for col in ["tipo_pedido_operativo", "producto", "color", "sku_terminado"]:
        work[col] = work[col].fillna("sin_info").astype(str)
    fig = px.treemap(
        work,
        path=["tipo_pedido_operativo", "producto", "color", "sku_terminado"],
        values="tallos",
        color="cumplimiento",
        color_continuous_scale="RdYlGn",
        title="Top SKUs terminados por estructura",
    )
    return apply_common_layout(fig, 520)


def _filter_solid_forecast_frame(
    frame: pd.DataFrame,
    start_date: str | None,
    end_date: str | None,
    years,
    week_range,
    markets,
    countries,
    clients,
    products,
    colors,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if "week_start" in out.columns:
        out["week_start"] = pd.to_datetime(out["week_start"], errors="coerce")
        if start_date:
            out = out[out["week_start"].ge(pd.to_datetime(start_date, errors="coerce"))].copy()
        if end_date:
            out = out[out["week_start"].le(pd.to_datetime(end_date, errors="coerce"))].copy()
    if years and "anio" in out.columns:
        year_set = {int(year) for year in years if pd.notna(year)}
        out = out[pd.to_numeric(out["anio"], errors="coerce").astype("Int64").isin(year_set)].copy()
    if week_range and len(week_range) == 2 and "semana_iso" in out.columns:
        weeks = pd.to_numeric(out["semana_iso"], errors="coerce")
        out = out[weeks.between(int(week_range[0]), int(week_range[1]))].copy()
    for col, values in [
        ("mercado_cluster", markets),
        ("pais", countries),
        ("cod_cliente", clients),
        ("producto", products),
        ("color", colors),
    ]:
        selected = selected_values(values)
        if selected and col in out.columns:
            out = out[out[col].astype(str).isin({str(value) for value in selected})].copy()
    return out


def _forecast_wape(frame: pd.DataFrame, group_cols: list[str] | None = None) -> float:
    if frame.empty or "tallos" not in frame.columns:
        return np.nan
    actual = pd.to_numeric(frame["tallos"], errors="coerce").fillna(0)
    if "error_abs" in frame.columns:
        error = pd.to_numeric(frame["error_abs"], errors="coerce").fillna(0)
    elif "prediccion" in frame.columns:
        predicted = pd.to_numeric(frame["prediccion"], errors="coerce").fillna(0)
        error = (predicted - actual).abs()
    else:
        return np.nan
    denom = actual.sum()
    return float(error.sum() / denom) if denom > 0 else np.nan


def _normalize_solid_forecast_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if "week_start" in out.columns:
        out["week_start"] = pd.to_datetime(out["week_start"], errors="coerce")
    for col in [
        "anio",
        "semana_iso",
        "tallos",
        "tallos_estimados",
        "prediccion",
        "error_abs",
        "probabilidad_compra",
        "volumen_si_compra",
        "MAE",
        "RMSE",
        "WAPE",
        "MAPE_no_cero",
        "bias_pct",
        "tallos_reales",
        "tallos_predichos",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def build_forecast_notes_table(importance: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    if importance.empty:
        return pd.DataFrame()
    out = importance.copy()
    score_col = "importancia_positiva" if "importancia_positiva" in out.columns else "importancia"
    if score_col in out.columns:
        out[score_col] = pd.to_numeric(out[score_col], errors="coerce")
        out = out.sort_values(score_col, ascending=False)
    cols = [
        "etapa_modelo",
        "bloque",
        "variable",
        "descripcion",
        score_col,
    ]
    out = out[[col for col in cols if col in out.columns]].head(top_n).copy()
    rename = {
        "etapa_modelo": "Etapa",
        "bloque": "Bloque",
        "variable": "Variable",
        "descripcion": "Lectura",
        score_col: "Importancia",
    }
    out = out.rename(columns=rename)
    if "Importancia" in out.columns:
        out["Importancia"] = out["Importancia"].map(lambda value: f"{value:.3f}" if pd.notna(value) else "")
    return out


def build_forecast_market_importance_table(
    market_importance: pd.DataFrame,
    markets,
    top_n_per_market: int = 5,
) -> pd.DataFrame:
    if market_importance.empty:
        return pd.DataFrame()
    out = market_importance.copy()
    selected_markets = selected_values(markets)
    if selected_markets and "mercado_cluster" in out.columns:
        out = out[out["mercado_cluster"].astype(str).isin(selected_markets)].copy()
    score_col = "importancia_positiva" if "importancia_positiva" in out.columns else "importancia"
    if score_col in out.columns:
        out[score_col] = pd.to_numeric(out[score_col], errors="coerce")
        sort_cols = ["mercado_cluster", score_col] if "mercado_cluster" in out.columns else [score_col]
        out = out.sort_values(sort_cols, ascending=[True, False] if len(sort_cols) == 2 else False)
    if "mercado_cluster" in out.columns:
        out = out.groupby("mercado_cluster", group_keys=False).head(top_n_per_market)
    cols = [
        "mercado_cluster",
        "etapa_modelo",
        "bloque",
        "variable",
        "descripcion",
        score_col,
    ]
    out = out[[col for col in cols if col in out.columns]].copy()
    rename = {
        "mercado_cluster": "Mercado",
        "etapa_modelo": "Etapa",
        "bloque": "Bloque",
        "variable": "Variable",
        "descripcion": "Lectura",
        score_col: "Importancia",
    }
    out = out.rename(columns=rename)
    if "Importancia" in out.columns:
        out["Importancia"] = out["Importancia"].map(lambda value: f"{value:.3f}" if pd.notna(value) else "")
    return out


def forecast_reading_guide():
    return html.Div(
        [
            html.Div("Forecast solidos", className="panel-title"),
            html.Div(
                [
                    html.P("La vista usa las tablas de forecast SOLIDO: historia semanal, prediccion futura, backtest y validacion retrospectiva."),
                    html.P("Los filtros reducen ese mismo universo de forecast por mercado, pais, cliente, producto y color."),
                ],
                className="reading-text",
            ),
        ],
        className="reading-panel",
    )


def render_forecast_solidos_tab(
    data: dict[str, pd.DataFrame],
    start_date: str | None,
    end_date: str | None,
    years,
    week_range,
    forecast_horizon_weeks: int | None,
    validation_year: int | None,
    validation_weeks: int | None,
    validation_start_week: int | None,
    markets,
    countries,
    clients,
    products,
    colors,
    test_model: str | None,
    scenario_client: str | None,
    scenario_product: str | None,
    scenario_color: str | None,
    scenario_probability: int | None,
    scenario_volume: int | None,
    top_n: int,
):
    """Renderiza forecast, backtest, explicabilidad y escenarios comerciales.

    Todos los filtros de esta vista operan sobre el universo SOLIDO historico
    separado de descriptivos.
    """
    history = _normalize_solid_forecast_frame(data.get("solid_forecast_weekly", pd.DataFrame()))
    future = _normalize_solid_forecast_frame(data.get("solid_forecast_future", pd.DataFrame()))
    test = _normalize_solid_forecast_frame(data.get("solid_forecast_test", pd.DataFrame()))
    historical_validation = _normalize_solid_forecast_frame(
        data.get("solid_forecast_historical_validation", pd.DataFrame())
    )
    evaluation = _normalize_solid_forecast_frame(data.get("solid_forecast_eval", pd.DataFrame()))
    source = data.get("solid_forecast_source", pd.DataFrame())
    importance = data.get("solid_forecast_importance", pd.DataFrame()).copy()
    market_importance = data.get("solid_forecast_market_importance", pd.DataFrame()).copy()
    market_calibration = data.get("solid_forecast_market_calibration", pd.DataFrame()).copy()
    predictors = data.get("solid_forecast_predictors", pd.DataFrame()).copy()
    if history.empty or future.empty:
        return html.Div(
            "No hay outputs de forecast historico. Ejecuta run_forecast_solidos.py y apunta --forecast-dir a su salida.",
            className="table-panel",
        )

    hist_view = _filter_solid_forecast_frame(history, start_date, end_date, years, week_range, markets, countries, clients, products, colors)
    # La corrida genera hasta ocho semanas futuras; el usuario selecciona
    # cuantas necesita exponer para la decision comercial actual.
    forecast_horizon_weeks = int(forecast_horizon_weeks) if forecast_horizon_weeks in {2, 5, 8} else 5
    future_weeks = sorted(pd.to_datetime(future["week_start"], errors="coerce").dropna().unique())[:forecast_horizon_weeks]
    future_scope = future[future["week_start"].isin(future_weeks)].copy()
    future_view = _filter_solid_forecast_frame(future_scope, None, None, None, None, markets, countries, clients, products, colors)
    test_view = _filter_solid_forecast_frame(test, None, None, None, None, markets, countries, clients, products, colors)
    # La retrospectiva usa una ventana independiente seleccionable, para
    # contrastar error y sesgo en el mismo plazo que se quiere proyectar.
    validation_weeks = int(validation_weeks) if validation_weeks in {2, 5, 8} else 5
    valid_starts = valid_validation_window_starts(historical_validation, validation_year, validation_weeks)
    validation_start_week = int(validation_start_week) if validation_start_week in valid_starts else (valid_starts[0] if valid_starts else None)
    validation_end_week = validation_start_week + validation_weeks - 1 if validation_start_week is not None else None
    retrospective_scope = historical_validation.copy()
    if validation_year is not None and validation_start_week is not None:
        retrospective_scope = retrospective_scope[
            retrospective_scope["anio"].eq(int(validation_year))
            & retrospective_scope["semana_iso"].between(validation_start_week, validation_end_week, inclusive="both")
        ].copy()
    else:
        retrospective_scope = retrospective_scope.iloc[0:0].copy()
    retrospective_view = _filter_solid_forecast_frame(
        retrospective_scope, None, None, None, None, markets, countries, clients, products, colors
    )
    validation_window_label = (
        f"{int(validation_year)} | semanas {validation_start_week:02d} - {validation_end_week:02d} ({validation_weeks} semanas)"
        if validation_year is not None and validation_start_week is not None
        else "Sin ventana comparable"
    )
    validation_years_available = sorted(
        pd.to_numeric(historical_validation.get("anio", pd.Series(dtype=float)), errors="coerce")
        .dropna().astype(int).unique().tolist()
    )
    validation_limit_text = (
        f"Ventanas disponibles: anos {validation_years_available[0]} a {validation_years_available[-1]}, "
        f"solo inicios que completan {validation_weeks} semanas dentro del ano y tienen referencia del ano anterior."
        if validation_years_available else
        "No hay periodos historicos comparables para validacion retrospectiva."
    )
    used_model = str(future["modelo"].dropna().iloc[0]) if "modelo" in future.columns and not future.empty else "sin_modelo"
    test_model = test_model or used_model
    test_view = test_view[test_view["modelo"].astype(str).eq(str(test_model))].copy() if not test_view.empty else test_view

    scope_actual = float(test_view["tallos"].sum()) if not test_view.empty else 0.0
    scope_error = float(test_view["error_abs"].sum()) if not test_view.empty else np.nan
    scope_wape = scope_error / scope_actual if scope_actual > 0 else np.nan
    scope_bias = (
        (float(test_view["prediccion"].sum()) - scope_actual) / scope_actual
        if scope_actual > 0 and not test_view.empty
        else np.nan
    )
    weekly_wape = _forecast_wape(test_view, ["week_start"])
    market_wape = _forecast_wape(test_view, ["mercado_cluster", "week_start"])
    product_color_wape = _forecast_wape(test_view, ["producto", "color", "week_start"])
    selected_eval = evaluation[evaluation["modelo"].astype(str).eq(used_model)] if not evaluation.empty else pd.DataFrame()
    global_wape = float(selected_eval.iloc[0]["WAPE"]) if not selected_eval.empty else np.nan

    seasonal_fig = go.Figure()
    if not hist_view.empty:
        historic_season = hist_view.groupby(["anio", "semana_iso"], as_index=False)["tallos"].sum()
        for year in sorted(historic_season["anio"].dropna().astype(int).unique()):
            line = historic_season[historic_season["anio"].eq(year)]
            seasonal_fig.add_trace(go.Scatter(
                x=line["semana_iso"], y=line["tallos"], mode="lines+markers",
                name=f"Real {year}", line=dict(width=2),
            ))
    if not future_view.empty:
        forecast_season = future_view.groupby("semana_iso", as_index=False)["tallos_estimados"].sum()
        seasonal_fig.add_trace(go.Scatter(
            x=forecast_season["semana_iso"], y=forecast_season["tallos_estimados"],
            mode="lines+markers", name=f"Forecast {int(future_view['anio'].max())}",
            line=dict(color=FORECAST_LINE_COLOR, width=5, dash="dash"),
            marker=dict(size=9, color=FORECAST_LINE_COLOR, line=dict(width=1, color="white")),
        ))
    if hist_view.empty and future_view.empty:
        seasonal_fig = empty_figure("Comparacion estacional por semana y ano")
    else:
        seasonal_fig.update_layout(title="Estacionalidad: tallos confirmados por semana en cada ano vs forecast")
        seasonal_fig.update_xaxes(title="Semana ISO", dtick=4)
        seasonal_fig.update_yaxes(title="Tallos")
        apply_common_layout(seasonal_fig, 460)

    historic_week = hist_view.groupby("week_start", as_index=False)["tallos"].sum() if not hist_view.empty else pd.DataFrame()
    future_week = future_view.groupby("week_start", as_index=False)["tallos_estimados"].sum() if not future_view.empty else pd.DataFrame()
    demand_fig = go.Figure()
    if not historic_week.empty:
        demand_fig.add_trace(go.Scatter(
            x=historic_week["week_start"],
            y=historic_week["tallos"],
            name="Historico real",
            mode="lines",
            line=dict(color="#4E79A7", width=2),
        ))
    if not future_week.empty:
        demand_fig.add_trace(go.Scatter(
            x=future_week["week_start"],
            y=future_week["tallos_estimados"],
            name=f"Forecast usado: {used_model}",
            mode="lines+markers",
            line=dict(color=FORECAST_LINE_COLOR, width=5),
            marker=dict(size=9, color=FORECAST_LINE_COLOR, line=dict(width=1, color="white")),
        ))
    if historic_week.empty and future_week.empty:
        demand_fig = empty_figure("Historia real y forecast filtrado")
    else:
        demand_fig.update_layout(title="Comportamiento historico y linea de forecast de solidos")
        demand_fig.update_yaxes(title="Tallos")
        demand_fig.update_xaxes(title="Semana")
        apply_common_layout(demand_fig, 420)

    if test_view.empty:
        test_fig = empty_figure("Validacion: real frente a prediccion")
    else:
        test_week = test_view.groupby("week_start", as_index=False).agg(
            tallos_reales=("tallos", "sum"),
            tallos_predichos=("prediccion", "sum"),
        )
        test_long = test_week.melt(id_vars="week_start", var_name="serie", value_name="tallos")
        test_fig = px.line(
            test_long,
            x="week_start",
            y="tallos",
            color="serie",
            markers=True,
            color_discrete_map={"tallos_reales": "#4E79A7", "tallos_predichos": FORECAST_LINE_COLOR},
            title=f"Validacion de las ultimas semanas: {test_model}",
        )
        apply_common_layout(test_fig, 390)

    retrospective_wape = _forecast_wape(retrospective_view, ["week_start"])
    retrospective_actual = float(retrospective_view["tallos"].sum()) if not retrospective_view.empty else 0.0
    retrospective_pred = float(retrospective_view["prediccion"].sum()) if not retrospective_view.empty else 0.0
    retrospective_bias = (
        (retrospective_pred - retrospective_actual) / retrospective_actual
        if retrospective_actual > 0 else np.nan
    )
    if retrospective_view.empty:
        retrospective_fig = empty_figure(f"Validacion retrospectiva: ventana de {validation_weeks} semanas")
        retrospective_table = pd.DataFrame()
    else:
        retro_week = retrospective_view.groupby("week_start", as_index=False).agg(
            tallos_reales=("tallos", "sum"),
            tallos_predichos=("prediccion", "sum"),
        )
        retro_long = retro_week.melt(id_vars="week_start", var_name="serie", value_name="tallos")
        retrospective_fig = px.line(
            retro_long,
            x="week_start",
            y="tallos",
            color="serie",
            markers=True,
            color_discrete_map={"tallos_reales": "#4E79A7", "tallos_predichos": FORECAST_LINE_COLOR},
            title=f"Prediccion retrospectiva estacional: {validation_window_label}",
        )
        apply_common_layout(retrospective_fig, 410)
        retrospective_table = retrospective_view.groupby(["mercado_cluster"], as_index=False).agg(
            tallos_reales=("tallos", "sum"),
            tallos_predichos=("prediccion", "sum"),
            error_abs=("error_abs", "sum"),
        )
        retrospective_table["WAPE"] = (
            retrospective_table["error_abs"] / retrospective_table["tallos_reales"].replace(0, np.nan)
        ).map(percent)
        retrospective_table["Bias"] = (
            (retrospective_table["tallos_predichos"] - retrospective_table["tallos_reales"])
            / retrospective_table["tallos_reales"].replace(0, np.nan)
        ).map(percent)
        retrospective_table = retrospective_table.rename(columns={
            "mercado_cluster": "Mercado",
            "tallos_reales": "Tallos reales",
            "tallos_predichos": "Tallos predichos",
        })
        retrospective_table.insert(0, "Ventana", validation_window_label)
    retrospective_duration_rows = []
    if validation_year is not None and validation_start_week is not None:
        for duration in [2, 5, 8]:
            if validation_start_week not in valid_validation_window_starts(historical_validation, validation_year, duration):
                continue
            candidate = historical_validation[
                historical_validation["anio"].eq(int(validation_year))
                & historical_validation["semana_iso"].between(
                    int(validation_start_week), int(validation_start_week) + duration - 1, inclusive="both"
                )
            ].copy()
            candidate = _filter_solid_forecast_frame(
                candidate, None, None, None, None, markets, countries, clients, products, colors
            )
            actual = float(candidate["tallos"].sum()) if not candidate.empty else 0.0
            predicted = float(candidate["prediccion"].sum()) if not candidate.empty else 0.0
            retrospective_duration_rows.append({
                "Horizonte": f"{duration} semanas",
                "Tallos reales": moneyless_number(actual),
                "Tallos predichos": moneyless_number(predicted),
                "WAPE": percent(_forecast_wape(candidate, ["week_start"])),
                "Bias": percent((predicted - actual) / actual if actual > 0 else np.nan),
            })
    retrospective_duration_table = pd.DataFrame(retrospective_duration_rows)

    if future_view.empty:
        color_fig = empty_figure("Forecast futuro por color")
        client_fig = empty_figure("Clientes con mayor forecast")
    else:
        top_colors = (
            future_view.groupby("color", as_index=False)["tallos_estimados"].sum()
            .sort_values("tallos_estimados", ascending=False)
            .head(max(top_n, 10))["color"]
        )
        color_week = future_view[future_view["color"].isin(top_colors)].groupby(
            ["week_start", "color"], as_index=False
        )["tallos_estimados"].sum()
        color_fig = px.bar(
            color_week,
            x="week_start",
            y="tallos_estimados",
            color="color",
            color_discrete_map=color_map_for(color_week, "color"),
            title="Composicion futura: colores que explican el volumen proyectado",
        )
        apply_common_layout(color_fig, 390)
        client_future = (
            future_view.groupby(["cod_cliente", "cliente", "mercado_cluster"], as_index=False)["tallos_estimados"].sum()
            .sort_values("tallos_estimados", ascending=False)
            .head(max(top_n, 10))
        )
        client_fig = px.bar(
            client_future.sort_values("tallos_estimados"),
            x="tallos_estimados",
            y="cliente",
            orientation="h",
            color="mercado_cluster",
            color_discrete_map=color_map_for(client_future, "mercado_cluster"),
            title="Clientes con mayor demanda solida proyectada",
            hover_data=["cod_cliente"],
        )
        apply_common_layout(client_fig, 390)

    if test_view.empty:
        fit_fig = empty_figure("Ajuste por producto-color y semana")
    else:
        fit_points = (
            test_view.groupby(["producto", "color", "week_start"], as_index=False)
            .agg(real=("tallos", "sum"), prediccion=("prediccion", "sum"))
        )
        fit_fig = px.scatter(
            fit_points,
            x="real",
            y="prediccion",
            color="producto",
            size="real",
            hover_data=["color", "week_start"],
            title="Rendimiento: pronostico vs real por producto-color-semana",
        )
        upper = float(max(fit_points["real"].max(), fit_points["prediccion"].max())) if not fit_points.empty else 0
        fit_fig.add_trace(go.Scatter(
            x=[0, upper], y=[0, upper], name="Ajuste perfecto", mode="lines",
            line=dict(color="#334155", dash="dot", width=2),
        ))
        apply_common_layout(fit_fig, 400)

    notes_table = build_forecast_notes_table(importance)
    market_importance_table = build_forecast_market_importance_table(market_importance, markets)
    calibration_table = market_calibration.copy()
    selected_markets = selected_values(markets)
    if selected_markets and not calibration_table.empty:
        calibration_table = calibration_table[
            calibration_table["mercado_cluster"].astype(str).isin(selected_markets)
        ].copy()
    if not calibration_table.empty:
        calibration_table["Mercado"] = calibration_table["mercado_cluster"].astype(str).str.replace("_", " ", regex=False)
        calibration_table["Ajuste volumen"] = pd.to_numeric(
            calibration_table["factor_calibracion_mercado"], errors="coerce"
        ).map(lambda value: f"x{value:.2f}" if pd.notna(value) else "x1.00")
        calibration_table["Sesgo base"] = pd.to_numeric(
            calibration_table["sesgo_base_pct"], errors="coerce"
        ).map(percent)
        calibration_table["Decision"] = np.where(
            calibration_table["subpronostico_sostenido"].astype(str).str.lower().isin(["true", "1"]),
            "Ajuste aplicado",
            "Sin ajuste",
        )
        calibration_table = calibration_table[["Mercado", "Sesgo base", "Ajuste volumen", "Decision", "lectura_negocio"]]

    scenario_prob_factor = float(scenario_probability or 100) / 100.0
    scenario_volume_factor = float(scenario_volume or 100) / 100.0
    scenario_selected = bool(scenario_client)
    if scenario_selected:
        scenario_frame = _filter_solid_forecast_frame(
            future_scope,
            None,
            None,
            None,
            None,
            markets,
            countries,
            [scenario_client],
            [scenario_product] if scenario_product else None,
            [scenario_color] if scenario_color else None,
        )
        scenario_frame["probabilidad_escenario"] = (
            scenario_frame.get("probabilidad_compra", pd.Series(1.0, index=scenario_frame.index)) * scenario_prob_factor
        ).clip(0, 1)
        if "volumen_si_compra" in scenario_frame.columns:
            scenario_frame["volumen_escenario"] = scenario_frame["volumen_si_compra"] * scenario_volume_factor
            scenario_frame["tallos_escenario"] = scenario_frame["probabilidad_escenario"] * scenario_frame["volumen_escenario"]
        else:
            scenario_frame["tallos_escenario"] = scenario_frame["tallos_estimados"] * scenario_prob_factor * scenario_volume_factor
        scenario_week = scenario_frame.groupby("week_start", as_index=False).agg(
            base=("tallos_estimados", "sum"),
            escenario=("tallos_escenario", "sum"),
        )
        scenario_long = scenario_week.melt(id_vars="week_start", var_name="serie", value_name="tallos")
        scenario_fig = px.line(
            scenario_long,
            x="week_start",
            y="tallos",
            color="serie",
            markers=True,
            color_discrete_map={"base": FORECAST_LINE_COLOR, "escenario": SCENARIO_LINE_COLOR},
            title="Simulador comercial: forecast base vs escenario ajustado",
        )
        apply_common_layout(scenario_fig, 395)
        scenario_base_total = float(scenario_frame["tallos_estimados"].sum())
        scenario_total = float(scenario_frame["tallos_escenario"].sum())
        scenario_delta = (scenario_total - scenario_base_total) / scenario_base_total if scenario_base_total > 0 else np.nan
    else:
        scenario_fig = empty_figure("Simulador comercial: selecciona un cliente")
        scenario_base_total = 0
        scenario_total = 0
        scenario_delta = np.nan

    if evaluation.empty:
        model_table = pd.DataFrame()
    else:
        model_table = evaluation.copy()
        model_table["uso"] = np.where(model_table["modelo_seleccionado"].eq(True), "USADO PARA FORECAST", "comparacion")
        for col in ["WAPE", "MAPE_no_cero", "bias_pct"]:
            if col in model_table.columns:
                model_table[col] = model_table[col].map(percent)
        for col in ["MAE", "RMSE", "tallos_reales", "tallos_predichos"]:
            if col in model_table.columns:
                model_table[col] = model_table[col].map(lambda value: moneyless_number(value, 0))
        model_table = model_table[["uso", "modelo", "WAPE", "MAE", "RMSE", "bias_pct", "tallos_reales", "tallos_predichos"]]

    detail_cols = [
        "week_start", "mercado_cluster", "pais", "cod_cliente", "cliente", "producto", "color",
        "probabilidad_compra", "volumen_si_compra", "tallos_estimados", "modelo",
    ]
    detail = future_view[[col for col in detail_cols if col in future_view.columns]].sort_values(
        "tallos_estimados", ascending=False
    ).head(1000) if not future_view.empty else pd.DataFrame()
    if "week_start" in detail:
        detail["week_start"] = detail["week_start"].dt.strftime("%Y-%m-%d")
    market_summary = (
        future_view.groupby(["mercado_cluster", "producto", "color"], as_index=False)
        .agg(tallos_estimados=("tallos_estimados", "sum"), clientes=("cod_cliente", "nunique"))
        .sort_values("tallos_estimados", ascending=False)
        .head(100)
        if not future_view.empty else pd.DataFrame()
    )

    filter_text = (
        f"Alcance visible: mercado {selected_label(markets)}, pais {selected_label(countries)}, "
        f"producto {selected_label(products)}, color {selected_label(colors)}, cliente {selected_label(clients)} "
        f"y horizonte de {forecast_horizon_weeks} semanas futuras. "
        f"La comparacion historica muestra semanas ISO {int(week_range[0]) if week_range else 1} a {int(week_range[1]) if week_range else 53}."
    )
    risk_text = (
        f"En el backtest final de ocho semanas, el ajuste para volumen semanal es {percent(weekly_wape)} y para producto-color es {percent(product_color_wape)}; "
        f"la asignacion fina a cliente-producto-color es mas incierta ({percent(scope_wape)}). Usa color/volumen para planeacion y confirma la distribucion por cliente comercialmente."
    )
    source_text = ""
    if not source.empty:
        row = source.iloc[0]
        source_text = (
            f"Fuente modelada: SOLIDO confirmado desde {pd.to_datetime(row.get('fecha_min')).strftime('%Y-%m-%d')} "
            f"hasta {pd.to_datetime(row.get('fecha_max')).strftime('%Y-%m-%d')}; "
            f"{moneyless_number(row.get('lineas_solidas_confirmadas', 0))} lineas y "
            f"{moneyless_number(row.get('clientes', 0))} clientes."
        )
    selected_clients = selected_values(clients)
    if len(selected_clients) == 1:
        match = history[history["cod_cliente"].astype(str).eq(selected_clients[0])]["cliente"].dropna().astype(str)
        client_card_label = f"{match.iloc[0]} | {selected_clients[0]}" if not match.empty else selected_clients[0]
    else:
        client_card_label = selected_label(clients, "Todos")
    market_card_label = selected_label(markets, "Todos").replace("_", " ")
    return html.Div(
        [
            forecast_reading_guide(),
            html.Div("1. Proyeccion para el alcance seleccionado", className="report-step-title"),
            html.Div(
                [
                    html.Div("Alcance seleccionado para la prediccion", className="panel-title"),
                    html.Div(
                        [
                            make_card("Mercado", market_card_label, "filtro activo"),
                            make_card("Pais", selected_label(countries, "Todos"), "filtro activo"),
                            make_card("Cliente", client_card_label, "demanda pronosticada"),
                            make_card("Producto", selected_label(products, "Todos"), "solidos"),
                            make_card("Color", selected_label(colors, "Todos"), "composicion"),
                            make_card("Horizonte", f"{forecast_horizon_weeks} semanas", "forecast futuro"),
                        ],
                        className="metrics-grid",
                    ),
                ],
                className="table-panel",
            ),
            html.Div(
                [
                    html.Div("Lectura comercial del alcance seleccionado", className="panel-title"),
                    html.Div(
                        [
                            html.P(source_text),
                            html.P(filter_text),
                            html.P(f"El modelo utilizado para la linea futura es {used_model}. El modelo visible en el backtest es {test_model}. En semanas florales se aplica un refuerzo anual cuando existe evidencia comparable; la demanda se proyecta por cliente, producto y color."),
                            html.P(risk_text),
                        ],
                        className="reading-text",
                    ),
                ],
                className="reading-panel",
            ),
            html.Div(
                [
                    make_card("Modelo usado", used_model, "seleccionado por menor WAPE global"),
                    make_card("WAPE semana", percent(weekly_wape), "backtest final 8 semanas"),
                    make_card("WAPE mercado", percent(market_wape), "backtest final 8 semanas"),
                    make_card("WAPE producto-color", percent(product_color_wape), "backtest final 8 semanas"),
                    make_card("WAPE cliente-color", percent(scope_wape), "backtest final 8 semanas"),
                    make_card("Bias filtrado", percent(scope_bias), "backtest final; + sobrepronostico"),
                    make_card("Forecast visible", moneyless_number(future_view["tallos_estimados"].sum() if not future_view.empty else 0), f"tallos en {forecast_horizon_weeks} semanas"),
                ],
                className="metrics-grid",
            ),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=seasonal_fig), panel_note("Compara la misma semana entre los anos seleccionados. La linea segmentada es el forecast y permanece visible aunque elijas anos historicos, para revisar directamente si respeta la estacionalidad del producto, color o cliente filtrado.")], className="panel"),
                ],
                className="section-gap",
            ),
            html.Div("2. Validacion de una ventana historica", className="report-step-title"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(f"Validacion retrospectiva de {validation_weeks} semanas", className="panel-title"),
                            panel_note("Escoge el ano, la duracion y el inicio en los filtros. Esta prueba valida la referencia estacional contra semanas que ya ocurrieron; no agrega todo el ano ni reentrena el boosting para cada corte."),
                            html.Div(
                                [
                                    make_card("Ventana evaluada", validation_window_label, "periodo fijo"),
                                    make_card("Tallos reales", moneyless_number(retrospective_actual), f"{validation_weeks} semanas"),
                                    make_card("Tallos predichos", moneyless_number(retrospective_pred), f"{validation_weeks} semanas"),
                                    make_card("WAPE", percent(retrospective_wape), "error ventana"),
                                    make_card("Bias", percent(retrospective_bias), "positivo = sobrepronostico"),
                                ],
                                className="metrics-grid",
                            ),
                            panel_note(validation_limit_text),
                            dcc.Graph(figure=retrospective_fig),
                        ],
                        className="panel",
                    ),
                    html.Div(
                        [
                            html.Div("Comparacion por horizonte", className="panel-title"),
                            panel_note("Compara 2, 5 y 8 semanas desde el mismo inicio seleccionado. El bias negativo indica que la referencia estacional habria quedado corta."),
                            make_table(retrospective_duration_table, 3),
                            html.Div("Precision por mercado", className="panel-title"),
                            make_table(retrospective_table, 12),
                        ],
                        className="table-panel no-top-margin",
                    ),
                ],
                className="grid-2 section-gap",
            ),
            html.Div("3. Detalle de demanda y ajuste observado", className="report-step-title"),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=demand_fig), panel_note("Une la trayectoria real del filtro con la demanda futura estimada. Revisa si la pendiente y los picos futuros son coherentes con la historia del cliente, producto o color seleccionado.")], className="panel"),
                    html.Div([dcc.Graph(figure=test_fig), panel_note("Es una prueba historica: compara la prediccion con tallos realmente observados. Separaciones grandes implican cautela para ese filtro.")], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=color_fig), panel_note("Descompone el forecast por color. Sirve para preparar oferta y abastecimiento de los colores que explican mayor volumen futuro.")], className="panel"),
                    html.Div([dcc.Graph(figure=client_fig), panel_note("Prioriza cuentas con mayor volumen previsto en el filtro actual. Confirma primero los clientes con mayor exposiciÃ³n comercial.")], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div([html.Div("Demanda proyectada por mercado, producto y color", className="panel-title"), panel_note("Resumen comercial de volumen futuro: permite identificar donde concentrar validacion con clientes y preparacion de producto/color."), make_table(market_summary, 14)], className="table-panel"),
            html.Div([html.Div("Detalle accionable de demanda solida proyectada", className="panel-title"), panel_note("Cada fila es demanda semanal estimada por cliente, destino, producto y color. Cuando aplica, incluye probabilidad de compra y volumen esperado si la compra ocurre."), make_table(detail, 18)], className="table-panel"),
            html.Div([html.Div([dcc.Graph(figure=fit_fig), panel_note("Cada punto compara tallos reales con tallos pronosticados por producto-color-semana durante el test. Los puntos cercanos a la diagonal indican mejor ajuste.")], className="panel")], className="section-gap"),
            html.Div("4. Simulacion comercial", className="report-step-title"),
            html.Div(
                [
                    html.Div("Simulador comercial de una prediccion", className="panel-title"),
                    panel_note("Selecciona un cliente en los controles de escenario y, opcionalmente, producto/color. Ajustar probabilidad o volumen no reentrena el modelo: simula una hipotesis comercial sobre la prediccion base."),
                    html.Div(
                        [
                            make_card("Cliente escenario", selected_label(scenario_client, "Selecciona cliente"), "simulacion"),
                            make_card("Producto escenario", selected_label(scenario_product, "Todos"), "simulacion"),
                            make_card("Color escenario", selected_label(scenario_color, "Todos"), "simulacion"),
                            make_card("Forecast base", moneyless_number(scenario_base_total), "tallos"),
                            make_card("Escenario", moneyless_number(scenario_total), "tallos"),
                            make_card("Cambio", percent(scenario_delta), "contra base"),
                        ],
                        className="metrics-grid",
                    ),
                    dcc.Graph(figure=scenario_fig),
                ],
                className="table-panel",
            ),
            html.Div("5. Modelo, variables y limitaciones", className="report-step-title"),
            html.Div(
                [
                    html.Div("Notas del modelo", className="panel-title"),
                    panel_note("El boosting combina probabilidad de compra y volumen esperado. Aprende fases de temporada (preparacion, pico y salida post-fiesta) e indices semanales por mercado-producto-color para reconocer subidas y caidas recurrentes; una importancia alta no implica causalidad."),
                    make_table(notes_table, 10),
                    html.Div(
                        [
                            html.P("Limitaciones: el forecast proyecta tallos SOLIDO por cliente, producto y color; no determina grado, caja ni inventario requerido."),
                            html.P("La mejora se evalua principalmente en volumen semanal, mercado y producto-color. La asignacion fina por cliente-color es mas incierta; valida comercialmente picos, clientes nuevos y cambios de programa."),
                        ],
                        className="reading-text",
                    ),
                    html.Div("Ajuste de nivel por mercado", className="panel-title"),
                    panel_note("Si el modelo subestima volumen en ambas mitades del backtest, se aplica una correccion acotada por mercado. El refuerzo anual solo opera en preparacion o pico floral con historia comparable; las semanas posteriores quedan en manos del modelo para representar la caida observada."),
                    make_table(calibration_table, 8),
                ],
                className="reading-panel",
            ),
            html.Div([html.Div("Seleccion del modelo y metricas de ajuste global", className="panel-title"), panel_note("Los tres modelos se evaluan en las mismas ocho semanas finales. El marcado como USADO PARA FORECAST alimenta la linea futura."), make_table(model_table, 6)], className="table-panel"),
            html.Div([html.Div("Importancia del boosting por mercado", className="panel-title"), panel_note("Compara que senales son mas relevantes dentro de cada mercado en validacion. Es el mismo modelo general evaluado por mercado, no un modelo diferente para cada uno."), make_table(market_importance_table, 20)], className="table-panel"),
        ]
    )


def render_datos_tab(data: dict[str, pd.DataFrame], filtered: pd.DataFrame, selected_code: str | None):
    profile_cols = [
        "cod_cliente",
        "cliente",
        "score_compra_terminada",
        "recomendacion_compra",
        "segmento_cliente",
        "tallos_total",
        "semanas_activas",
        "cumplimiento_tallos",
        "share_top5_sku_terminado",
        "share_top3_color",
    ]
    profile_table = filtered[[col for col in profile_cols if col in filtered.columns]].head(500)

    estado = data["estado"]

    return html.Div(
        [
            html.Div(
                [
                    html.Div([html.Div("Perfil clientes filtrado", className="panel-title"), make_table(profile_table, 15)], className="table-panel"),
                    html.Div([html.Div("Estado de ordenes", className="panel-title"), make_table(estado, 10)], className="table-panel"),
                ],
                className="grid-2",
            ),
        ]
    )


if __name__ == "__main__":
    args = parse_args()
    app = build_app(Path(args.data_dir), Path(args.forecast_dir))
    app.run(host=args.host, port=args.port, debug=args.debug)
