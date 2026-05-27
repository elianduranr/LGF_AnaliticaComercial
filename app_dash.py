"""Dashboard modular de analitica comercial LGF.

Consume de forma separada outputs descriptivos, clusters por mercado y
forecast historico de solidos. Las pestañas de inventario se mantienen como
reservas funcionales hasta que exista una fuente oficial de proyeccion.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash
from dash import Input
from dash import Output
from dash import State
from dash import ctx
from dash import dash_table
from dash import dcc
from dash import html


DEFAULT_DATA_DIR = Path("resultados") / "descriptivos"
DEFAULT_CLUSTER_DIR = Path("resultados") / "clusters"
DEFAULT_FORECAST_DIR = Path("resultados") / "forecast_solidos"

CORPORATE_BURGUNDY = "#800020"
FORECAST_LINE_COLOR = "#E63946"
SCENARIO_LINE_COLOR = "#00875A"
REGION_COLOR_MAP = {
    "EEUU / CANADA": "#4E79A7",
    "EEUU / CANADÁ": "#4E79A7",
    "USA": "#4E79A7",
    "UNITED STATES": "#4E79A7",
    "CANADA": "#4E79A7",
    "CANADÁ": "#4E79A7",
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
    "tallos_promedio_semana_normal", "porcentaje_semana_normal", "frecuencia_en_ventana", "pedidos_en_ventana", "instancias_en_ventana",
    "cumplimiento", "vigencia_sku", "recomendacion", "tallos_ventana", "ventas_usd_ventana",
]

SKU_COMPOSITION_COLS = [
    "cod_cliente", "cliente", "sku_operativo", "tipo_pedido_operativo", "producto", "color", "variedad",
    "porcentaje_composicion", "tallos_promedio_semana_normal", "ramos_promedio_semana_normal",
    "tipo_caja", "tallos_por_ramo", "capuchon", "comida", "empaque", "semanas", "estabilidad_composicion", "std_share_color",
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
        "--clusters-dir",
        default=str(DEFAULT_CLUSTER_DIR),
        help="Carpeta independiente con los CSV generados por run_clusters.py.",
    )
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
    if value is None or pd.isna(value):
        return "0"
    return f"{value:,.{decimals}f}"


def percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "0.0%"
    return f"{value * 100:,.1f}%"


def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True)


def load_cluster_bundle(source_dir: Path) -> dict[str, pd.DataFrame]:
    """Carga una corrida anual completa de clusters desde una carpeta."""
    similares = read_csv_if_exists(source_dir / "clientes_similares.csv")
    if not similares.empty:
        similares["cod_cliente_base"] = normalize_code(similares["cod_cliente_base"])
        similares["cod_cliente_similar"] = normalize_code(similares["cod_cliente_similar"])

    clusters = read_csv_if_exists(source_dir / "clusters_clientes.csv")
    if not clusters.empty:
        clusters["cod_cliente"] = normalize_code(clusters["cod_cliente"])
        for col in [
            "tallos_total", "semanas_activas", "pct_semanas_activas",
            "tallos_promedio_semana", "cv_volumen", "cumplimiento_tallos",
            "ventas_usd_total", "ventas_usd_por_tallo", "participacion_tallos_mercado",
            "tallos_ultimas_8_semanas", "tallos_8_semanas_previas", "variacion_reciente_vs_previa",
            "complejidad_operativa_score",
            "share_top3_color", "share_top5_sku", "share_top1_tipo_pedido",
            "tallos_x_ramo_promedio", "ramos_x_caja_promedio",
            "score_compra_terminada", "score_compra_terminada_operativo",
            "silhouette_modelo", "calinski_modelo",
        ]:
            if col in clusters.columns:
                clusters[col] = pd.to_numeric(clusters[col], errors="coerce").fillna(0)
    features = read_csv_if_exists(source_dir / "cluster_features_cliente.csv")
    if not features.empty:
        features["cod_cliente"] = normalize_code(features["cod_cliente"])
    return {
        "similares": similares,
        "clusters": clusters,
        "cluster_eval": read_csv_if_exists(source_dir / "cluster_model_evaluation.csv"),
        "cluster_resumen": read_csv_if_exists(source_dir / "cluster_resumen.csv"),
        "cluster_features": features,
        "cluster_diff": read_csv_if_exists(source_dir / "cluster_variables_diferenciadoras.csv"),
        "cluster_blocks": read_csv_if_exists(source_dir / "cluster_perfil_bloques.csv"),
        "cluster_periodo": read_csv_if_exists(source_dir / "cluster_periodo_analisis.csv", parse_dates=["fecha_min", "fecha_max"]),
    }


def discover_cluster_bundles(cluster_root: Path) -> tuple[dict[str, dict[str, pd.DataFrame]], str | None]:
    """Descubre corridas `clusters/<anio>/`; admite una corrida plana legado."""
    bundles: dict[str, dict[str, pd.DataFrame]] = {}
    if cluster_root.exists():
        for path in sorted(cluster_root.iterdir()):
            if path.is_dir() and path.name.isdigit() and (path / "clusters_clientes.csv").exists():
                bundles[path.name] = load_cluster_bundle(path)
        if not bundles and (cluster_root / "clusters_clientes.csv").exists():
            flat = load_cluster_bundle(cluster_root)
            periodo = flat.get("cluster_periodo", pd.DataFrame())
            year = (
                str(int(periodo.iloc[0]["anio_cluster"]))
                if not periodo.empty and "anio_cluster" in periodo.columns
                else "Corrida vigente"
            )
            bundles[year] = flat
    default_year = sorted(bundles, key=lambda value: int(value) if value.isdigit() else -1)[-1] if bundles else None
    return bundles, default_year


def load_data(
    data_dir: Path,
    forecast_dir: Path | None = None,
    clusters_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Carga outputs independientes para construir las vistas del dashboard.

    ``data_dir`` contiene descriptivos, ``clusters_dir`` contiene la
    segmentacion de clientes y ``forecast_dir`` contiene solo el forecast de
    solidos. Si no existe una carpeta separada de clusters se admite la
    carpeta descriptiva por compatibilidad con corridas antiguas.
    """
    perfil = read_csv_if_exists(data_dir / "perfil_cliente.csv", PROFILE_COLS)
    if not perfil.empty:
        perfil["cod_cliente"] = normalize_code(perfil["cod_cliente"])
        if "ultima_fecha_confirmada" in perfil.columns:
            perfil["ultima_fecha_confirmada"] = pd.to_datetime(perfil["ultima_fecha_confirmada"], errors="coerce")
        if "dias_desde_ultima_compra" not in perfil.columns and "ultima_fecha_confirmada" in perfil.columns:
            perfil["dias_desde_ultima_compra"] = (perfil["ultima_fecha_confirmada"].max() - perfil["ultima_fecha_confirmada"]).dt.days
        perfil = perfil.sort_values(["score_compra_terminada", "tallos_total"], ascending=False)

    serie = read_csv_if_exists(data_dir / "serie_cliente_semana.csv", SERIE_COLS)
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

    mix_producto = read_csv_if_exists(data_dir / "mix_producto.csv", MIX_COMMON_COLS + ["producto"])
    mix_color = read_csv_if_exists(data_dir / "mix_color.csv", MIX_COMMON_COLS + ["color"])
    mix_tipo = read_csv_if_exists(
        data_dir / "mix_tipo_pedido.csv",
        MIX_COMMON_COLS + ["tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_empaque", "receta"],
    )
    mix_sku = read_csv_if_exists(
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
    )
    mix_analisis = read_csv_if_exists(
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
    )
    mix_color_rol = read_csv_if_exists(
        data_dir / "mix_color_rol.csv",
        MIX_COMMON_COLS + ["familia_analisis_operativa", "rol_color_operativo", "tipo_pedido_operativo", "producto", "color"],
    )
    for frame in [mix_producto, mix_color, mix_tipo, mix_sku, mix_analisis, mix_color_rol]:
        if not frame.empty:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])

    cluster_source_dir = clusters_dir if clusters_dir and clusters_dir.exists() else data_dir
    cluster_bundles, cluster_default_year = discover_cluster_bundles(cluster_source_dir)
    active_cluster_bundle = cluster_bundles.get(cluster_default_year, {})
    similares = active_cluster_bundle.get("similares", pd.DataFrame())
    clusters = active_cluster_bundle.get("clusters", pd.DataFrame())
    cluster_eval = active_cluster_bundle.get("cluster_eval", pd.DataFrame())
    cluster_resumen = active_cluster_bundle.get("cluster_resumen", pd.DataFrame())
    cluster_features = active_cluster_bundle.get("cluster_features", pd.DataFrame())
    cluster_diff = active_cluster_bundle.get("cluster_diff", pd.DataFrame())
    cluster_blocks = active_cluster_bundle.get("cluster_blocks", pd.DataFrame())

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

    historico_confirmado = read_csv_if_exists(data_dir / "historico_confirmado.csv", HISTORICO_SOLIDOS_COLS, ["fecha"])
    historico_visualizador_comercial = read_csv_if_exists(
        data_dir / "historico_visualizador_comercial.csv", HISTORICO_SOLIDOS_COLS, ["fecha"]
    )
    if historico_visualizador_comercial.empty:
        historico_visualizador_comercial = historico_confirmado.copy()
    for history_frame in [historico_confirmado, historico_visualizador_comercial]:
        if history_frame.empty:
            continue
        history_frame["cod_cliente"] = normalize_code(history_frame["cod_cliente"])
        history_frame["tallos_historicos"] = pd.to_numeric(
            history_frame.get("tallos_analisis", history_frame.get("tallos_total", 0)),
            errors="coerce",
        ).fillna(0)
        if "ventas_usd" not in history_frame.columns:
            history_frame["ventas_usd"] = 0.0
        history_frame["ventas_usd"] = pd.to_numeric(history_frame["ventas_usd"], errors="coerce").fillna(0)
        for col in ["VALORUNITARIO", "VALORTOTAL"]:
            if col in history_frame.columns:
                history_frame[col] = pd.to_numeric(history_frame[col], errors="coerce").fillna(0)
        if "NomMoneda" not in history_frame.columns:
            history_frame["NomMoneda"] = "SIN_MONEDA"
        enriched = add_week_columns(history_frame, "fecha")
        history_frame[enriched.columns] = enriched
    historico_solidos = historico_confirmado.copy()
    if not historico_solidos.empty:
        historico_solidos = historico_solidos[
            historico_solidos["tipo_pedido_operativo"].astype(str).str.upper().eq("SOLIDO")
        ].copy()

    estado = read_csv_if_exists(data_dir / "estado_resumen.csv")

    forecast_dir = forecast_dir or DEFAULT_FORECAST_DIR
    solid_forecast_source = read_csv_if_exists(forecast_dir / "solid_forecast_fuente_datos.csv", parse_dates=["fecha_min", "fecha_max"])
    solid_forecast_eval = read_csv_if_exists(forecast_dir / "solid_forecast_model_evaluation.csv")
    solid_forecast_importance = read_csv_if_exists(forecast_dir / "solid_forecast_feature_importance.csv")
    solid_forecast_market_importance = read_csv_if_exists(forecast_dir / "solid_forecast_market_feature_importance.csv")
    solid_forecast_market_calibration = read_csv_if_exists(forecast_dir / "solid_forecast_market_calibration.csv")
    solid_forecast_predictors = read_csv_if_exists(forecast_dir / "solid_forecast_predictors.csv")
    solid_forecast_weekly = read_csv_if_exists(forecast_dir / "solid_forecast_weekly_demand.csv", parse_dates=["week_start"])
    solid_forecast_test = read_csv_if_exists(forecast_dir / "solid_forecast_test_predictions.csv", parse_dates=["week_start"])
    solid_forecast_historical_validation = read_csv_if_exists(forecast_dir / "solid_forecast_historical_validation.csv", parse_dates=["week_start"])
    solid_forecast_future = read_csv_if_exists(forecast_dir / "solid_forecast_future.csv", parse_dates=["week_start"])
    solid_forecast_error_market = read_csv_if_exists(forecast_dir / "solid_forecast_error_by_market.csv")
    for frame in [solid_forecast_weekly, solid_forecast_test, solid_forecast_historical_validation, solid_forecast_future]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
        if not frame.empty:
            for col in ["tallos", "prediccion", "tallos_estimados", "anio", "semana_iso", "probabilidad_compra", "volumen_si_compra"]:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    estructuras = read_csv_if_exists(data_dir / "cliente_estructuras_repetidas.csv", STRUCTURE_COLS)
    if not estructuras.empty:
        estructuras["cod_cliente"] = normalize_code(estructuras["cod_cliente"])

    semana_tipica = read_csv_if_exists(data_dir / "cliente_semana_tipica.csv", TYPICAL_WEEK_COLS)
    if not semana_tipica.empty:
        semana_tipica["cod_cliente"] = normalize_code(semana_tipica["cod_cliente"])
        semana_tipica["semana"] = pd.to_numeric(semana_tipica["semana"], errors="coerce").astype("Int64")

    sku_resumen = read_csv_if_exists(data_dir / "cliente_sku_operativo_resumen.csv", SKU_SUMMARY_COLS)
    sku_composicion = read_csv_if_exists(data_dir / "cliente_sku_operativo_composicion.csv", SKU_COMPOSITION_COLS)
    semana_sku = read_csv_if_exists(data_dir / "cliente_semana_sku_operativo.csv", WEEK_SKU_COLS)
    for frame in [sku_resumen, sku_composicion, semana_sku]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])

    ventas_semana = read_csv_if_exists(data_dir / "ventas_semana_cliente_producto.csv", SALES_VISUAL_COLS)
    ventas_producto = read_csv_if_exists(data_dir / "ventas_producto_periodo.csv", [col for col in SALES_VISUAL_COLS if col not in ["cod_cliente", "cliente"]])
    ventas_cliente = read_csv_if_exists(data_dir / "ventas_cliente_periodo.csv", ["anio", "semana_iso", "anio_semana", "cod_cliente", "cliente", "moneda_original", "tallos_confirmados", "ventas_usd", "valor_total_original", "pedidos", "cajas_ids", "precio_usd_tallo", "precio_moneda_original_tallo"])
    ventas_caja = read_csv_if_exists(data_dir / "ventas_caja_periodo.csv", SALES_BOX_COLS)
    for frame in [ventas_semana, ventas_cliente, ventas_caja]:
        if not frame.empty and "cod_cliente" in frame.columns:
            frame["cod_cliente"] = normalize_code(frame["cod_cliente"])
    for frame in [ventas_semana, ventas_producto, ventas_cliente, ventas_caja]:
        if not frame.empty:
            for col in ["anio", "semana_iso", "tallos_confirmados", "ventas_usd", "valor_total_original", "precio_usd_tallo", "precio_moneda_original_tallo"]:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    estructura_caja = read_csv_if_exists(data_dir / "estructura_caja.csv", STRUCTURE_BOX_COLS, ["fecha"])
    estructura_componentes = read_csv_if_exists(data_dir / "estructura_componentes.csv", STRUCTURE_COMPONENT_COLS, ["fecha"])
    catalogo_estructura_version = read_csv_if_exists(
        data_dir / "catalogo_estructura_version.csv",
        STRUCTURE_VERSION_COLS,
        ["primera_fecha", "ultima_fecha"],
    )
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
        "similares": similares,
        "clusters": clusters,
        "cluster_eval": cluster_eval,
        "cluster_resumen": cluster_resumen,
        "cluster_features": cluster_features,
        "cluster_diff": cluster_diff,
        "cluster_blocks": cluster_blocks,
        "cluster_bundles": cluster_bundles,
        "cluster_default_year": cluster_default_year,
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
    return str(value or "").upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U").strip()


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
            delta = "nuevo" if value else "0.0%"
            delta_class = "year-delta positive" if value else "year-delta neutral"
        else:
            change = (value - previous_value) / previous_value
            delta = f"{change:+.1%} vs {previous_year}"
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


def make_table(df: pd.DataFrame, page_size: int = 10) -> dash_table.DataTable:
    if df.empty:
        df = pd.DataFrame({"mensaje": ["Sin datos para mostrar"]})
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": col, "id": col} for col in df.columns],
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        export_format="csv",
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


def build_app(data_dir: Path, forecast_dir: Path | None = None, clusters_dir: Path | None = None) -> Dash:
    """Construye el tablero a partir de los tres modulos analiticos activos."""
    data = load_data(data_dir, forecast_dir, clusters_dir)
    perfil = data["perfil"]

    recommendation_options = []
    segment_options = []
    client_options = []
    product_options = []
    color_options = []
    cluster_year_options = []
    cluster_default_year = data.get("cluster_default_year")
    cluster_market_options = []
    cluster_id_options = []
    sales_year_options = []
    sales_default_years = []
    sales_base_year_options = []
    sales_default_base_year = None
    sales_default_compare_year = None
    general_sales_client_options = []
    general_sales_product_options = []
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
        client_options = [
            {"label": f"{row.cod_cliente}", "value": row.cod_cliente}
            for row in perfil[["cod_cliente", "cliente"]].head(5000).itertuples(index=False)
        ]
    cluster_year_options = [
        {"label": str(year), "value": str(year)}
        for year in sorted(
            data.get("cluster_bundles", {}),
            key=lambda value: int(value) if str(value).isdigit() else -1,
            reverse=True,
        )
    ]
    clusters_source = data.get("clusters", pd.DataFrame())
    if not clusters_source.empty and "mercado_cluster" in clusters_source.columns:
        cluster_market_options = [
            {"label": market, "value": market}
            for market in sorted(clusters_source["mercado_cluster"].dropna().astype(str).unique())
        ]
        if "cluster_id" in clusters_source.columns:
            label_cols = [col for col in ["mercado_cluster", "cluster_id", "nombre_cluster"] if col in clusters_source.columns]
            cluster_labels = clusters_source[label_cols].drop_duplicates().sort_values(label_cols).copy()
            cluster_id_options = [
                {
                    "label": " | ".join(str(getattr(row, col)) for col in label_cols),
                    "value": getattr(row, "cluster_id"),
                }
                for row in cluster_labels.itertuples(index=False)
            ]
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
        if "producto" in ventas_source.columns:
            general_sales_product_options = [
                {"label": product, "value": product}
                for product in sorted(ventas_source["producto"].dropna().astype(str).unique())
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
    app = Dash(__name__, title="LGF Analitica Comercial")
    app.layout = html.Div(
        [
            dcc.Store(id="data-dir", data=str(data_dir)),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("LGF Analitica Comercial"),
                            html.P("Visualizador de clientes, clusters y forecast historico de solidos."),
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
                            dcc.Dropdown(id="client", options=client_options, value=None, clearable=True, placeholder="Todos los clientes"),
                            html.Div("Primero selecciona un cliente. El 360 explica como viene pidiendo en semanas recientes y separa solidos, surtidos, recetas y bulk.", className="filter-help"),
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
                                    dcc.Tab(label="Visualizador clientes general", value="visualizador_clientes_general"),
                                    dcc.Tab(label="Ventas generales", value="ventas_generales"),
                                    dcc.Tab(label="Estructuras y componentes", value="estructuras_componentes"),
                                    dcc.Tab(label="Clusters", value="clusters"),
                                    dcc.Tab(label="Comprador", value="comprador"),
                                    dcc.Tab(label="Demanda e inventario", value="demanda"),
                                    dcc.Tab(label="Forecast solidos historico", value="forecast_solidos"),
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
                                            html.Label("Año base"),
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
                                            html.Label("Año comparativo"),
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
                                ],
                                id="general-sales-options",
                                className="demand-options",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Label("Ano de cluster"),
                                            dcc.Dropdown(
                                                id="cluster-year-filter",
                                                options=cluster_year_options,
                                                value=cluster_default_year,
                                                clearable=False,
                                                placeholder="Selecciona el ano modelado",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Mercado"),
                                            dcc.Dropdown(
                                                id="cluster-market-filter",
                                                options=cluster_market_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los mercados",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Cluster"),
                                            dcc.Dropdown(
                                                id="cluster-id-filter",
                                                options=cluster_id_options,
                                                value=[],
                                                multi=True,
                                                clearable=True,
                                                placeholder="Todos los clusters",
                                            ),
                                        ],
                                        className="demand-control",
                                    ),
                                ],
                                id="cluster-options",
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
        Input("general-sales-clients", "value"),
        Input("general-sales-products", "value"),
        Input("compare-mode", "value"),
        Input("solid-product", "value"),
        Input("analysis-scope", "value"),
        Input("color-filter", "value"),
        Input("cluster-year-filter", "value"),
        Input("cluster-market-filter", "value"),
        Input("cluster-id-filter", "value"),
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
        client: str,
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
        general_sales_clients: list[str] | None,
        general_sales_products: list[str] | None,
        compare_mode: str | None,
        solid_product: str | None,
        analysis_scope: str | None,
        color_filter: str | None,
        cluster_year_filter: str | None,
        cluster_market_filter: list[str] | str | None,
        cluster_id_filter: list[str] | str | None,
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
        selected = select_client(filtered, data["perfil"], client)
        selected_code = None if selected is None else selected["cod_cliente"]
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
                selected_code,
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
                general_sales_clients,
                general_sales_products,
            )
        if tab == "estructuras_componentes":
            return render_estructuras_componentes_tab(
                data,
                selected_code,
                top_n,
                client_product_filter,
                client_color_filter,
                visual_sales_years,
                visual_week_range,
            )
        if tab == "clusters":
            cluster_data = data.copy()
            cluster_bundle = data.get("cluster_bundles", {}).get(str(cluster_year_filter), {})
            cluster_data.update(cluster_bundle)
            return render_clusters_tab(
                cluster_data,
                filtered,
                selected_code,
                top_n,
                cluster_market_filter,
                cluster_id_filter,
                cluster_year_filter,
                data.get("cluster_bundles", {}),
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
        return render_visualizador_clientes_general(
            data, filtered, selected, selected_code, top_n, client_lookback_weeks,
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
        Output("cluster-options", "style"),
        Output("forecast-options", "style"),
        Output("global-client-filters", "style"),
        Output("app-shell", "style"),
        Input("tabs", "value"),
    )
    def toggle_context_options(tab: str):
        visible = {"display": "block"}
        hidden = {"display": "none"}
        if tab in ["visualizador_clientes_general", "estructuras_componentes"]:
            if tab == "visualizador_clientes_general":
                return {"display": "none"}, {"display": "grid"}, hidden, hidden, visible, hidden, hidden, hidden, {}, {}
            return {"display": "none"}, {"display": "grid"}, hidden, hidden, hidden, hidden, hidden, hidden, {}, {}
        if tab == "ventas_generales":
            return hidden, hidden, hidden, hidden, hidden, {"display": "grid"}, hidden, hidden, hidden, {"gridTemplateColumns": "1fr"}
        if tab == "clusters":
            return hidden, hidden, hidden, hidden, hidden, hidden, {"display": "grid"}, hidden, {"display": "none"}, {"gridTemplateColumns": "1fr"}
        if tab == "forecast_solidos":
            return hidden, hidden, hidden, hidden, hidden, hidden, hidden, {"display": "block"}, {"display": "none"}, {"gridTemplateColumns": "1fr"}
        return hidden, hidden, hidden, hidden, hidden, hidden, hidden, hidden, {"display": "none"}, {"gridTemplateColumns": "1fr"}

    @app.callback(
        Output("cluster-market-filter", "options"),
        Output("cluster-market-filter", "value"),
        Output("cluster-id-filter", "options"),
        Output("cluster-id-filter", "value"),
        Input("cluster-year-filter", "value"),
        Input("cluster-market-filter", "value"),
        Input("cluster-id-filter", "value"),
    )
    def update_cluster_filter_options(year, markets, cluster_ids):
        """Mantiene filtros consistentes con la corrida anual elegida."""
        bundle = data.get("cluster_bundles", {}).get(str(year), {})
        frame = bundle.get("clusters", pd.DataFrame())
        if frame.empty:
            return [], [], [], []
        market_values = sorted(frame["mercado_cluster"].dropna().astype(str).unique())
        selected_markets = [value for value in selected_values(markets) if value in set(market_values)]
        scope = frame[frame["mercado_cluster"].astype(str).isin(selected_markets)].copy() if selected_markets else frame
        label_cols = [col for col in ["mercado_cluster", "cluster_id", "nombre_cluster"] if col in scope.columns]
        labels = scope[label_cols].drop_duplicates().sort_values(label_cols)
        valid_ids = set(labels["cluster_id"].astype(str)) if "cluster_id" in labels.columns else set()
        selected_ids = [value for value in selected_values(cluster_ids) if str(value) in valid_ids]
        return (
            [{"label": value, "value": value} for value in market_values],
            selected_markets,
            [
                {
                    "label": " | ".join(str(getattr(row, col)) for col in label_cols),
                    "value": str(getattr(row, "cluster_id")),
                }
                for row in labels.itertuples(index=False)
            ],
            selected_ids,
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
        client: str | None,
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
        selected = select_client(data["perfil"], data["perfil"], client)
        selected_code = None if selected is None else selected["cod_cliente"]
        base = filter_visual_operational_base(
            data,
            data["perfil"],
            selected_code,
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
        Input("product-select-all", "n_clicks"),
        Input("product-clear", "n_clicks"),
        State("client-product-filter", "value"),
    )
    def update_client_product_options(client: str | None, product_select_all_clicks: int | None, product_clear_clicks: int | None, current_value: list[str] | str | None):
        hist = data.get("historico_confirmado", pd.DataFrame())
        sales = data.get("ventas_semana", pd.DataFrame())
        if not client and not sales.empty and "producto" in sales.columns:
            ranked = sales.groupby("producto", dropna=False)["tallos_confirmados"].sum().sort_values(ascending=False)
            products = [str(idx) for idx in ranked.index if str(idx) and str(idx) != "nan"]
            options = [{"label": f"{product} | {moneyless_number(ranked.loc[product], 0)} tallos", "value": product} for product in products]
            value = synced_multi_value(current_value, products, "product-select-all", "product-clear")
            return options, value
        if not client or hist.empty or "producto" not in hist.columns:
            return [], []
        work = hist[hist["cod_cliente"] == str(client)].copy()
        ranked = work.groupby("producto", dropna=False)["tallos_historicos"].sum().sort_values(ascending=False)
        products = [str(idx) for idx in ranked.index if str(idx) and str(idx) != "nan"]
        options = [{"label": f"{product} | {moneyless_number(ranked.loc[product], 0)} tallos", "value": product} for product in products]
        value = synced_multi_value(current_value, products, "product-select-all", "product-clear")
        return options, value

    @app.callback(
        Output("client-color-filter", "options"),
        Output("client-color-filter", "value"),
        Input("client", "value"),
        Input("client-product-filter", "value"),
        Input("color-select-all", "n_clicks"),
        Input("color-clear", "n_clicks"),
        State("client-color-filter", "value"),
    )
    def update_client_color_options(client: str | None, product: list[str] | str | None, color_select_all_clicks: int | None, color_clear_clicks: int | None, current_value: list[str] | str | None):
        hist = data.get("historico_confirmado", pd.DataFrame())
        sales = data.get("ventas_semana", pd.DataFrame())
        if not client and not sales.empty and "color" in sales.columns:
            work = sales.copy()
            products = selected_values(product)
            if products and "producto" in work.columns:
                work = work[work["producto"].astype(str).isin(set(products))].copy()
            ranked = work.groupby("color", dropna=False)["tallos_confirmados"].sum().sort_values(ascending=False)
            colors = [str(idx) for idx in ranked.index if str(idx) and str(idx) != "nan"]
            options = [{"label": f"{color} | {moneyless_number(ranked.loc[color], 0)} tallos", "value": color} for color in colors]
            value = synced_multi_value(current_value, colors, "color-select-all", "color-clear")
            return options, value
        if not client or hist.empty or "color" not in hist.columns:
            return [], []
        work = hist[hist["cod_cliente"] == str(client)].copy()
        products = selected_values(product)
        if products and "producto" in work.columns:
            work = work[work["producto"].astype(str).isin(set(products))].copy()
        ranked = work.groupby("color", dropna=False)["tallos_historicos"].sum().sort_values(ascending=False)
        colors = [str(idx) for idx in ranked.index if str(idx) and str(idx) != "nan"]
        options = [{"label": f"{color} | {moneyless_number(ranked.loc[color], 0)} tallos", "value": color} for color in colors]
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
    def update_client_program_options(client: str | None, product: list[str] | str | None, color: list[str] | str | None, current_value: str | None):
        summary = data.get("sku_resumen", pd.DataFrame())
        hist = data.get("historico_confirmado", pd.DataFrame())
        if not summary.empty and "sku_operativo" in summary.columns and client:
            work = summary[summary["cod_cliente"] == str(client)].copy()
            products = selected_values(product)
            colors = selected_values(color)
            if products and "producto" in work.columns:
                work = work[work["producto"].astype(str).isin(set(products))].copy()
            if colors:
                comp = data.get("sku_composicion", pd.DataFrame())
                if not comp.empty and "color" in comp.columns:
                    valid_skus = comp[
                        (comp["cod_cliente"] == str(client))
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
        work = hist[hist["cod_cliente"] == str(client)].copy()
        if not client:
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
    def update_selected_sku_options(client: str | None, product: list[str] | str | None, color: list[str] | str | None, program: str | None, current_value: str | None):
        summary = data.get("sku_resumen", pd.DataFrame())
        hist = data.get("historico_confirmado", pd.DataFrame())
        if not summary.empty and "sku_operativo" in summary.columns and client:
            work = summary[summary["cod_cliente"] == str(client)].copy()
            products = selected_values(product)
            colors = selected_values(color)
            if products and "producto" in work.columns:
                work = work[work["producto"].astype(str).isin(set(products))].copy()
            if colors:
                comp = data.get("sku_composicion", pd.DataFrame())
                if not comp.empty and "color" in comp.columns:
                    valid_skus = comp[
                        (comp["cod_cliente"] == str(client))
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
        work = hist[hist["cod_cliente"] == str(client)].copy() if client else hist.copy()
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
        Input("general-sales-export-report", "n_clicks"),
        State("general-sales-base-year", "value"),
        State("general-sales-compare-year", "value"),
        State("general-sales-years", "value"),
        State("general-sales-week-range", "value"),
        State("general-sales-clients", "value"),
        State("general-sales-products", "value"),
        prevent_initial_call=True,
    )
    def export_general_sales_report(n_clicks, base_year, compare_year, years, week_range, clients, products):
        if not n_clicks:
            return dash.no_update
        sales = data.get("ventas_semana", pd.DataFrame())
        if sales.empty:
            return dash.no_update
        view = filter_general_sales_frame(sales, years, week_range, clients, products)
        if view.empty:
            return dash.no_update
        context = build_sales_executive_context_v2(view, base_year, compare_year)
        if not context.get("ok"):
            report_html = build_sales_report_html_v2(context)
        else:
            report_html = build_sales_report_html_v2(context)
        filename = f"informe_ejecutivo_ventas_{context.get('base_year', 'base')}_vs_{context.get('compare_year', 'comp')}.html"
        return dcc.send_string(report_html, filename=filename)

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
                .metric-card { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 14px; min-height: 84px; }
                .metric-card-comparison { min-height: 128px; }
                .metric-title { color: #667382; font-size: 12px; font-weight: 700; text-transform: uppercase; }
                .metric-value { font-size: 26px; line-height: 34px; font-weight: 800; color: #17202a; overflow-wrap: anywhere; }
                .metric-detail { color: #6f7c8a; font-size: 12px; }
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
                .panel { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 8px; min-width: 0; }
                .panel-title { font-size: 15px; font-weight: 800; padding: 8px 10px 0; }
                .table-panel { background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 12px; margin-top: 14px; }
                .no-top-margin { margin-top: 0; }
                .reading-panel { background: white; border: 1px solid #dfe5ec; border-left: 5px solid #800020; border-radius: 8px; padding: 10px 14px 16px; margin-bottom: 14px; }
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
            tipo.isin(["SURTIDO", "SURTIDO_M", "BULK"]) & base["frecuencia_ultimas_12_semanas"].ge(2),
            tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]) & base["frecuencia_ultimas_12_semanas"].ge(2),
            base["frecuencia_ultimas_12_semanas"].eq(0),
        ],
        ["PILOTO", "COMPRAR_COLOR_BASE", "REVISAR_COMPOSICION", "NO_ANTICIPAR"],
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
            work["tipo_upper"].isin(["SURTIDO", "SURTIDO_M", "RAINBOW", "COMBO", "BOUQUET", "BQT"]),
            work["tipo_upper"].eq("BULK"),
        ],
        [
            work.get("producto_color", work.get("sku_terminado", work["sku_operativo"])),
            work["sku_operativo"],
            (work["producto"].astype(str) + "|" + work["color"].astype(str)),
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
            tipo.isin(["SURTIDO", "SURTIDO_M"]),
            tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]),
            tipo.eq("BULK"),
        ],
        ["SKU terminado exacto", "Mezcla de colores/composicion", "Receta/composicion", "Producto-color volumen"],
        default="Revision manual",
    )
    base["recomendacion"] = np.select(
        [
            tipo.eq("SOLIDO") & base["semanas"].ge(2) & base["cumplimiento"].ge(0.9),
            tipo.eq("SOLIDO") & base["semanas"].ge(1),
            tipo.isin(["SURTIDO", "SURTIDO_M", "BULK"]) & base["semanas"].ge(2),
            tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]) & base["semanas"].ge(2),
        ],
        ["COMPRAR_TERMINADO", "PILOTO", "COMPRAR_COLOR_BASE", "REVISAR_COMPOSICION"],
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
            tipo.isin(["SURTIDO", "SURTIDO_M", "RAINBOW", "COMBO", "BOUQUET", "BQT"]),
            tipo.eq("BULK"),
        ],
        [
            work.get("producto_color", work.get("sku_terminado", work["sku_operativo"])),
            work["sku_operativo"],
            work["producto"].astype(str) + "|" + work["color"].astype(str),
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


def explain_similar_clients(sim_client: pd.DataFrame, hist: pd.DataFrame, selected_code: str) -> pd.DataFrame:
    if sim_client.empty or hist.empty:
        return sim_client
    selected_recent = hist[hist["cod_cliente"] == selected_code].copy()
    rows = []
    for row in sim_client.to_dict("records"):
        code = str(row.get("cod_cliente_similar", ""))
        other = hist[hist["cod_cliente"] == code].copy()
        reasons = []
        for col, label in [
            ("producto", "producto"),
            ("color", "color"),
            ("tipo_pedido_operativo", "tipo pedido"),
            ("tallos_x_ramo", "tallos/ramo"),
            ("capuchon", "capuchon"),
            ("empaque", "empaque"),
        ]:
            a = set(_top_values(selected_recent, col, n=3))
            b = set(_top_values(other, col, n=3))
            common = [x for x in a.intersection(b) if x and x != "sin_info"]
            if common:
                reasons.append(f"{label}: {', '.join(common[:2])}")
        row["razones_similitud"] = "; ".join(reasons) if reasons else "similitud por vectores de producto/color/tipo de pedido"
        rows.append(row)
    return pd.DataFrame(rows)


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

    similares = data["similares"]
    sim_client = similares[similares["cod_cliente_base"] == selected_code].head(20) if not similares.empty else pd.DataFrame()
    sim_cols = [
        "cod_cliente_similar",
        "cliente_similar",
        "similitud_total",
        "similitud_producto_color",
        "similitud_sku_flexible",
        "similitud_tipo_pedido",
        "compatibilidad_operativa",
    ]
    sim_client = sim_client[[col for col in sim_cols if col in sim_client.columns]]
    sim_client = explain_similar_clients(sim_client, hist, selected_code)

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
            html.Div([html.Div("Clientes similares y razones", className="panel-title"), make_table(sim_client, 8)], className="table-panel"),
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
    selected_code: str | None,
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
    selected_code: str | None,
    years: list[int] | None,
    week_range: list[int] | None,
    tipo_filter: list[str] | None,
    product_filter: list[str] | str | None,
    color_filter: list[str] | str | None,
) -> pd.DataFrame:
    if sales.empty:
        return sales
    out = sales.copy()
    if selected_code and "cod_cliente" in out.columns:
        out = out[out["cod_cliente"].astype(str).eq(str(selected_code))].copy()
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


NON_SOLID_TYPES = {"SURTIDO", "SURTIDO_M", "RAINBOW", "COMBO", "BOUQUET", "BQT", "MIX", "ASSORTED"}


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


def synced_multi_value(current_value, ordered_values: list[str], select_all_id: str, clear_id: str) -> list[str]:
    trigger_id = ctx.triggered_id
    if trigger_id == clear_id:
        return []
    if trigger_id == select_all_id:
        return ordered_values
    valid = set(ordered_values)
    return [item for item in selected_values(current_value) if item in valid]


def normalize_operational_type(series: pd.Series) -> pd.Series:
    return series.fillna("SIN_TIPO").astype(str).str.upper().str.replace("Ó", "O", regex=False).str.strip()


def ensure_visual_operational_sku(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    tipo = normalize_operational_type(out.get("tipo_pedido_operativo", pd.Series("SIN_TIPO", index=out.index)))
    fallback = out.get("sku_operativo", pd.Series("sin_info", index=out.index)).fillna("sin_info").astype(str)
    solid = out.get("producto_color", out.get("sku_terminado", fallback)).fillna(fallback).astype(str)
    nonsolid = out.get("receta_programa_key", out.get("sku_composicion", pd.Series("", index=out.index))).fillna("").astype(str)
    receta = out.get("receta_estructura_key", fallback).fillna(fallback).astype(str)
    nonsolid = nonsolid.where(~nonsolid.str.lower().isin(["", "nan", "none", "sin_info"]), receta)
    out["sku_operativo"] = np.where(tipo.eq("SOLIDO"), solid, nonsolid)
    out["tipo_operativo_norm"] = tipo
    out["es_solido"] = tipo.eq("SOLIDO")
    return out


def filter_visual_operational_base(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected_code: str | None,
    years: list[int] | None,
    week_range: list[int] | None,
    tipo_filter: list[str] | None,
    product_filter: list[str] | str | None,
    color_filter: list[str] | str | None,
    sku_filter: str | list[str] | None,
) -> pd.DataFrame:
    hist = data.get("historico_visualizador_comercial", data.get("historico_confirmado", pd.DataFrame()))
    if hist.empty:
        return pd.DataFrame()
    needed = [
        "fecha", "cod_cliente", "cliente", "pedido", "anio", "anio_iso", "semana_iso", "anio_semana",
        "tipo_pedido_operativo", "producto", "familia_analisis_operativa", "variedad", "color",
        "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque", "caja_operativa",
        "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta", "codempaque", "bulkbouquet",
        "tallos_analisis", "tallos_confirmados", "ventas_usd", "valor_total_original",
        "moneda_original", "sku_operativo", "sku_terminado", "sku_composicion", "receta_estructura_key",
    ]
    out = hist[[col for col in needed if col in hist.columns]].copy()
    if "anio" not in out.columns and "anio_iso" in out.columns:
        out["anio"] = out["anio_iso"]
    out = ensure_visual_operational_sku(out)
    if "tallos_pedidos" not in out.columns:
        out["tallos_pedidos"] = pd.to_numeric(out.get("tallos_analisis", 0), errors="coerce").fillna(0)
    for col in ["tallos_confirmados", "ventas_usd", "valor_total_original"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    valid_codes = set(filtered["cod_cliente"].astype(str)) if not filtered.empty and "cod_cliente" in filtered.columns else set()
    if selected_code and "cod_cliente" in out.columns:
        out = out[out["cod_cliente"].astype(str).eq(str(selected_code))].copy()
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
    return out


def summarize_visual_operational(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = df.groupby(group_cols, dropna=False, as_index=False).agg(
        tallos_confirmados=("tallos_confirmados", "sum"),
        tallos_pedidos=("tallos_pedidos", "sum"),
        ventas_usd=("ventas_usd", "sum"),
        pedidos=("pedido", "nunique") if "pedido" in df.columns else ("sku_operativo", "size"),
        cajas=("caja_operativa", "nunique") if "caja_operativa" in df.columns else ("sku_operativo", "size"),
        semanas_activas=("anio_semana", "nunique") if "anio_semana" in df.columns else ("sku_operativo", "size"),
    )
    out["precio_usd_tallo"] = (out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)).fillna(0)
    out["cumplimiento"] = (out["tallos_confirmados"] / out["tallos_pedidos"].replace(0, np.nan)).fillna(0).clip(0, 1)
    return out


def top_text(series: pd.Series, n: int = 3) -> str:
    values = series.dropna().astype(str)
    values = values[~values.str.lower().isin(["", "nan", "none", "sin_info"])]
    return ", ".join(values.value_counts().head(n).index)


def _first_non_empty(row: pd.Series, fields: list[str], default: str = "sin_info") -> str:
    for field in fields:
        value = row.get(field, "")
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "sin_info"}:
            return text
    return default


def _primary_value(value: str) -> str:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "sin_info"}:
        return "sin_info"
    return text.split(",")[0].split("|")[0].strip()


def _mean_numeric_text(series: pd.Series, decimals: int = 1) -> str:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return ""
    return moneyless_number(float(numeric.mean()), decimals)


def operational_sku_label(row: pd.Series, detail: bool = False) -> str:
    tipo = str(
        row.get("tipo_operativo_norm", row.get("tipo_pedido_operativo", "SIN_TIPO"))
    ).upper().replace("Ó", "O").replace("Ã“", "O").strip()

    producto = _first_non_empty(
        row,
        ["familia_analisis_operativa", "producto_familia", "producto"],
        "sin_producto",
    )

    color = _primary_value(
        _first_non_empty(row, ["color", "colores_internos"], "")
    )

    tipo_caja = _first_non_empty(row, ["tipo_caja"], "sin_caja")
    tallos_ramo = _first_non_empty(row, ["tallos_x_ramo", "tallos_por_ramo"], "sin_ramo")
    tallos_programa = _first_non_empty(row, ["tallos_programa_ramo"], "")
    tallos_caja_programa = _first_non_empty(row, ["tallos_programa_caja", "tallos_componentes_caja"], "")
    subtipo = _first_non_empty(
        row,
        ["subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta", "sku_composicion", "receta_estructura_key"],
        "sin_estructura",
    )
    receta_programa = _first_non_empty(row, ["receta", "receta_programa_key", "receta_estructura_key"], "")

    # REGLA LGF:
    # SOLIDO: el color sí hace parte del SKU visible.
    # NO SOLIDO: surtidos, rainbow, combo, bouquet, bulk, etc. se leen como estructura del pedido.
    if tipo == "SOLIDO":
        parts = [tipo, producto, color]

        if detail:
            parts.extend([tipo_caja, f"{tallos_ramo} tallos/ramo"])

            variedad = _first_non_empty(row, ["variedad", "variedades_internas"], "")
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

        return " | ".join([p for p in parts if p and str(p).lower() not in {"nan", "none", "sin_info", "sin_color"}])

    # Para NO sólidos se vuelve a la estructura del pedido.
    # Aquí NO se mete color en el SKU visible.
    parts = [tipo, producto]
    if receta_programa:
        parts.append(receta_programa)
    else:
        parts.extend([tipo_caja, f"{tallos_ramo} tallos/ramo"])
    if tallos_programa and str(tallos_programa).lower() not in {"nan", "none", "sin_info", "0", "0.0"}:
        parts.append(f"{tallos_programa} tallos/ramo")
    if detail and tallos_caja_programa and str(tallos_caja_programa).lower() not in {"nan", "none", "sin_info", "0", "0.0"}:
        parts.append(f"{tallos_caja_programa} tallos/caja")

    if detail:
        parts.append(subtipo)

        variedad = _first_non_empty(row, ["variedad", "variedades_internas"], "")
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

    return " | ".join([p for p in parts if p and str(p).lower() not in {"nan", "none", "sin_info", "sin_color"}])


def operational_sku_filter_label(row: pd.Series) -> str:
    tipo = str(
        row.get("tipo_operativo_norm", row.get("tipo_pedido_operativo", "SIN_TIPO"))
    ).upper().replace("Ó", "O").replace("Ã“", "O").strip()

    producto = _first_non_empty(
        row,
        ["familia_analisis_operativa", "producto_familia", "producto"],
        "",
    )

    color = _primary_value(
        _first_non_empty(row, ["color", "colores_internos"], "")
    )

    tipo_caja = _first_non_empty(row, ["tipo_caja"], "")
    tallos_ramo = _first_non_empty(row, ["tallos_x_ramo", "tallos_por_ramo"], "")
    tallos_programa = _first_non_empty(row, ["tallos_programa_ramo"], "")

    # SOLIDO: color sí identifica el SKU.
    if tipo == "SOLIDO":
        parts = [p for p in [tipo, producto, color] if p and str(p).lower() not in {"nan", "none", "sin_info", "sin_color"}]
        return " | ".join(parts) if parts else _first_non_empty(row, ["sku_operativo"], "sin_sku")

    # NO SOLIDO: se identifica por estructura general, no por color.
    parts = [p for p in [tipo, producto, _first_non_empty(row, ["receta", "receta_programa_key", "receta_estructura_key"], "") or tipo_caja] if p and str(p).lower() not in {"nan", "none", "sin_info", "sin_color"}]
    if tallos_programa and str(tallos_programa).lower() not in {"nan", "none", "sin_info", "0", "0.0"}:
        parts.append(f"{tallos_programa} tallos/ramo")

    if not _first_non_empty(row, ["receta", "receta_programa_key", "receta_estructura_key"], "") and tallos_ramo and str(tallos_ramo).lower() not in {"nan", "none", "sin_info", "sin_ramo"}:
        parts.append(f"{tallos_ramo} tallos/ramo")

    return " | ".join(parts) if parts else _first_non_empty(row, ["sku_operativo"], "sin_sku")


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
    if not sku and not multi_selected and not ranking.empty:
        sku = str(ranking.iloc[0]["sku_operativo"])
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
    return out.sort_values("tallos_confirmados", ascending=False)


def visual_recent_history(df: pd.DataFrame, analysis_week: int, top_n: int, sku_view_mode: str = "general") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    week = int(analysis_week or pd.to_numeric(work["semana_iso"], errors="coerce").max() or 1)
    grouped = work.groupby(["sku_operativo", "tipo_pedido_operativo", "semana_iso"], dropna=False, as_index=False)["tallos_confirmados"].sum()
    pivot = grouped.pivot_table(index=["sku_operativo", "tipo_pedido_operativo"], columns="semana_iso", values="tallos_confirmados", aggfunc="sum", fill_value=0).reset_index()
    for offset in range(4):
        col = week - offset
        label = "Semana actual" if offset == 0 else f"Semana -{offset}"
        pivot[label] = pivot[col] if col in pivot.columns else 0
    last_12 = work[pd.to_numeric(work["semana_iso"], errors="coerce").between(max(1, week - 11), week)]
    avg = summarize_visual_operational(last_12, ["sku_operativo"]).rename(columns={"tallos_confirmados": "promedio_ultimas_12"})
    avg["promedio_ultimas_12"] = avg["promedio_ultimas_12"] / max(last_12["anio_semana"].nunique(), 1) if not last_12.empty else 0
    total = work["tallos_confirmados"].sum()
    total_sku = summarize_visual_operational(work, ["sku_operativo"])[["sku_operativo", "tallos_confirmados", "precio_usd_tallo"]]
    sku_meta = work.groupby(["sku_operativo"], dropna=False, as_index=False).agg(
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
    out = pivot.merge(avg[["sku_operativo", "promedio_ultimas_12"]], on="sku_operativo", how="left").merge(total_sku, on="sku_operativo", how="left").merge(sku_meta, on="sku_operativo", how="left")
    out["participacion"] = out["tallos_confirmados"] / total if total else 0
    out["variacion_vs_promedio"] = (out["Semana actual"] / out["promedio_ultimas_12"].replace(0, np.nan) - 1).fillna(0)
    out["sku_operativo_general"] = out.apply(lambda row: operational_sku_label(row, detail=False), axis=1)
    out["sku_operativo_detalle"] = out.apply(lambda row: operational_sku_label(row, detail=True), axis=1)
    out["sku_operativo_visible"] = out["sku_operativo_general"] if str(sku_view_mode or "general").lower() != "detalle" else out["sku_operativo_detalle"]
    cols = ["sku_operativo_visible", "sku_operativo_general", "sku_operativo_detalle", "tipo_pedido_operativo", "producto", "variedad", "capuchon", "comida", "empaque", "tipo_caja", "tallos_x_ramo", "ramos_x_caja", "caja_operativa", "Semana actual", "Semana -1", "Semana -2", "Semana -3", "promedio_ultimas_12", "participacion", "variacion_vs_promedio", "precio_usd_tallo"]
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
        "promedio_ultimas_12": "Promedio ultimas 12 semanas",
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
    for col in ["Tallos confirmados", "Tallos pedidos", "Pedidos", "Cajas", "Semanas activas", "Semana actual", "Semana -1", "Semana -2", "Semana -3", "Promedio ultimas 12 semanas"]:
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
    selected_products = selected_values(products)
    if selected_products and "producto" in out.columns:
        out = out[out["producto"].astype(str).isin(selected_products)].copy()
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
    compare_projected_usd = compare_metrics["ventas_usd"] if compare_weeks >= 52 else compare_metrics["ventas_usd"] / compare_weeks * 52
    compare_projected_tallos = compare_metrics["tallos_confirmados"] if compare_weeks >= 52 else compare_metrics["tallos_confirmados"] / compare_weeks * 52
    compare_projected_price = compare_projected_usd / compare_projected_tallos if compare_projected_tallos > 0 else 0.0

    monthly = pd.concat(
        [
            base_frame.assign(ano_tipo="Año base"),
            compare_frame.assign(ano_tipo="Año comparativo"),
        ],
        ignore_index=True,
    )
    monthly["mes_num"] = pd.to_numeric(monthly["mes_num"], errors="coerce").fillna(0).astype(int)
    monthly = summarize_sales_frame(monthly, ["ano_tipo", "mes_num"]).sort_values(["ano_tipo", "mes_num"])
    monthly["Mes"] = monthly["mes_num"].map(_month_label)
    monthly["Año"] = monthly["ano_tipo"]

    product_summary = pd.concat(
        [
            base_frame.groupby("producto", dropna=False, as_index=False).agg(
                tallos_base=("tallos_confirmados", "sum"),
                ventas_base=("ventas_usd", "sum"),
            ).assign(Ano="Año base"),
            compare_frame.groupby("producto", dropna=False, as_index=False).agg(
                tallos_compare=("tallos_confirmados", "sum"),
                ventas_compare=("ventas_usd", "sum"),
            ).assign(Ano="Año comparativo"),
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
        for year_name in ["Año base", "Año comparativo"]:
            subset = monthly[monthly["Año"].eq(year_name)]
            monthly_fig.add_trace(
                go.Bar(
                    x=subset["Mes"],
                    y=subset["ventas_usd"],
                    name=year_name,
                )
            )
        monthly_fig.update_layout(barmode="group", title="Facturación USD por mes")
        monthly_fig.update_yaxes(title="Ventas USD")
        monthly_fig.update_xaxes(title="Mes")
        apply_common_layout(monthly_fig, 360)
    else:
        monthly_fig = empty_figure("Facturación USD por mes")

    product_bar_fig = go.Figure()
    compare_top = product_compare.head(10).copy()
    if not compare_top.empty:
        product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_base"], name="Año base"))
        product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_compare"], name="Año comparativo"))
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
        title=f"Mix de tallos del año comparativo {compare_year}",
    ) if not mix_donut.empty else empty_figure("Mix por producto")
    if not mix_donut.empty:
        apply_pie_label_style(mix_fig)
        apply_common_layout(mix_fig, 360)

    consolidated_table = pd.DataFrame(
        [
            {"Año": f"Año base {base_year}", "Tipo de dato": "Real", "Total USD": base_metrics["ventas_usd"]},
            {"Año": f"Año comparativo {compare_year}", "Tipo de dato": "Real", "Total USD": compare_metrics["ventas_usd"]},
            {
                "Año": f"Año comparativo {compare_year}",
                "Tipo de dato": "Proyección simple",
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
            f"La proyeccion del año comparativo estima una diferencia de {moneyless_number(consolidated_delta, 2)} USD frente al año base, equivalente a {percent(consolidated_delta_pct)} y {compare_growth_mult:.2f}x."
        )
    insights = insights[:6]

    context.update(
        {
            "ok": True,
            "message": "",
            "monthly_fig": monthly_fig,
            "mix_fig": mix_fig,
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
    weekly_note = "Incluye lectura semanal detallada al final de la pestaña en el dashboard."
    return f"""
    <html><head><meta charset="utf-8">{style}</head><body>
    <h1>Informe ejecutivo de Ventas Generales</h1>
    <div class="meta">Comparación: año base {base_year} vs año comparativo {compare_year}</div>
    <div class="cards">
      <div class="card"><div class="label">Facturación año base</div><div class="value">{moneyless_number(base_metrics['ventas_usd'], 2)}</div><div class="sub">USD</div></div>
      <div class="card"><div class="label">Facturación comparativa</div><div class="value">{moneyless_number(context['compare_projected_usd'], 2)}</div><div class="sub">USD proyectados / reales</div></div>
      <div class="card"><div class="label">Diferencia absoluta</div><div class="value">{moneyless_number(context['consolidated_delta'], 2)}</div><div class="sub">USD</div></div>
      <div class="card"><div class="label">Crecimiento</div><div class="value">{percent(context['consolidated_delta_pct'])}</div><div class="sub">{context['compare_growth_mult']:.2f}x</div></div>
    </div>
    <div class="grid2">
      <div class="panel"><h3>Resumen de facturación USD</h3>{monthly_html}</div>
      <div class="panel"><h3>Mix por producto</h3>{mix_html}</div>
    </div>
    <div class="grid2">
      <div class="panel"><h3>Tallos por producto</h3>{product_html}</div>
      <div class="panel"><h3>Consolidado y proyección</h3>{consolidated_table.to_html(index=False, escape=False)}</div>
    </div>
    <div class="panel">
      <h2>Insights automáticos</h2>
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
) -> html.Div:
    """Present sales totals from the weekly aggregate without recipe-level detail."""
    sales = data.get("ventas_semana", pd.DataFrame())
    if sales.empty:
        return html.Div(
            "No existe ventas_semana_cliente_producto.csv. Ejecuta descriptivos para habilitar Ventas generales.",
            className="table-panel",
        )
    view = filter_general_sales_frame(sales, years, week_range, clients, products)
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
                        "Muestra tallos, ventas USD y precio ponderado; para composicion detallada usa Visualizador clientes general."
                    ),
                    html.Div(
                        [
                            make_card("Tallos confirmados", moneyless_number(tallos), "periodo filtrado"),
                            make_card("Ventas USD", moneyless_number(ventas, 2), "periodo filtrado"),
                            make_card("Precio promedio", moneyless_number(precio, 4), "USD/tallo ponderado"),
                            make_card("Semanas ISO", weeks_text, "filtro activo"),
                            make_card("Clientes", selected_label(clients, "Todos"), "filtro activo"),
                            make_card("Productos", selected_label(products, "Todos"), "filtro activo"),
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
    base_weeks = max(int(base_frame["semana_iso"].nunique()), 1) if "semana_iso" in base_frame.columns else 1
    compare_weeks = max(int(compare_frame["semana_iso"].nunique()), 1) if "semana_iso" in compare_frame.columns else 1

    compare_projected_usd = compare_metrics["ventas_usd"] if compare_weeks >= 52 else compare_metrics["ventas_usd"] / compare_weeks * 52
    compare_projected_tallos = compare_metrics["tallos_confirmados"] if compare_weeks >= 52 else compare_metrics["tallos_confirmados"] / compare_weeks * 52
    compare_projected_price = compare_projected_usd / compare_projected_tallos if compare_projected_tallos > 0 else 0.0

    monthly = pd.concat(
        [
            base_frame.assign(ano_label=f"Ano base {int(base_year)}"),
            compare_frame.assign(ano_label=f"Ano comparativo {int(compare_year)}"),
        ],
        ignore_index=True,
    )
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
    for year_label in [f"Ano base {int(base_year)}", f"Ano comparativo {int(compare_year)}"]:
        subset = monthly[monthly["ano_label"].eq(year_label)]
        monthly_fig.add_trace(go.Bar(x=subset["Mes"], y=subset["ventas_usd"], name=year_label))
    monthly_fig.update_layout(barmode="group", title="Facturacion USD por mes")
    monthly_fig.update_yaxes(title="Ventas USD")
    monthly_fig.update_xaxes(title="Mes")
    apply_common_layout(monthly_fig, 360)

    mix_fig = px.pie(mix_donut, names="producto", values="tallos_compare", hole=0.42, title=f"Mix de tallos del ano comparativo {compare_year}")
    apply_pie_label_style(mix_fig)
    apply_common_layout(mix_fig, 360)

    compare_top = product_compare.head(10).copy()
    product_bar_fig = go.Figure()
    product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_base"], name=f"Ano base {base_year}"))
    product_bar_fig.add_trace(go.Bar(x=compare_top["producto"], y=compare_top["tallos_compare"], name=f"Ano comparativo {compare_year}"))
    product_bar_fig.update_layout(barmode="group", title="Tallos por producto: base vs comparativo")
    product_bar_fig.update_yaxes(title="Tallos confirmados")
    product_bar_fig.update_xaxes(title="Producto")
    apply_common_layout(product_bar_fig, 370)

    consolidated_table = pd.DataFrame(
        [
            {"Ano": f"Ano base {base_year}", "Tipo de dato": "Real", "Total USD": base_metrics["ventas_usd"]},
            {"Ano": f"Ano comparativo {compare_year}", "Tipo de dato": "Real", "Total USD": compare_metrics["ventas_usd"]},
            {"Ano": f"Ano comparativo {compare_year}", "Tipo de dato": "Proyeccion simple", "Total USD": compare_projected_usd},
        ]
    )
    consolidated_fig = go.Figure()
    consolidated_fig.add_trace(go.Bar(x=consolidated_table["Ano"], y=consolidated_table["Total USD"], marker_color=["#800020", "#4E79A7", "#59A14F"]))
    consolidated_fig.update_layout(title="Consolidado y proyeccion USD", showlegend=False)
    consolidated_fig.update_yaxes(title="USD")
    apply_common_layout(consolidated_fig, 330)

    consolidated_delta = compare_projected_usd - base_metrics["ventas_usd"]
    consolidated_delta_pct = consolidated_delta / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan
    compare_real_delta = compare_metrics["ventas_usd"] - base_metrics["ventas_usd"]
    compare_real_pct = compare_real_delta / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan
    compare_real_mult = compare_metrics["ventas_usd"] / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan
    compare_growth_mult = compare_projected_usd / base_metrics["ventas_usd"] if base_metrics["ventas_usd"] > 0 else np.nan

    product_leader = mix_donut.sort_values("share", ascending=False).iloc[0] if not mix_donut.empty else None
    product_grower = product_compare.sort_values("delta_usd_pct", ascending=False).iloc[0] if not product_compare.empty else None
    product_decliner = product_compare.sort_values("delta_usd_pct", ascending=True).iloc[0] if not product_compare.empty else None
    insights = [f"La comparacion usa {base_weeks} semanas del ano base y {compare_weeks} semanas del ano comparativo dentro del alcance filtrado."]
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
            "mix_fig": mix_fig,
            "product_bar_fig": product_bar_fig,
            "consolidated_fig": consolidated_fig,
            "consolidated_table": consolidated_table,
            "product_compare": product_compare,
            "base_metrics": base_metrics,
            "compare_metrics": compare_metrics,
            "compare_projected_usd": compare_projected_usd,
            "compare_projected_tallos": compare_projected_tallos,
            "compare_projected_price": compare_projected_price,
            "consolidated_delta": consolidated_delta,
            "consolidated_delta_pct": consolidated_delta_pct,
            "compare_real_delta": compare_real_delta,
            "compare_real_pct": compare_real_pct,
            "compare_real_mult": compare_real_mult,
            "compare_growth_mult": compare_growth_mult,
            "insights": insights,
            "base_year": int(base_year),
            "compare_year": int(compare_year),
            "week_text": f"{int(view['semana_iso'].min())}-{int(view['semana_iso'].max())}" if "semana_iso" in view.columns else "todas",
        }
    )
    return context


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
    consolidated_table = context["consolidated_table"].copy()
    consolidated_table["Total USD"] = consolidated_table["Total USD"].map(lambda value: moneyless_number(value, 2))

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
      <div class="panel"><h3>Consolidado y proyeccion</h3>{consolidated_html}</div>
    </div>
    <div class="panel">
      <h2>Tabla consolidada</h2>
      {consolidated_table.to_html(index=False, escape=False)}
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
    clients: list[str] | None,
    products: list[str] | None,
) -> html.Div:
    """Executive sales tab with yearly comparison and weekly context."""
    sales = data.get("ventas_semana", pd.DataFrame())
    if sales.empty:
        return html.Div("No existe ventas_semana_cliente_producto.csv. Ejecuta descriptivos para habilitar Ventas generales.", className="table-panel")

    view = filter_general_sales_frame(sales, years, week_range, clients, products)
    if view.empty:
        available_years = sorted(pd.to_numeric(sales["anio"], errors="coerce").dropna().astype(int).unique().tolist()) if "anio" in sales.columns else []
        years_text = ", ".join(map(str, available_years)) if available_years else "sin anos disponibles"
        return html.Div(
            [
                html.Div("Ventas generales", className="panel-title"),
                panel_note(
                    f"No hay ventas para los filtros seleccionados. Años disponibles en esta base: {years_text}. "
                    "Revisa el rango de semanas, el cliente o el producto seleccionado."
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

    ventas_fig = px.line(weekly, x="semana_iso", y="ventas_usd", color="anio", markers=True, title="Ventas USD por semana")
    ventas_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="Ventas USD")
    apply_common_layout(ventas_fig, 370)

    precio_fig = px.line(weekly, x="semana_iso", y="precio_usd_tallo", color="anio", markers=True, title="Precio promedio USD/tallo por semana")
    precio_fig.update_layout(xaxis_title="Semana ISO", yaxis_title="USD/tallo")
    apply_common_layout(precio_fig, 345)

    annual_display = annual.rename(columns={"anio": "Ano", "tallos_confirmados": "Tallos confirmados", "ventas_usd": "Ventas USD", "precio_usd_tallo": "USD/tallo"})[["Ano", "Tallos confirmados", "Ventas USD", "USD/tallo"]].copy()
    annual_display["Tallos confirmados"] = annual_display["Tallos confirmados"].map(moneyless_number)
    annual_display["Ventas USD"] = annual_display["Ventas USD"].map(lambda value: moneyless_number(value, 2))
    annual_display["USD/tallo"] = annual_display["USD/tallo"].map(lambda value: moneyless_number(value, 4))
    weeks_text = f"{int(week_range[0])}-{int(week_range[1])}" if week_range and len(week_range) == 2 else "todas"

    export_button = html.Button(
        "Exportar informe ejecutivo",
        id="general-sales-export-report",
        n_clicks=0,
        type="button",
        style={"border": "1px solid #800020", "background": "#800020", "color": "white", "borderRadius": "6px", "padding": "10px 14px", "fontWeight": "700", "cursor": "pointer"},
    )

    executive_metrics = [
        make_card("Facturacion base", moneyless_number(context["base_metrics"]["ventas_usd"] if context.get("ok") else ventas, 2), f"Ano {base_year if base_year is not None else 'seleccionado'}"),
        make_card("Facturacion comparativa", moneyless_number(context["compare_metrics"]["ventas_usd"] if context.get("ok") else ventas, 2), f"Ano {compare_year if compare_year is not None else 'seleccionado'}"),
        make_card("Diferencia USD", moneyless_number(context["compare_real_delta"] if context.get("ok") else 0, 2), "comparacion real"),
        make_card("Crecimiento", percent(context["compare_real_pct"]) if context.get("ok") else "0.0%", f"{context['compare_real_mult']:.2f}x" if context.get("ok") and pd.notna(context.get("compare_real_mult")) else "sin dato"),
    ]

    report_panel = html.Div(
        [
            html.Div(
                [
                    html.Div("Informe ejecutivo comercial", className="panel-title"),
                    panel_note("Compara dos anos seleccionados sobre el mismo alcance filtrado. Mantiene la lectura semanal y agrega un resumen ejecutivo de facturacion, mix y consolidado."),
                    export_button,
                ]
            ),
            html.Div(executive_metrics, className="metrics-grid"),
            html.Div(
                [
                    html.Div([html.Div("Resumen mensual USD", className="panel-title"), panel_note("Comparacion mensual del ano base frente al comparativo."), dcc.Graph(figure=context["monthly_fig"] if context.get("ok") else empty_figure("Facturacion USD por mes"))], className="panel"),
                    html.Div([html.Div("Mix por producto", className="panel-title"), panel_note("Producto dominante del ano comparativo y su participacion en tallos."), dcc.Graph(figure=context["mix_fig"] if context.get("ok") else empty_figure("Mix por producto"))], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([html.Div("Tallos por producto", className="panel-title"), panel_note("Base vs comparativo por producto. La tabla de apoyo muestra la variacion absoluta y porcentual."), dcc.Graph(figure=context["product_bar_fig"] if context.get("ok") else empty_figure("Tallos por producto"))], className="panel"),
                    html.Div([html.Div("Consolidado y proyeccion", className="panel-title"), panel_note("Real del ano base, real del comparativo y proyeccion simple anualizada del comparativo."), dcc.Graph(figure=context["consolidated_fig"] if context.get("ok") else empty_figure("Consolidado y proyeccion USD"))], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div("Tabla resumida consolidado / proyeccion", className="panel-title"),
                    panel_note("Ano, tipo de dato y total USD para lectura ejecutiva rapida."),
                    make_table(context["consolidated_table"] if context.get("ok") else pd.DataFrame(), 8),
                ],
                className="table-panel section-gap",
            ),
            html.Div(
                [
                    html.Div("Insights automaticos", className="panel-title"),
                    panel_note("Frases ejecutivas calculadas automaticamente a partir de la comparacion seleccionada."),
                    html.Ul([html.Li(item) for item in (context["insights"] if context.get("ok") else ["No hay suficientes datos para construir la comparacion ejecutiva."])], className="insights-list"),
                ],
                className="table-panel section-gap",
            ),
        ],
        className="table-panel",
    )

    weekly_panel = html.Div(
        [
            html.Div("Lectura semanal complementaria", className="panel-title"),
            panel_note("Mantiene el foco semanal para validar nivel y estacionalidad dentro del informe."),
            html.Div([html.Div(dcc.Graph(figure=tallos_fig), className="panel"), html.Div(dcc.Graph(figure=ventas_fig), className="panel")], className="grid-2 section-gap"),
            html.Div(
                [
                    html.Div(dcc.Graph(figure=precio_fig), className="panel"),
                    html.Div([html.Div("Resumen por ano", className="panel-title"), panel_note("Totales del periodo semanal seleccionado; el precio no es promedio simple, se pondera por tallos."), make_table(annual_display, 8)], className="table-panel no-top-margin"),
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
    hist = data.get("historico_visualizador_comercial", data.get("historico_confirmado", pd.DataFrame()))
    if hist.empty:
        return html.Div(
            "Falta historico_visualizador_comercial.csv o historico_confirmado.csv para construir el visualizador por SKU operativo.",
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
    if composition.empty:
        comp_fig = empty_figure("Composicion interna de colores del SKU")
    else:
        comp_fig = px.bar(
            composition,
            x="color_interno",
            y="participacion",
            color="color_interno",
            color_discrete_map=color_map_for(composition, "color_interno"),
            hover_data=["sku_operativo", "tallos_confirmados", "ventas_usd", "precio_usd_tallo"],
            title="Composicion interna de colores del SKU",
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
        view_note = "Vista no solidos: el ranking prioriza la estructura del pedido; el color queda como composicion interna."
    else:
        view_note = "Vista todos los tipos: no se mezclan solidos y no solidos como producto + color."
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
                    html.Div([html.Div("Composicion interna por color", className="panel-title"), make_table(format_operational_display(composition), 12)], className="table-panel no-top-margin"),
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


def cluster_natural_reading(
    clusters: pd.DataFrame,
    cluster_summary: pd.DataFrame,
    block_profile: pd.DataFrame,
    differentiators: pd.DataFrame,
    tipo_mix: pd.DataFrame,
) -> html.Div:
    if clusters.empty:
        return html.Div("No hay clusters visibles para construir la lectura.", className="reading-text")

    markets = sorted(clusters["mercado_cluster"].dropna().astype(str).unique()) if "mercado_cluster" in clusters.columns else []
    market_label = ", ".join(markets[:3]) + (f" y {len(markets) - 3} mas" if len(markets) > 3 else "")
    n_clients = clusters["cod_cliente"].nunique() if "cod_cliente" in clusters.columns else len(clusters)
    n_clusters = clusters["cluster_id"].nunique() if "cluster_id" in clusters.columns else 0
    tallos = clusters["tallos_total"].sum() if "tallos_total" in clusters.columns else 0

    top_product = _top_values(clusters, "producto_dominante", value_col="tallos_total", n=3)
    top_color = _top_values(clusters, "color_dominante", value_col="tallos_total", n=3)
    top_type = _top_values(clusters, "tipo_pedido_dominante", value_col="tallos_total", n=3)

    block_text = "sin bloque dominante claro"
    if not block_profile.empty and "bloque_que_mas_diferencia" in block_profile.columns:
        block_counts = block_profile["bloque_que_mas_diferencia"].dropna().astype(str).value_counts()
        if not block_counts.empty:
            block_text = ", ".join([f"{idx} ({val})" for idx, val in block_counts.head(3).items()])

    strongest_cluster = ""
    if not cluster_summary.empty:
        top_cluster = cluster_summary.sort_values(["clientes", "tallos"], ascending=False).iloc[0]
        strongest_cluster = (
            f"El cluster con mas clientes es {top_cluster.get('cluster_id', 'sin_cluster')} "
            f"({top_cluster.get('nombre_cluster', 'sin nombre')}), con "
            f"{moneyless_number(top_cluster.get('clientes', 0))} clientes."
        )

    diff_text = ""
    if not differentiators.empty:
        top_diff = differentiators.sort_values("importancia_modelo", ascending=False).head(5)
        readable = top_diff.get("lectura_variable", top_diff.get("variable", pd.Series(dtype=str))).dropna().astype(str).tolist()
        if readable:
            diff_text = "Variables que mas explican la separacion: " + "; ".join(readable[:5]) + "."

    type_text = ""
    if not tipo_mix.empty and "tipo_pedido_dominante" in tipo_mix.columns:
        type_counts = tipo_mix.groupby("tipo_pedido_dominante", dropna=False)["clientes"].sum().sort_values(ascending=False)
        if not type_counts.empty:
            type_text = "Tipo de pedido dominante en los clusters visibles: " + ", ".join(
                [f"{idx} ({int(val)} clientes)" for idx, val in type_counts.head(4).items()]
            ) + "."

    operations = []
    if "cv_volumen" in clusters.columns:
        cv_avg = pd.to_numeric(clusters["cv_volumen"], errors="coerce").mean()
        if pd.notna(cv_avg):
            operations.append(f"variabilidad promedio {moneyless_number(cv_avg, 2)}")
    if "share_top3_color" in clusters.columns:
        color_avg = pd.to_numeric(clusters["share_top3_color"], errors="coerce").mean()
        if pd.notna(color_avg):
            operations.append(f"concentracion color top 3 {percent(color_avg)}")
    if "share_top1_tipo_pedido" in clusters.columns:
        type_avg = pd.to_numeric(clusters["share_top1_tipo_pedido"], errors="coerce").mean()
        if pd.notna(type_avg):
            operations.append(f"concentracion tipo pedido {percent(type_avg)}")

    typology_paragraphs = []
    if not cluster_summary.empty:
        visible_summary = cluster_summary.sort_values(["clientes", "tallos"], ascending=False).head(8).copy()
        for _, cluster_row in visible_summary.iterrows():
            cluster_id = str(cluster_row.get("cluster_id", "sin_cluster"))
            cluster_clients = clusters[clusters["cluster_id"].astype(str).eq(cluster_id)].copy()
            if cluster_clients.empty:
                continue
            cluster_block = block_profile[block_profile["cluster_id"].astype(str).eq(cluster_id)].copy() if not block_profile.empty else pd.DataFrame()
            cluster_diff = differentiators[differentiators["cluster_id"].astype(str).eq(cluster_id)].copy() if not differentiators.empty else pd.DataFrame()
            products = _top_values(cluster_clients, "producto_dominante", value_col="tallos_total", n=2)
            colors = _top_values(cluster_clients, "color_dominante", value_col="tallos_total", n=2)
            types = _top_values(cluster_clients, "tipo_pedido_dominante", value_col="tallos_total", n=2)
            block = ""
            block_vars = ""
            if not cluster_block.empty:
                block = str(cluster_block.iloc[0].get("bloque_que_mas_diferencia", "") or "")
                block_vars = str(cluster_block.iloc[0].get("variables_clave_bloque", "") or "")
            diff_vars = []
            if not cluster_diff.empty:
                diff_vars = cluster_diff.sort_values("importancia_modelo", ascending=False)["lectura_variable"].dropna().astype(str).head(3).tolist()
            avg_cv = pd.to_numeric(cluster_clients.get("cv_volumen", pd.Series(dtype=float)), errors="coerce").mean()
            avg_color = pd.to_numeric(cluster_clients.get("share_top3_color", pd.Series(dtype=float)), errors="coerce").mean()
            avg_type = pd.to_numeric(cluster_clients.get("share_top1_tipo_pedido", pd.Series(dtype=float)), errors="coerce").mean()
            if pd.notna(avg_cv) and avg_cv <= 0.55:
                constancy = "bastante constantes"
            elif pd.notna(avg_cv) and avg_cv <= 1.0:
                constancy = "de constancia media"
            else:
                constancy = "mas variables"
            if pd.notna(avg_color) and avg_color >= 0.75:
                color_style = "muy concentrados en pocos colores"
            elif pd.notna(avg_color) and avg_color >= 0.50:
                color_style = "con una mezcla de colores moderadamente concentrada"
            else:
                color_style = "con mezcla de colores amplia"
            if pd.notna(avg_type) and avg_type >= 0.85:
                type_style = "compran casi siempre el mismo tipo de pedido"
            elif pd.notna(avg_type) and avg_type >= 0.60:
                type_style = "tienen un formato de pedido dominante, aunque con algunas variaciones"
            else:
                type_style = "mezclan varios formatos de pedido"
            commercial_use = []
            if constancy == "bastante constantes" and pd.notna(avg_color) and avg_color >= 0.60 and pd.notna(avg_type) and avg_type >= 0.70:
                commercial_use.append("son buenos candidatos para ofertas recurrentes, acuerdos por programa y planeacion anticipada")
            elif constancy == "bastante constantes":
                commercial_use.append("conviene trabajarlos con seguimiento comercial periodico, porque repiten compra aunque su mix puede variar")
            else:
                commercial_use.append("conviene tratarlos como clientes de oportunidad o campana, validando mix antes de anticipar compromisos")
            if block == "color":
                commercial_use.append("la conversacion comercial debe partir del color dominante y sustitutos cercanos")
            elif block == "producto":
                commercial_use.append("la conversacion comercial debe partir del portafolio/producto dominante")
            elif block == "tipo_pedido":
                commercial_use.append("la oportunidad esta en vender por formato operativo, no solo por producto")
            elif block == "constancia":
                commercial_use.append("la prioridad es entender ritmo de compra y semanas activas")
            if pd.notna(avg_color) and avg_color >= 0.75:
                commercial_use.append("sirven para propuestas muy enfocadas en pocos colores")
            if pd.notna(avg_type) and avg_type >= 0.85:
                commercial_use.append("pueden recibir ofertas empaquetadas por el mismo tipo de pedido")

            typology_paragraphs.append(
                (
                    f"{cluster_id}: {moneyless_number(cluster_clients['cod_cliente'].nunique())} clientes "
                    f"{constancy}, {color_style} y que {type_style}. "
                    f"Predominan productos como {', '.join(products) if products else 'sin producto claro'}, "
                    f"colores como {', '.join(colors) if colors else 'sin color claro'} y tipos de pedido "
                    f"{', '.join(types) if types else 'sin tipo claro'}. "
                    f"El bloque que mas los separa es {block or 'no identificado'}"
                    f"{f' ({block_vars})' if block_vars else ''}. "
                    f"Variables clave: {', '.join(diff_vars) if diff_vars else 'sin variables diferenciadoras claras'}. "
                    f"Insight comercial: {'; '.join(commercial_use)}."
                )
            )

    paragraphs = [
        f"Lectura para {market_label or 'los mercados visibles'}: hay {moneyless_number(n_clients)} clientes distribuidos en {moneyless_number(n_clusters)} clusters, con {moneyless_number(tallos)} tallos analizados.",
        strongest_cluster,
        f"Los bloques que mas diferencian los clusters visibles son: {block_text}.",
        f"Los productos dominantes mas frecuentes son {', '.join(top_product) if top_product else 'sin informacion'}; los colores dominantes mas frecuentes son {', '.join(top_color) if top_color else 'sin informacion'}; y los tipos de pedido mas frecuentes son {', '.join(top_type) if top_type else 'sin informacion'}.",
        type_text,
        diff_text,
        "Indicadores operativos visibles: " + "; ".join(operations) + "." if operations else "",
    ]
    paragraphs = [p for p in paragraphs if p]
    children = [html.P(p) for p in paragraphs]
    if typology_paragraphs:
        children.append(html.P("Tipos de clientes encontrados en los clusters visibles:"))
        children.extend([html.P(p) for p in typology_paragraphs])
    return html.Div(children, className="reading-text")


def cluster_reading_guide() -> html.Div:
    return html.Div(
        [
            html.Div("Guia para leer y usar el informe de clusters", className="panel-title"),
            html.Div(
                [
                    html.P("1. Selecciona Ano de cluster. Cada ano corresponde a un modelo recalculado con pedidos de ese periodo; no es un filtro sobre un unico modelo historico."),
                    html.P("2. Filtra por Mercado. Los clusters fueron calculados dentro de cada mercado, por eso no conviene comparar directamente un cluster de USA/Canada contra uno de Asia sin contexto."),
                    html.P("3. Luego filtra por Cluster. La vista de clientes muestra quienes pertenecen al grupo y que comparten: color, producto, tipo de pedido, constancia, volumen y cumplimiento."),
                    html.P("4. Usa 'Bloque principal' para entender por que existe el cluster. Si el bloque es color, los clientes se parecen por composicion/concentracion de color; si es producto, por portafolio; si es tipo_pedido, por formato operativo; si es constancia, por ritmo de compra."),
                    html.P("5. Usa 'Cambio de clientes entre anos' para observar cambios de tipologia, producto o color; no compares directamente el numero del cluster entre corridas anuales."),
                    html.P("6. Usa las tablas de clientes y similares para priorizar cuentas, replicar ofertas o preparar programas recurrentes dentro del mismo mercado."),
                ],
                className="reading-text",
            ),
        ],
        className="reading-panel",
    )


def panel_note(text: str) -> html.Div:
    return html.Div(text, className="metric-detail")


def build_cluster_commercial_actions(clusters: pd.DataFrame, block_profile: pd.DataFrame) -> pd.DataFrame:
    if clusters.empty:
        return pd.DataFrame()
    rows = []
    for keys, frame in clusters.groupby(["mercado_cluster", "cluster_id", "nombre_cluster"], dropna=False):
        mercado, cluster_id, nombre = keys
        block = ""
        if not block_profile.empty:
            match = block_profile[block_profile["cluster_id"].astype(str).eq(str(cluster_id))]
            if not match.empty:
                block = str(match.iloc[0].get("bloque_que_mas_diferencia", "") or "")
        products = _top_values(frame, "producto_dominante", value_col="tallos_total", n=2)
        colors = _top_values(frame, "color_dominante", value_col="tallos_total", n=2)
        types = _top_values(frame, "tipo_pedido_dominante", value_col="tallos_total", n=2)
        avg_cv = pd.to_numeric(frame.get("cv_volumen", pd.Series(dtype=float)), errors="coerce").mean()
        avg_color = pd.to_numeric(frame.get("share_top3_color", pd.Series(dtype=float)), errors="coerce").mean()
        avg_type = pd.to_numeric(frame.get("share_top1_tipo_pedido", pd.Series(dtype=float)), errors="coerce").mean()
        avg_score = pd.to_numeric(frame.get("score_compra_terminada", pd.Series(dtype=float)), errors="coerce").mean()
        avg_complexity = pd.to_numeric(frame.get("complejidad_operativa_score", pd.Series(dtype=float)), errors="coerce").mean()
        avg_recent = pd.to_numeric(frame.get("variacion_reciente_vs_previa", pd.Series(dtype=float)), errors="coerce").mean()
        if pd.notna(avg_cv) and avg_cv <= 0.55:
            ritmo = "constantes"
        elif pd.notna(avg_cv) and avg_cv <= 1.0:
            ritmo = "intermedios"
        else:
            ritmo = "variables"
        if pd.notna(avg_color) and avg_color >= 0.75:
            color_profile = "muy concentrados en color"
        elif pd.notna(avg_color) and avg_color >= 0.50:
            color_profile = "color moderadamente concentrado"
        else:
            color_profile = "mix de color amplio"
        if pd.notna(avg_type) and avg_type >= 0.85:
            type_profile = "formato operativo repetitivo"
        elif pd.notna(avg_type) and avg_type >= 0.60:
            type_profile = "formato dominante con variaciones"
        else:
            type_profile = "formatos variados"

        if ritmo == "constantes" and color_profile != "mix de color amplio" and type_profile == "formato operativo repetitivo":
            oportunidad = "programas recurrentes, preventa y ofertas cerradas por color/producto/formato"
            accion = "proponer portafolio fijo, calendario comercial y sustitutos controlados"
        elif block == "producto":
            oportunidad = "venta cruzada alrededor del producto dominante"
            accion = "ofrecer extensiones de producto, colores cercanos y paquetes por familia"
        elif block == "color":
            oportunidad = "campanas por color y manejo de sustitutos"
            accion = "segmentar ofertas por color dominante y disponibilidad de colores equivalentes"
        elif block == "tipo_pedido":
            oportunidad = "ofertas por formato operativo"
            accion = "vender estructuras similares segun SOLIDO/SURTIDO/BOUQUET/BQT/COMBO/RAINBOW/BULK y no solo por variedad"
        elif ritmo == "variables":
            oportunidad = "venta oportunistica y validacion comercial previa"
            accion = "usar como lista de prospeccion/seguimiento, evitando comprometer compra anticipada sin confirmacion"
        else:
            oportunidad = "seguimiento comercial por comportamiento parecido"
            accion = "comparar clientes espejo y replicar ofertas probadas en el mismo cluster"

        if ritmo == "variables":
            riesgo = "alta variabilidad; validar pedido antes de anticipar compra"
        elif pd.notna(avg_score) and avg_score < 55:
            riesgo = "score bajo para compra terminada; usar como lectura comercial antes que compromiso operativo"
        elif color_profile == "mix de color amplio":
            riesgo = "mix amplio; evitar ofertas demasiado cerradas en un solo color"
        else:
            riesgo = "riesgo operativo moderado; revisar disponibilidad y cumplimiento"
        if pd.notna(avg_complexity) and avg_complexity >= 60:
            accion_operativa = "preparar estructura, sustitutos y validacion de armado antes de confirmar oferta"
        elif type_profile == "formato operativo repetitivo":
            accion_operativa = "estandarizar presentacion recurrente y validar disponibilidad del formato dominante"
        else:
            accion_operativa = "revisar composicion antes de comprometer disponibilidad"
        if ritmo == "constantes":
            accion_planeacion = "incorporar demanda base al plan y revisar excepciones por color o producto"
        elif pd.notna(avg_recent) and avg_recent > 0.20:
            accion_planeacion = "monitorear crecimiento reciente y elevar cobertura solo con confirmacion comercial"
        else:
            accion_planeacion = "planear bajo escenarios y evitar reservar volumen rigido"

        rows.append(
            {
                "mercado": mercado,
                "cluster": cluster_id,
                "nombre_cluster": nombre,
                "clientes": frame["cod_cliente"].nunique(),
                "tallos": frame["tallos_total"].sum(),
                "ventas_usd": frame["ventas_usd_total"].sum() if "ventas_usd_total" in frame.columns else np.nan,
                "perfil_comercial": f"{ritmo}, {color_profile}, {type_profile}",
                "producto_base": ", ".join(products) if products else "sin_info",
                "color_base": ", ".join(colors) if colors else "sin_info",
                "tipo_pedido_base": ", ".join(types) if types else "sin_info",
                "bloque_que_explica": block or "sin_info",
                "oportunidad_comercial": oportunidad,
                "accion_comercial": accion,
                "riesgo_principal": riesgo,
                "accion_operativa": accion_operativa,
                "accion_planeacion": accion_planeacion,
            }
        )
    return pd.DataFrame(rows).sort_values(["mercado", "clientes"], ascending=[True, False])


def build_cluster_benchmark_table(clusters: pd.DataFrame) -> pd.DataFrame:
    """Compara cada cluster con el promedio de clientes de su propio mercado."""
    if clusters.empty:
        return pd.DataFrame()
    metrics = [
        ("tallos_total", "Volumen por cliente"),
        ("semanas_activas", "Semanas activas"),
        ("cv_volumen", "Variabilidad semanal"),
        ("share_top3_color", "Concentracion color top 3"),
        ("share_top5_sku", "Concentracion SKU top 5"),
        ("share_top1_tipo_pedido", "Concentracion tipo pedido"),
        ("ventas_usd_total", "Ventas USD por cliente"),
        ("variacion_reciente_vs_previa", "Cambio reciente vs previo"),
        ("complejidad_operativa_score", "Complejidad operativa"),
    ]
    present = [(col, label) for col, label in metrics if col in clusters.columns]
    rows = []
    for (market, cluster_id, name), frame in clusters.groupby(
        ["mercado_cluster", "cluster_id", "nombre_cluster"], dropna=False
    ):
        market_frame = clusters[clusters["mercado_cluster"].astype(str).eq(str(market))]
        for col, label in present:
            cluster_value = pd.to_numeric(frame[col], errors="coerce").mean()
            market_value = pd.to_numeric(market_frame[col], errors="coerce").mean()
            if pd.isna(cluster_value) or pd.isna(market_value):
                continue
            delta = cluster_value - market_value
            rows.append(
                {
                    "Cluster": cluster_id,
                    "Indicador": label,
                    "Valor cluster": cluster_value,
                    "Promedio mercado": market_value,
                    "Diferencia": delta,
                    "Lectura": "Por encima del mercado" if delta > 0 else "Por debajo del mercado",
                }
            )
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table["relevancia"] = table.groupby("Indicador")["Diferencia"].transform(lambda s: s.abs())
    return table.sort_values(["Cluster", "relevancia"], ascending=[True, False]).drop(columns="relevancia")


def build_cluster_year_change_section(
    current: pd.DataFrame,
    selected_year: str | None,
    bundles: dict[str, dict[str, pd.DataFrame]] | None,
) -> html.Div:
    """Muestra cambios de tipologia contra la corrida anual previa disponible."""
    if not selected_year or not str(selected_year).isdigit() or not bundles:
        return html.Div()
    previous_years = sorted(
        int(year) for year in bundles if str(year).isdigit() and int(year) < int(selected_year)
    )
    if not previous_years:
        return html.Div(
            [
                html.Div("Cambio de clientes entre anos", className="panel-title"),
                panel_note("Ejecuta clusters de un ano anterior para habilitar la comparacion de cambios comerciales."),
            ],
            className="table-panel section-gap",
        )
    previous_year = str(previous_years[-1])
    previous = bundles.get(previous_year, {}).get("clusters", pd.DataFrame()).copy()
    if previous.empty or current.empty:
        return html.Div()
    markets = set(current["mercado_cluster"].astype(str))
    previous = previous[previous["mercado_cluster"].astype(str).isin(markets)].copy()
    fields = [
        "cod_cliente", "cliente", "mercado_cluster", "cluster_id", "nombre_cluster",
        "producto_dominante", "color_dominante", "tipo_pedido_dominante", "tallos_total",
    ]
    left = previous[[col for col in fields if col in previous.columns]].copy()
    right = current[[col for col in fields if col in current.columns]].copy()
    change = left.merge(right, on=["cod_cliente", "mercado_cluster"], suffixes=(f"_{previous_year}", f"_{selected_year}"))
    if change.empty:
        return html.Div()
    before = f"nombre_cluster_{previous_year}"
    after = f"nombre_cluster_{selected_year}"
    change["cambio_tipologia"] = np.where(change[before].eq(change[after]), "Mantiene tipologia", "Cambia tipologia")
    summary = (
        change.groupby("cambio_tipologia", as_index=False)["cod_cliente"]
        .nunique()
        .rename(columns={"cod_cliente": "clientes"})
    )
    fig = px.bar(
        summary,
        x="cambio_tipologia",
        y="clientes",
        color="cambio_tipologia",
        title=f"Clientes comparables: {previous_year} vs {selected_year}",
    )
    apply_common_layout(fig, 350)
    detail_cols = [
        "cod_cliente", f"cliente_{selected_year}", "mercado_cluster", "cambio_tipologia",
        before, after,
        f"producto_dominante_{previous_year}", f"producto_dominante_{selected_year}",
        f"color_dominante_{previous_year}", f"color_dominante_{selected_year}",
        f"tipo_pedido_dominante_{previous_year}", f"tipo_pedido_dominante_{selected_year}",
        f"tallos_total_{previous_year}", f"tallos_total_{selected_year}",
    ]
    detail = change[[col for col in detail_cols if col in change.columns]].sort_values("cambio_tipologia")
    return html.Div(
        [
            html.Div("Cambio de clientes entre anos", className="panel-title"),
            panel_note(
                f"Compara clientes presentes en {previous_year} y {selected_year}. "
                "La tipologia es comparable; el identificador del cluster se recalcula dentro de cada ano."
            ),
            html.Div(dcc.Graph(figure=fig), className="panel"),
            make_table(detail.head(300), 14),
        ],
        className="table-panel section-gap",
    )


def build_cluster_variable_explanation(differentiators: pd.DataFrame) -> pd.DataFrame:
    """Convierte variables diferenciadoras en una lectura ejecutiva inicial."""
    if differentiators.empty:
        return pd.DataFrame()
    meaning = {
        "share_top1_color": "Peso del color principal en la compra.",
        "share_top3_color": "Concentracion del volumen en los tres colores principales.",
        "entropia_color_norm": "Diversidad de colores comprados.",
        "share_top1_producto": "Dependencia del producto principal.",
        "share_top3_producto": "Concentracion en el portafolio principal.",
        "entropia_producto_norm": "Diversidad de productos comprados.",
        "share_top1_tipo_pedido": "Concentracion en un formato de pedido.",
        "pct_semanas_activas": "Frecuencia con que el cliente compra en el ano.",
        "cv_volumen": "Variabilidad del volumen semanal.",
        "tallos_total": "Tamano total de la cuenta en tallos.",
    }
    business = {
        "color": "Ayuda a definir ofertas y disponibilidad por color.",
        "producto": "Orienta el portafolio que conviene ofrecer al grupo.",
        "tipo_pedido": "Indica si la propuesta debe plantearse por formato operativo.",
        "constancia": "Distingue programas recurrentes de compras de oportunidad.",
        "volumen": "Permite priorizar cuentas por impacto comercial.",
        "operacion": "Aporta restricciones de presentacion y servicio.",
        "sku": "Identifica repeticion de configuraciones comerciales.",
    }
    table = differentiators.copy()
    table = table.sort_values("importancia_modelo", ascending=False)
    if "cluster_id" in table.columns and table["cluster_id"].nunique() > 1:
        table = table.groupby("cluster_id", group_keys=False).head(3)
    else:
        table = table.head(8)
    table["Variable"] = table.get("lectura_variable", table["variable"])
    table["Importancia"] = pd.to_numeric(table["importancia_modelo"], errors="coerce").fillna(0)
    table["Que significa"] = table["variable"].map(meaning).fillna(table["Variable"])
    table["Lectura de negocio"] = table["bloque_variable"].map(business).fillna(
        "Describe una diferencia relevante frente al mercado."
    )
    if "lectura" in table.columns:
        table["Lectura de negocio"] = table["Lectura de negocio"] + " Resultado: " + table["lectura"].fillna("").astype(str) + "."
    cols = ["Variable", "Importancia", "Que significa", "Lectura de negocio"]
    if "cluster_id" in table.columns and differentiators["cluster_id"].nunique() > 1:
        table["Cluster"] = table["cluster_id"]
        cols = ["Cluster"] + cols
    return table[cols].reset_index(drop=True)


def render_clusters_tab(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected_code: str | None,
    top_n: int,
    market_filter: list[str] | str | None = None,
    cluster_filter: list[str] | str | None = None,
    cluster_year: str | None = None,
    cluster_bundles: dict[str, dict[str, pd.DataFrame]] | None = None,
):
    clusters = data["clusters"].copy()
    if clusters.empty:
        return html.Div("No hay clusters_clientes.csv disponible.", className="table-panel")

    profile_keys = [
        "cod_cliente",
        "tallos_total",
        "semanas_activas",
        "pct_semanas_activas",
        "cv_volumen",
        "segmento_cliente",
        "recomendacion_compra",
    ]
    profile_slice = data["perfil"][[col for col in profile_keys if col in data["perfil"].columns]].copy()
    if "cod_cliente" in profile_slice.columns:
        clusters = clusters.merge(profile_slice, on="cod_cliente", how="left", suffixes=("", "_perfil"))
        for col in ["tallos_total", "semanas_activas", "pct_semanas_activas", "cv_volumen", "segmento_cliente", "recomendacion_compra"]:
            perfil_col = f"{col}_perfil"
            if perfil_col in clusters.columns:
                if col in clusters.columns:
                    clusters[col] = clusters[col].where(clusters[col].notna(), clusters[perfil_col])
                else:
                    clusters[col] = clusters[perfil_col]

    if "mercado_cluster" not in clusters.columns:
        clusters["mercado_cluster"] = "SIN_MERCADO"
    if "metodo_cluster" not in clusters.columns:
        clusters["metodo_cluster"] = "SIN_METODO"
    if "nombre_cluster" not in clusters.columns:
        clusters["nombre_cluster"] = clusters.get("cluster_id", "SIN_CLUSTER")
    if "score_compra_terminada_operativo" in clusters.columns and "score_compra_terminada" not in clusters.columns:
        clusters["score_compra_terminada"] = clusters["score_compra_terminada_operativo"]
    for col in ["score_compra_terminada", "score_color", "score_sku_terminado", "cumplimiento_tallos", "tallos_total"]:
        if col not in clusters.columns:
            clusters[col] = 0

    market_values = selected_values(market_filter)
    if market_values:
        clusters = clusters[clusters["mercado_cluster"].astype(str).isin(market_values)].copy()
    cluster_values = selected_values(cluster_filter)
    if cluster_values:
        clusters = clusters[clusters["cluster_id"].astype(str).isin(cluster_values)].copy()

    valid_codes = set(filtered["cod_cliente"]) if not filtered.empty else set()
    if selected_code:
        clusters = clusters[clusters["cod_cliente"] == selected_code].copy()
    elif valid_codes:
        clusters = clusters[clusters["cod_cliente"].isin(valid_codes)].copy()

    if clusters.empty:
        return html.Div("No hay clientes de cluster para los filtros seleccionados.", className="table-panel")

    feature_cols = [
        col
        for col in [
            "tallos_total",
            "semanas_activas",
            "pct_semanas_activas",
            "tallos_promedio_semana",
            "cv_volumen",
            "cumplimiento_tallos",
            "share_top3_color",
            "share_top5_sku",
            "share_top1_tipo_pedido",
            "tallos_x_ramo_promedio",
            "ramos_x_caja_promedio",
            "score_compra_terminada",
        ]
        if col in clusters.columns
    ]

    cluster_summary = (
        clusters.groupby(["mercado_cluster", "cluster_id", "nombre_cluster", "metodo_cluster"], dropna=False, as_index=False)
        .agg(
            clientes=("cod_cliente", "nunique"),
            tallos=("tallos_total", "sum"),
            score_promedio=("score_compra_terminada", "mean"),
            color_promedio=("share_top3_color", "mean") if "share_top3_color" in clusters.columns else ("score_color", "mean"),
            sku_promedio=("share_top5_sku", "mean") if "share_top5_sku" in clusters.columns else ("score_sku_terminado", "mean"),
            cv_volumen_promedio=("cv_volumen", "mean") if "cv_volumen" in clusters.columns else ("tallos_total", "mean"),
            cumplimiento_promedio=("cumplimiento_tallos", "mean"),
        )
        .sort_values("clientes", ascending=False)
    )
    summary_keys = ["mercado_cluster", "cluster_id", "nombre_cluster", "metodo_cluster"]
    optional_summary = {
        "ventas_usd_total": ("ventas_usd", "sum"),
        "variacion_reciente_vs_previa": ("cambio_reciente_promedio", "mean"),
        "complejidad_operativa_score": ("complejidad_promedio", "mean"),
    }
    for source_col, (target_col, operation) in optional_summary.items():
        if source_col in clusters.columns:
            add = clusters.groupby(summary_keys, dropna=False, as_index=False).agg(**{target_col: (source_col, operation)})
            cluster_summary = cluster_summary.merge(add, on=summary_keys, how="left")

    visible_cluster_ids = set(clusters["cluster_id"].astype(str))
    differentiators = data.get("cluster_diff", pd.DataFrame()).copy()
    if not differentiators.empty:
        differentiators = differentiators[differentiators["cluster_id"].astype(str).isin(visible_cluster_ids)].copy()
        if market_values and "mercado_cluster" in differentiators.columns:
            differentiators = differentiators[differentiators["mercado_cluster"].astype(str).isin(market_values)].copy()
        differentiators = differentiators.sort_values(["cluster_id", "importancia_modelo"], ascending=[True, False])
    else:
        cluster_profiles = (
            clusters.groupby(["mercado_cluster", "cluster_id", "nombre_cluster"], dropna=False)[feature_cols]
            .mean()
            .reset_index()
        ) if feature_cols else pd.DataFrame()
        market_profiles = (
            clusters.groupby("mercado_cluster", dropna=False)[feature_cols]
            .mean()
            .reset_index()
            .rename(columns={col: f"{col}_mercado" for col in feature_cols})
        ) if feature_cols else pd.DataFrame()
        if not cluster_profiles.empty:
            diff = cluster_profiles.merge(market_profiles, on="mercado_cluster", how="left")
            labels = {
                "tallos_total": "Volumen total cliente",
                "semanas_activas": "Frecuencia",
                "pct_semanas_activas": "Constancia",
                "tallos_promedio_semana": "Volumen semanal",
                "cv_volumen": "Variabilidad semanal",
                "cumplimiento_tallos": "Cumplimiento",
                "share_top3_color": "Concentracion en colores",
                "share_top5_sku": "Repeticion SKU operativo",
                "share_top1_tipo_pedido": "Concentracion tipo pedido",
                "tallos_x_ramo_promedio": "Tallos por ramo",
                "ramos_x_caja_promedio": "Ramos por caja",
                "score_compra_terminada": "Score compra terminada",
            }
            rows = []
            for row in diff.to_dict("records"):
                for col in feature_cols:
                    cluster_value = float(row.get(col, 0) or 0)
                    market_value = float(row.get(f"{col}_mercado", 0) or 0)
                    delta = cluster_value - market_value
                    if abs(delta) <= 1e-9:
                        continue
                    rows.append(
                        {
                            "mercado_cluster": row["mercado_cluster"],
                            "cluster_id": row["cluster_id"],
                            "nombre_cluster": row["nombre_cluster"],
                            "bloque_variable": "perfil",
                            "lectura_variable": labels.get(col, col),
                            "valor_cluster": cluster_value,
                            "promedio_mercado": market_value,
                            "diferencia": delta,
                            "importancia_modelo": abs(delta),
                            "lectura": "mas alto que mercado" if delta > 0 else "mas bajo que mercado",
                        }
                    )
            differentiators = pd.DataFrame(rows).sort_values(["cluster_id", "importancia_modelo"], ascending=[True, False]) if rows else pd.DataFrame()

    block_profile = data.get("cluster_blocks", pd.DataFrame()).copy()
    if not block_profile.empty:
        block_profile = block_profile[block_profile["cluster_id"].astype(str).isin(visible_cluster_ids)].copy()
    commercial_actions = build_cluster_commercial_actions(clusters, block_profile)
    explanation_table = build_cluster_variable_explanation(differentiators)
    benchmark_table = build_cluster_benchmark_table(clusters)

    tipo_mix = pd.DataFrame()
    if "tipo_pedido_dominante" in clusters.columns:
        tipo_mix = (
            clusters.groupby(["mercado_cluster", "cluster_id", "nombre_cluster", "tipo_pedido_dominante"], dropna=False, as_index=False)
            .agg(clientes=("cod_cliente", "nunique"), tallos=("tallos_total", "sum"), concentracion_tipo=("share_top1_tipo_pedido", "mean"))
            .sort_values(["mercado_cluster", "cluster_id", "clientes"], ascending=[True, True, False])
        )

    scatter = px.scatter(
        clusters,
        x="share_top3_color" if "share_top3_color" in clusters.columns else "score_color",
        y="share_top5_sku" if "share_top5_sku" in clusters.columns else "score_sku_terminado",
        size="tallos_total",
        color="nombre_cluster",
        facet_col="mercado_cluster" if clusters["mercado_cluster"].nunique() <= 5 else None,
        color_discrete_map=color_map_for(clusters, "nombre_cluster"),
        hover_data=[
            col
            for col in [
                "cod_cliente",
                "cliente",
                "mercado_cluster",
                "metodo_cluster",
                "cluster_id",
                "producto_dominante",
                "color_dominante",
                "tipo_pedido_dominante",
                "segmento_cliente",
                "recomendacion_compra",
                "score_compra_terminada",
            ]
            if col in clusters.columns
        ],
        title="Clusters por mercado: concentracion de color vs concentracion de SKU",
    )
    apply_common_layout(scatter, 500)

    tree = px.treemap(
        cluster_summary,
        path=["mercado_cluster", "nombre_cluster"],
        values="clientes",
        color="score_promedio",
        color_continuous_scale=[CORPORATE_BURGUNDY, "#B07AA1", "#4E79A7", "#59A14F"],
        title="Tamano de clusters por mercado",
    )
    apply_common_layout(tree, 500)

    bars = px.bar(
        cluster_summary.head(max(top_n, 10)),
        x="clientes",
        y="cluster_id",
        orientation="h",
        color="mercado_cluster",
        color_discrete_map=color_map_for(cluster_summary, "mercado_cluster"),
        hover_data=["nombre_cluster", "metodo_cluster", "score_promedio", "cv_volumen_promedio"],
        title="Clusters con mas clientes",
    )
    bars.update_layout(yaxis={"categoryorder": "total ascending"})
    apply_common_layout(bars, 460)

    method_market = (
        clusters.groupby(["mercado_cluster", "metodo_cluster"], dropna=False, as_index=False)
        .agg(clientes=("cod_cliente", "nunique"), tallos=("tallos_total", "sum"))
        .sort_values("clientes", ascending=False)
    )
    heat = px.density_heatmap(
        method_market,
        x="mercado_cluster",
        y="metodo_cluster",
        z="clientes",
        histfunc="sum",
        text_auto=True,
        color_continuous_scale="Blues",
        title="Metodo seleccionado por mercado",
    )
    heat.update_layout(xaxis_tickangle=-35)
    apply_common_layout(heat, 500)

    if tipo_mix.empty:
        tipo_fig = empty_figure("Tipo de pedido dominante por cluster")
    else:
        tipo_fig = px.bar(
            tipo_mix,
            x="cluster_id",
            y="clientes",
            color="tipo_pedido_dominante",
            facet_col="mercado_cluster" if tipo_mix["mercado_cluster"].nunique() <= 5 else None,
            hover_data=["nombre_cluster", "tallos", "concentracion_tipo"],
            title="Tipo de pedido dominante dentro de cada cluster",
        )
        tipo_fig.update_layout(xaxis_tickangle=-35)
        apply_common_layout(tipo_fig, 500)

    if differentiators.empty:
        diff_fig = empty_figure("Variables que diferencian cada cluster")
        diff_table = differentiators
    else:
        top_diff = differentiators.groupby("cluster_id", group_keys=False).head(5).copy()
        y_col = "lectura_variable" if "lectura_variable" in top_diff.columns else "variable"
        color_col = "bloque_variable" if "bloque_variable" in top_diff.columns else "cluster_id"
        diff_fig = px.bar(
            top_diff,
            x="diferencia_estandarizada" if "diferencia_estandarizada" in top_diff.columns else "diferencia",
            y=y_col,
            color=color_col,
            orientation="h",
            facet_col="mercado_cluster" if top_diff["mercado_cluster"].nunique() <= 3 else None,
            hover_data=["nombre_cluster", "valor_cluster", "promedio_mercado", "lectura"],
            title="Variables que mas diferencian cada cluster contra su mercado",
        )
        diff_fig.update_layout(yaxis={"categoryorder": "total ascending"})
        apply_common_layout(diff_fig, 560)
        diff_table = differentiators.drop(columns=["diferencia_abs"], errors="ignore").head(160)

    if block_profile.empty or "bloque_que_mas_diferencia" not in block_profile.columns:
        block_fig = empty_figure("Bloque que mas explica cada cluster")
    else:
        block_fig = px.bar(
            block_profile,
            x="cluster_id",
            y="clientes",
            color="bloque_que_mas_diferencia",
            facet_col="mercado_cluster" if block_profile["mercado_cluster"].nunique() <= 5 else None,
            hover_data=["nombre_cluster", "variables_clave_bloque", "tipo_pedido_dominante_cluster", "producto_dominante_cluster", "color_dominante_cluster"],
            title="Bloque principal que diferencia cada cluster",
        )
        block_fig.update_layout(xaxis_tickangle=-35)
        apply_common_layout(block_fig, 500)

    eval_table = data.get("cluster_eval", pd.DataFrame()).copy()
    if not eval_table.empty:
        for col in ["silhouette", "calinski_harabasz", "clientes"]:
            if col in eval_table.columns:
                eval_table[col] = pd.to_numeric(eval_table[col], errors="coerce")
        eval_table = eval_table.sort_values(["mercado_cluster", "silhouette", "calinski_harabasz"], ascending=[True, False, False])
        eval_table = eval_table.head(80)

    similar = data.get("similares", pd.DataFrame()).copy()
    if not similar.empty:
        if selected_code:
            similar = similar[similar["cod_cliente_base"] == selected_code].copy()
        else:
            visible_codes = set(clusters["cod_cliente"].astype(str))
            similar = similar[similar["cod_cliente_base"].astype(str).isin(visible_codes)].copy()
        similar_cols = [
            "mercado_cluster",
            "cluster_id_base",
            "nombre_cluster_base",
            "cod_cliente_base",
            "cliente_base",
            "cod_cliente_similar",
            "cliente_similar",
            "mismo_cluster",
            "similitud_total",
            "razon_cluster",
            "producto_base",
            "producto_similar",
            "color_base",
            "color_similar",
            "tipo_pedido_base",
            "tipo_pedido_similar",
        ]
        similar = similar[[col for col in similar_cols if col in similar.columns]].head(400)

    client_cols = [
        "mercado_cluster",
        "metodo_cluster",
        "cluster_id",
        "nombre_cluster",
        "cod_cliente",
        "cliente",
        "pais_principal",
        "segmento_cliente",
        "recomendacion_compra",
        "score_compra_terminada",
        "share_top3_color",
        "share_top5_sku",
        "share_top1_tipo_pedido",
        "tallos_x_ramo_promedio",
        "ramos_x_caja_promedio",
        "producto_dominante",
        "color_dominante",
        "tipo_pedido_dominante",
        "cv_volumen",
        "cumplimiento_tallos",
        "tallos_total",
        "ventas_usd_total",
        "participacion_tallos_mercado",
        "variacion_reciente_vs_previa",
        "complejidad_operativa",
        "complejidad_operativa_score",
    ]
    clients_table = clusters[[col for col in client_cols if col in clusters.columns]].sort_values(
        ["mercado_cluster", "cluster_id", "tallos_total"], ascending=[True, True, False]
    )
    year_change_section = build_cluster_year_change_section(clusters, cluster_year, cluster_bundles)
    natural_reading = cluster_natural_reading(clusters, cluster_summary, block_profile, differentiators, tipo_mix)
    periodo = data.get("cluster_periodo", pd.DataFrame())
    period_label = "corrida seleccionada"
    if not periodo.empty and "fecha_min" in periodo.columns and "fecha_max" in periodo.columns:
        min_date = pd.to_datetime(periodo.iloc[0]["fecha_min"], errors="coerce")
        max_date = pd.to_datetime(periodo.iloc[0]["fecha_max"], errors="coerce")
        if pd.notna(min_date) and pd.notna(max_date):
            period_label = f"{min_date:%Y-%m-%d} a {max_date:%Y-%m-%d}"
    clients_table_display = clients_table.copy()
    rename_clients = {
        "mercado_cluster": "mercado",
        "cluster_id": "cluster",
        "nombre_cluster": "tipo_cluster",
        "cod_cliente": "cod",
        "pais_principal": "pais",
        "score_compra_terminada": "score",
        "share_top3_color": "concentracion_color_top3",
        "share_top5_sku": "repeticion_sku_top5",
        "share_top1_tipo_pedido": "concentracion_tipo_pedido",
        "tallos_x_ramo_promedio": "tallos_ramo",
        "ramos_x_caja_promedio": "ramos_caja",
        "cv_volumen": "variabilidad",
        "cumplimiento_tallos": "cumplimiento",
        "tallos_total": "tallos",
        "ventas_usd_total": "ventas_usd",
        "participacion_tallos_mercado": "participacion_mercado",
        "variacion_reciente_vs_previa": "cambio_reciente",
        "complejidad_operativa": "complejidad",
        "complejidad_operativa_score": "score_complejidad",
    }
    clients_table_display = clients_table_display.rename(columns={k: v for k, v in rename_clients.items() if k in clients_table_display.columns})
    representative_clients = (
        clients_table.sort_values(["cluster_id", "tallos_total"], ascending=[True, False])
        .groupby("cluster_id", group_keys=False)
        .head(5)
        .rename(columns={k: v for k, v in rename_clients.items() if k in clients_table.columns})
    )
    missing_market = (
        clusters["mercado_cluster"].astype(str).eq("05_OTROS").all()
        and "pais_principal" in clusters.columns
        and clusters["pais_principal"].fillna("sin_info").astype(str).str.lower().eq("sin_info").all()
    )
    market_warning = html.Div()
    if missing_market:
        market_warning = html.Div(
            "Esta corrida no contiene pais en la entrada y agrupa todos los clientes como OTROS. Regenera descriptivos y clusters despues de actualizar la base para habilitar la lectura real por mercado.",
            className="table-panel section-gap",
        )

    if clients_table.empty:
        client_rank_fig = empty_figure("Clientes del cluster por volumen")
        client_mix_fig = empty_figure("Composicion de clientes visibles")
    else:
        rank = clients_table.sort_values("tallos_total", ascending=False).head(max(top_n, 20)).copy()
        rank["cliente_label"] = rank["cod_cliente"].astype(str) + " | " + rank["cliente"].astype(str).str.slice(0, 28)
        client_rank_fig = px.bar(
            rank,
            x="tallos_total",
            y="cliente_label",
            color="cluster_id",
            orientation="h",
            hover_data=[
                col
                for col in [
                    "mercado_cluster",
                    "nombre_cluster",
                    "producto_dominante",
                    "color_dominante",
                    "tipo_pedido_dominante",
                    "share_top3_color",
                    "share_top1_tipo_pedido",
                    "pct_semanas_activas",
                    "cv_volumen",
                ]
                if col in rank.columns
            ],
            title="Clientes dentro del cluster por volumen",
        )
        client_rank_fig.update_layout(yaxis={"categoryorder": "total ascending"})
        apply_common_layout(client_rank_fig, 560)

        mix_parts = []
        for col, label in [
            ("producto_dominante", "Producto dominante"),
            ("color_dominante", "Color dominante"),
            ("tipo_pedido_dominante", "Tipo pedido dominante"),
        ]:
            if col in clients_table.columns:
                tmp = (
                    clients_table.groupby([col], dropna=False, as_index=False)
                    .agg(clientes=("cod_cliente", "nunique"), tallos=("tallos_total", "sum"))
                    .sort_values("clientes", ascending=False)
                    .head(10)
                )
                tmp["dimension"] = label
                tmp = tmp.rename(columns={col: "valor"})
                mix_parts.append(tmp)
        client_mix = pd.concat(mix_parts, ignore_index=True) if mix_parts else pd.DataFrame()
        if client_mix.empty:
            client_mix_fig = empty_figure("Composicion de clientes visibles")
        else:
            client_mix_fig = px.bar(
                client_mix,
                x="clientes",
                y="valor",
                color="dimension",
                facet_col="dimension",
                orientation="h",
                hover_data=["tallos"],
                title="Composicion descriptiva de los clientes visibles",
            )
            client_mix_fig.update_layout(yaxis={"categoryorder": "total ascending"})
            apply_common_layout(client_mix_fig, 520)

    metric_cards = [
        make_card("Ano cluster", str(cluster_year or "sin dato"), period_label),
        make_card("Clusters", moneyless_number(cluster_summary["cluster_id"].nunique()), "en filtro actual"),
        make_card("Clientes", moneyless_number(clusters["cod_cliente"].nunique()), "asignados"),
        make_card("Mercados", moneyless_number(clusters["mercado_cluster"].nunique()), "grupos definidos"),
        make_card("Tallos", moneyless_number(clusters["tallos_total"].sum()), "volumen analizado"),
    ]
    if "ventas_usd_total" in clusters.columns:
        metric_cards.append(make_card("Ventas USD", moneyless_number(clusters["ventas_usd_total"].sum(), 2), "valor del grupo"))
    if "complejidad_operativa_score" in clusters.columns:
        metric_cards.append(
            make_card("Complejidad", moneyless_number(clusters["complejidad_operativa_score"].mean(), 1), "promedio 0-100")
        )
    metric_cards.append(
        make_card(
            "Metodo elegido",
            str(method_market.sort_values("clientes", ascending=False).iloc[0]["metodo_cluster"]),
            "mercado visible principal",
        )
    )

    return html.Div(
        [
            market_warning,
            html.Div(metric_cards, className="metrics-grid"),
            html.Div(
                [
                    html.Div("Resumen ejecutivo de los tipos de clientes visibles", className="panel-title"),
                    panel_note("Esta lectura describe clientes agrupados dentro del mercado seleccionado. Selecciona un solo cluster para convertirla en ficha de accion."),
                    natural_reading,
                ],
                className="reading-panel section-gap",
            ),
            html.Div(
                [
                    html.Div("Riesgos, oportunidades y acciones recomendadas", className="panel-title"),
                    panel_note("Usa esta tabla para llevar la segmentacion a gestion comercial, operacion y planeacion."),
                    make_table(commercial_actions, 12),
                ],
                className="table-panel",
            ),
            html.Div(
                [
                    html.Div("Variables que explican el cluster seleccionado", className="panel-title"),
                    panel_note("Muestra las variables que separan el grupo frente a clientes del mismo mercado. Son las razones del agrupamiento que deben validarse comercialmente."),
                    make_table(explanation_table, 12),
                ],
                className="table-panel",
            ),
            html.Div(
                [
                    html.Div("Cluster frente al promedio de su mercado", className="panel-title"),
                    panel_note("Permite distinguir si el grupo compra mas, compra con mayor regularidad, concentra su mix o exige una operacion mas compleja."),
                    make_table(benchmark_table, 12),
                ],
                className="table-panel",
            ),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=diff_fig), panel_note("Las barras mas largas identifican los atributos que mas diferencian el grupo frente a su mercado.")], className="panel"),
                    html.Div([dcc.Graph(figure=tipo_fig), panel_note("Indica si la gestion del cluster debe orientarse a SOLIDO, SURTIDO, SURTIDO_M, BOUQUET, BQT, COMBO, RAINBOW u otro formato.")], className="panel"),
                ],
                className="grid-2 section-gap",
            ),
            html.Div(
                [
                    html.Div([dcc.Graph(figure=client_rank_fig), panel_note("Prioriza las cuentas que explican mayor volumen dentro del grupo.")], className="panel"),
                ],
                className="section-gap",
            ),
            html.Div(
                [
                    html.Div("Clientes representativos del cluster", className="panel-title"),
                    panel_note("Muestra las cuentas de mayor volumen de cada grupo y sus rasgos dominantes para preparar oferta y seguimiento."),
                    make_table(representative_clients, 15),
                ],
                className="table-panel",
            ),
            html.Div(
                [
                    html.Div("Clientes parecidos dentro del mercado", className="panel-title"),
                    panel_note("Clientes espejo para replicar ofertas o validar sustitutos; la similitud se calcula sobre los mismos atributos usados para segmentar."),
                    make_table(similar, 12),
                ],
                className="table-panel",
            ),
            year_change_section,
            html.Details(
                [
                    html.Summary("Como leer este informe"),
                    cluster_reading_guide(),
                ],
                className="table-panel section-gap",
            ),
            html.Details(
                [
                    html.Summary("Analisis descriptivo y tecnico adicional"),
                    html.Div([html.Div(dcc.Graph(figure=scatter), className="panel"), html.Div(dcc.Graph(figure=tree), className="panel")], className="grid-2 section-gap"),
                    html.Div([html.Div(dcc.Graph(figure=bars), className="panel"), html.Div(dcc.Graph(figure=block_fig), className="panel")], className="grid-2 section-gap"),
                    html.Div([html.Div(dcc.Graph(figure=client_mix_fig), className="panel"), html.Div(dcc.Graph(figure=heat), className="panel")], className="grid-2 section-gap"),
                    html.Div([html.Div("Clientes del cluster seleccionado", className="panel-title"), make_table(clients_table_display.head(800), 18)], className="table-panel"),
                    html.Div([html.Div("Resumen cuantitativo de clusters", className="panel-title"), make_table(cluster_summary, 12)], className="table-panel"),
                    html.Div([html.Div("Perfil por bloques", className="panel-title"), make_table(block_profile, 12)], className="table-panel"),
                    html.Div([html.Div("Detalle de variables diferenciadoras", className="panel-title"), make_table(diff_table, 12)], className="table-panel"),
                    html.Div([html.Div("Tipo de pedido dominante", className="panel-title"), make_table(tipo_mix.head(120), 12)], className="table-panel"),
                    html.Div([html.Div("Evaluacion de metodos por mercado", className="panel-title"), make_table(eval_table, 12)], className="table-panel"),
                ],
                className="table-panel section-gap",
            ),
        ]
    )


def render_comprador_tab(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected_code: str | None,
    top_n: int,
    week_offset: int = 0,
    visible_weeks: int = 4,
):
    valid_codes = set(filtered["cod_cliente"]) if not filtered.empty else set()
    cruce = data["cruce"].copy()
    if not cruce.empty and selected_code:
        cruce = cruce[cruce["cod_cliente"] == selected_code].copy()
    elif not cruce.empty and valid_codes:
        cruce = cruce[cruce["cod_cliente"].isin(valid_codes)].copy()
    cruce = apply_future_window(cruce, week_offset, visible_weeks)

    if cruce.empty:
        return html.Div("No hay cruce_forecast_inventario.csv para construir la vista de comprador.", className="table-panel")

    cruce["tallos_prioridad_compra_cliente"] = pd.to_numeric(cruce["tallos_prioridad_compra_cliente"], errors="coerce").fillna(0)
    cruce["tallos_estimados"] = pd.to_numeric(cruce["tallos_estimados"], errors="coerce").fillna(0)
    compra = cruce[cruce["tallos_prioridad_compra_cliente"] > 0].copy()
    if compra.empty:
        compra = cruce.sort_values("tallos_estimados", ascending=False).head(200).copy()

    by_priority = compra.groupby("prioridad_compra", dropna=False, as_index=False)["tallos_prioridad_compra_cliente"].sum()
    priority_fig = px.bar(
        by_priority.sort_values("tallos_prioridad_compra_cliente", ascending=False),
        x="prioridad_compra",
        y="tallos_prioridad_compra_cliente",
        color="prioridad_compra",
        color_discrete_map=color_map_for(by_priority, "prioridad_compra"),
        title="Compra recomendada por prioridad",
    )
    priority_fig.update_layout(xaxis_tickangle=-30)
    apply_common_layout(priority_fig, 380)

    by_day = compra.groupby(["fecha_forecast", "prioridad_compra"], dropna=False, as_index=False)["tallos_prioridad_compra_cliente"].sum()
    day_fig = px.area(by_day, x="fecha_forecast", y="tallos_prioridad_compra_cliente", color="prioridad_compra", color_discrete_map=color_map_for(by_day, "prioridad_compra"), title="Necesidad de compra por fecha")
    apply_common_layout(day_fig, 400)

    by_item = (
        compra.groupby(["producto", "variedad", "color", "grado", "tipo_caja"], dropna=False, as_index=False)
        .agg(
            tallos_a_comprar=("tallos_prioridad_compra_cliente", "sum"),
            demanda=("tallos_estimados", "sum"),
            inventario_color=("inventario_color_total", "sum") if "inventario_color_total" in compra.columns else ("inventario_total", "sum"),
            share_no_usa=("share_variedad_demanda_no_usa", "max") if "share_variedad_demanda_no_usa" in compra.columns else ("tallos_estimados", "sum"),
        )
        .sort_values("tallos_a_comprar", ascending=False)
        .head(max(top_n, 15))
    )
    by_item["item"] = (
        by_item["producto"].astype(str)
        + " | "
        + by_item["variedad"].astype(str)
        + " | "
        + by_item["color"].astype(str)
        + " | "
        + by_item["grado"].astype(str)
        + " | "
        + by_item["tipo_caja"].astype(str)
    )
    item_fig = px.bar(
        by_item,
        x="tallos_a_comprar",
        y="item",
        orientation="h",
        color="share_no_usa",
        color_continuous_scale=[CORPORATE_BURGUNDY, "#B07AA1", "#4E79A7", "#59A14F"],
        title="Compra por variedad demandada por clientes no USA",
    )
    item_fig.update_layout(yaxis={"categoryorder": "total ascending"})
    apply_common_layout(item_fig, 560)

    by_client = (
        compra.groupby(["cod_cliente", "cliente", "recomendacion_compra"], dropna=False, as_index=False)
        .agg(tallos_a_comprar=("tallos_prioridad_compra_cliente", "sum"), demanda=("tallos_estimados", "sum"))
        .sort_values("tallos_a_comprar", ascending=False)
        .head(max(top_n, 15))
    )
    client_fig = px.bar(
        by_client,
        x="tallos_a_comprar",
        y="cliente",
        orientation="h",
        color="recomendacion_compra",
        color_discrete_map=color_map_for(by_client, "recomendacion_compra"),
        title="Clientes que explican la compra",
    )
    client_fig.update_layout(yaxis={"categoryorder": "total ascending"})
    apply_common_layout(client_fig, 560)

    action_cols = [
        "fecha_forecast",
        "prioridad_compra",
        "riesgo_disponibilidad",
        "riesgo_variedad",
        "criterio_compra_variedad",
        "cod_cliente",
        "cliente",
        "pais",
        "tipo_pedido_operativo",
        "producto",
        "variedad",
        "color",
        "grado",
        "tipo_caja",
        "tallos_estimados",
        "inventario_color_total",
        "inventario_variedad_total",
        "faltante_proyectado_item",
        "share_variedad_demanda_no_usa",
        "ranking_variedad_no_usa",
        "tallos_prioridad_compra_cliente",
        "score_compra_terminada",
        "recomendacion_compra",
    ]
    action_table = compra.sort_values(["tallos_prioridad_compra_cliente", "tallos_estimados"], ascending=False)
    action_table = action_table[[col for col in action_cols if col in action_table.columns]].head(500)

    return html.Div(
        [
            html.Div(
                [
                    make_card("Tallos a comprar", moneyless_number(compra["tallos_prioridad_compra_cliente"].sum()), "prioridad cliente"),
                    make_card("Lineas accionables", moneyless_number(len(compra)), "detalle fecha item"),
                    make_card("Clientes afectados", moneyless_number(compra["cod_cliente"].nunique()), "con necesidad"),
                    make_card("Ventana", f"{visible_weeks} semanas", window_detail(data["cruce"], week_offset, visible_weeks)),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div(dcc.Graph(figure=priority_fig), className="panel"), html.Div(dcc.Graph(figure=day_fig), className="panel")], className="grid-2"),
            html.Div([html.Div(dcc.Graph(figure=item_fig), className="panel"), html.Div(dcc.Graph(figure=client_fig), className="panel")], className="grid-2 section-gap"),
            html.Div([html.Div("Lista de compra accionable", className="panel-title"), make_table(action_table, 18)], className="table-panel"),
        ]
    )


def render_colores_tab(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected_code: str | None,
    top_n: int,
    week_offset: int = 0,
    visible_weeks: int = 4,
    product_filter: str | None = None,
    color_filter: str | None = None,
):
    cruce = data["cruce"].copy()
    inventario_color = data.get("inventario_color", pd.DataFrame()).copy()
    valid_codes = set(filtered["cod_cliente"]) if not filtered.empty else set()

    if selected_code and not cruce.empty:
        cruce = cruce[cruce["cod_cliente"] == selected_code].copy()
    elif valid_codes and not cruce.empty:
        cruce = cruce[cruce["cod_cliente"].isin(valid_codes)].copy()

    for frame_name in ["cruce", "inventario_color"]:
        frame = cruce if frame_name == "cruce" else inventario_color
        if frame.empty:
            continue
        if product_filter and "producto" in frame.columns:
            frame = frame[frame["producto"].astype(str).eq(str(product_filter))].copy()
        if color_filter and "color" in frame.columns:
            frame = frame[frame["color"].astype(str).eq(str(color_filter))].copy()
        if frame_name == "cruce":
            cruce = frame
        else:
            inventario_color = frame

    reference = cruce if not cruce.empty else inventario_color
    start, end = future_window_bounds(reference, week_offset, visible_weeks)
    cruce = apply_future_window(cruce, week_offset, visible_weeks)
    if not inventario_color.empty and start is not None and end is not None:
        dates = pd.to_datetime(inventario_color["fecha_forecast"], errors="coerce")
        inventario_color = inventario_color[(dates >= start) & (dates <= end)].copy()

    if cruce.empty and inventario_color.empty:
        return html.Div("No hay inventario proyectado o demanda cruzada para los filtros seleccionados.", className="table-panel")

    if not cruce.empty:
        for col in ["tallos_estimados", "inventario_total", "inventario_color_total", "faltante_proyectado_item", "tallos_prioridad_compra_cliente", "score_compra_terminada"]:
            if col in cruce.columns:
                cruce[col] = pd.to_numeric(cruce[col], errors="coerce").fillna(0)

    if not inventario_color.empty:
        for col in ["inventario_color_total", "faltante_color_proyectado", "sobrante_color_proyectado"]:
            if col in inventario_color.columns:
                inventario_color[col] = pd.to_numeric(inventario_color[col], errors="coerce").fillna(0)
        color_balance = inventario_color.copy()
        color_balance["inventario_final_proyectado"] = color_balance["inventario_color_total"]
        color_balance["faltante_color"] = color_balance.get("faltante_color_proyectado", color_balance["inventario_final_proyectado"].clip(upper=0).abs())
        color_balance["sobrante_color"] = color_balance.get("sobrante_color_proyectado", color_balance["inventario_final_proyectado"].clip(lower=0))
    else:
        keys = ["fecha_forecast", "producto", "color", "grado"]
        color_balance = (
            cruce.groupby(keys, dropna=False, as_index=False)
            .agg(
                inventario_final_proyectado=("inventario_color_total", "first") if "inventario_color_total" in cruce.columns else ("inventario_total", "first"),
                demanda=("tallos_estimados", "sum"),
            )
        )
        color_balance["faltante_color"] = color_balance["inventario_final_proyectado"].clip(upper=0).abs()
        color_balance["sobrante_color"] = color_balance["inventario_final_proyectado"].clip(lower=0)

    demand_by_color = pd.DataFrame()
    if not cruce.empty:
        demand_by_color = (
            cruce.groupby(["fecha_forecast", "producto", "color", "grado"], dropna=False, as_index=False)
            .agg(
                demanda=("tallos_estimados", "sum"),
                clientes=("cod_cliente", "nunique"),
                pedidos_reales=("fuente_demanda", lambda s: int(s.astype(str).str.contains("PENDIENTE", case=False, na=False).sum())),
                tallos_prioridad=("tallos_prioridad_compra_cliente", "sum") if "tallos_prioridad_compra_cliente" in cruce.columns else ("tallos_estimados", "sum"),
            )
        )
        merge_keys = ["fecha_forecast", "producto", "color", "grado"]
        color_balance = color_balance.merge(demand_by_color, on=merge_keys, how="left", suffixes=("", "_demanda"))
        if "demanda_demanda" in color_balance.columns:
            color_balance["demanda"] = color_balance["demanda"].fillna(color_balance["demanda_demanda"])
            color_balance = color_balance.drop(columns=["demanda_demanda"])

    for col in ["demanda", "clientes", "pedidos_reales", "tallos_prioridad"]:
        if col not in color_balance.columns:
            color_balance[col] = 0
        color_balance[col] = pd.to_numeric(color_balance[col], errors="coerce").fillna(0)
    color_balance["fecha_forecast"] = pd.to_datetime(color_balance["fecha_forecast"], errors="coerce")
    color_balance = add_week_columns(color_balance, "fecha_forecast")
    color_balance["estado_color"] = np.select(
        [
            color_balance["inventario_final_proyectado"] < 0,
            color_balance["inventario_final_proyectado"] > 0,
        ],
        ["FALTANTE", "SOBRANTE"],
        default="NEUTRO",
    )

    faltantes = color_balance[color_balance["inventario_final_proyectado"] < 0].copy()
    balance_day = color_balance.groupby(["fecha_forecast", "estado_color"], dropna=False, as_index=False).agg(
        tallos=("inventario_final_proyectado", "sum"),
        faltante=("faltante_color", "sum"),
        demanda=("demanda", "sum"),
    )
    day_fig = px.area(
        balance_day,
        x="fecha_forecast",
        y="faltante",
        color="estado_color",
        color_discrete_map=color_map_for(balance_day, "estado_color"),
        title="Faltantes diarios por inventario final proyectado",
    )
    apply_common_layout(day_fig, 400)

    top_color = (
        faltantes.groupby(["producto", "color", "grado"], dropna=False, as_index=False)
        .agg(faltante=("faltante_color", "sum"), demanda=("demanda", "sum"), dias_faltante=("fecha_forecast", "nunique"))
        .sort_values("faltante", ascending=False)
        .head(max(top_n, 15))
    )
    top_color["item"] = top_color["producto"].astype(str) + " | " + top_color["color"].astype(str) + " | " + top_color["grado"].astype(str)
    color_fig = px.bar(
        top_color,
        x="faltante",
        y="item",
        orientation="h",
        color="color",
        color_discrete_map=color_map_for(top_color, "color"),
        hover_data=["demanda", "dias_faltante"],
        title="Colores con mas faltante proyectado",
    )
    color_fig.update_layout(yaxis={"categoryorder": "total ascending"})
    apply_common_layout(color_fig, 520)

    if cruce.empty:
        variety_fig = empty_figure("Variedades que explican faltantes")
        client_fig = empty_figure("Clientes que explican necesidad")
        variety_table = pd.DataFrame()
        client_table = pd.DataFrame()
        order_table = pd.DataFrame()
    else:
        shortage_keys = faltantes[["fecha_forecast", "producto", "color", "grado"]].drop_duplicates()
        shortage_lines = cruce.merge(shortage_keys, on=["fecha_forecast", "producto", "color", "grado"], how="inner")
        variety_table = (
            shortage_lines.groupby(["producto", "variedad", "color", "grado"], dropna=False, as_index=False)
            .agg(
                demanda=("tallos_estimados", "sum"),
                clientes=("cod_cliente", "nunique"),
                compra_prioridad=("tallos_prioridad_compra_cliente", "sum") if "tallos_prioridad_compra_cliente" in shortage_lines.columns else ("tallos_estimados", "sum"),
                score_promedio=("score_compra_terminada", "mean"),
            )
            .sort_values(["compra_prioridad", "demanda"], ascending=False)
            .head(max(top_n, 20))
        )
        variety_table["item"] = variety_table["producto"].astype(str) + " | " + variety_table["variedad"].astype(str) + " | " + variety_table["color"].astype(str)
        variety_fig = px.bar(
            variety_table,
            x="demanda",
            y="item",
            orientation="h",
            color="color",
            color_discrete_map=color_map_for(variety_table, "color"),
            hover_data=["compra_prioridad", "clientes", "score_promedio"],
            title="Variedades mas demandadas dentro de colores faltantes",
        )
        variety_fig.update_layout(yaxis={"categoryorder": "total ascending"})
        apply_common_layout(variety_fig, 540)

        client_group_cols = [col for col in ["cod_cliente", "cliente", "pais", "recomendacion_compra"] if col in shortage_lines.columns]
        client_table = (
            shortage_lines.groupby(client_group_cols, dropna=False, as_index=False)
            .agg(
                demanda=("tallos_estimados", "sum"),
                compra_prioridad=("tallos_prioridad_compra_cliente", "sum") if "tallos_prioridad_compra_cliente" in shortage_lines.columns else ("tallos_estimados", "sum"),
                lineas=("color", "size"),
                colores=("color", "nunique"),
                score=("score_compra_terminada", "mean"),
            )
            .sort_values(["compra_prioridad", "score", "demanda"], ascending=False)
            .head(max(top_n, 20))
        ) if client_group_cols else pd.DataFrame()
        client_color = "recomendacion_compra" if "recomendacion_compra" in client_table.columns else None
        client_y = "cliente" if "cliente" in client_table.columns else ("cod_cliente" if "cod_cliente" in client_table.columns else None)
        client_fig = (
            px.bar(
                client_table,
                x="compra_prioridad",
                y=client_y,
                orientation="h",
                color=client_color,
                color_discrete_map=color_map_for(client_table, client_color) if client_color else None,
                title="Clientes recomendados para explicar la compra",
            )
            if client_y
            else empty_figure("Clientes que explican necesidad")
        )
        client_fig.update_layout(yaxis={"categoryorder": "total ascending"})
        apply_common_layout(client_fig, 540)

        order_cols = [
            "fecha_forecast",
            "semana_label",
            "cod_cliente",
            "cliente",
            "pais",
            "fuente_demanda",
            "tipo_pedido_operativo",
            "enfoque_analisis_operativo",
            "producto",
            "variedad",
            "color",
            "grado",
            "tipo_caja",
            "tallos_estimados",
            "inventario_color_total",
            "inventario_total",
            "faltante_proyectado_item",
            "tallos_prioridad_compra_cliente",
            "prioridad_compra",
            "score_compra_terminada",
            "recomendacion_compra",
        ]
        shortage_lines = add_week_columns(shortage_lines, "fecha_forecast")
        order_table = shortage_lines[[col for col in order_cols if col in shortage_lines.columns]].sort_values(
            ["tallos_prioridad_compra_cliente", "tallos_estimados"], ascending=False
        ).head(600)

    color_table_cols = [
        "fecha_forecast",
        "semana_label",
        "producto",
        "color",
        "grado",
        "inventario_final_proyectado",
        "faltante_color",
        "sobrante_color",
        "demanda",
        "clientes",
        "pedidos_reales",
        "estado_color",
    ]
    color_table = color_balance[[col for col in color_table_cols if col in color_balance.columns]].sort_values(
        ["faltante_color", "demanda"], ascending=False
    ).head(600)

    product_label = product_filter or "todos"
    color_label = color_filter or "todos"
    return html.Div(
        [
            html.Div(
                [
                    make_card("Faltante proyectado", moneyless_number(faltantes["faltante_color"].sum() if not faltantes.empty else 0), "suma de diferencias negativas dia a dia"),
                    make_card("Colores faltantes", moneyless_number(faltantes[["producto", "color", "grado"]].drop_duplicates().shape[0] if not faltantes.empty else 0), "producto color grado"),
                    make_card("Clientes en faltantes", moneyless_number(order_table["cod_cliente"].nunique() if not order_table.empty and "cod_cliente" in order_table.columns else 0), "demanda asociada"),
                    make_card("Filtro", f"{product_label} / {color_label}", window_detail(reference, week_offset, visible_weeks)),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div(dcc.Graph(figure=day_fig), className="panel"), html.Div(dcc.Graph(figure=color_fig), className="panel")], className="grid-2"),
            html.Div([html.Div(dcc.Graph(figure=variety_fig), className="panel"), html.Div(dcc.Graph(figure=client_fig), className="panel")], className="grid-2 section-gap"),
            html.Div([html.Div("Inventario final proyectado por dia, producto, color y grado", className="panel-title"), make_table(color_table, 16)], className="table-panel"),
            html.Div([html.Div("Variedades que explican faltantes", className="panel-title"), make_table(variety_table.drop(columns=["item"], errors="ignore"), 14)], className="table-panel"),
            html.Div([html.Div("Clientes recomendados para compra", className="panel-title"), make_table(client_table, 14)], className="table-panel"),
            html.Div([html.Div("Pedidos y lineas que contienen esos colores", className="panel-title"), make_table(order_table, 16)], className="table-panel"),
        ]
    )


def render_demanda_tab(
    data: dict[str, pd.DataFrame],
    filtered: pd.DataFrame,
    selected_code: str | None,
    top_n: int,
    compare_mode: str = "none",
    solid_product: str | None = None,
    week_offset: int = 0,
    visible_weeks: int = 4,
    history_weeks: int = 26,
    analysis_scope: str = "solidos",
):
    valid_codes = set(filtered["cod_cliente"]) if not filtered.empty else set()
    demanda = filter_operational_scope(data["demanda"], analysis_scope, solid_product)
    cruce = filter_operational_scope(data["cruce"], analysis_scope, solid_product)
    historico_source = data["historico_solidos"] if analysis_scope == "solidos" else data.get("historico_confirmado", data["historico_solidos"])
    historico = filter_operational_scope(historico_source, analysis_scope, solid_product)
    if selected_code:
        demanda = demanda[demanda["cod_cliente"] == selected_code] if not demanda.empty else demanda
        cruce = cruce[cruce["cod_cliente"] == selected_code] if not cruce.empty else cruce
        historico = historico[historico["cod_cliente"] == selected_code] if not historico.empty else historico
    elif valid_codes:
        demanda = demanda[demanda["cod_cliente"].isin(valid_codes)] if not demanda.empty else demanda
        cruce = cruce[cruce["cod_cliente"].isin(valid_codes)] if not cruce.empty else cruce
        historico = historico[historico["cod_cliente"].isin(valid_codes)] if not historico.empty else historico

    start, end = future_window_bounds(demanda, week_offset, visible_weeks)
    demanda = apply_future_window(demanda, week_offset, visible_weeks)
    cruce = apply_future_window(cruce, week_offset, visible_weeks)
    if start is not None:
        hist_start = start - pd.Timedelta(weeks=3)
        hist_end = start - pd.Timedelta(days=1)
        hist_dates = pd.to_datetime(historico["fecha"], errors="coerce") if not historico.empty else pd.Series(dtype="datetime64[ns]")
        historico_reciente = historico[(hist_dates >= hist_start) & (hist_dates <= hist_end)].copy() if not historico.empty else historico
    else:
        historico_reciente = historico.head(0).copy()

    demanda = add_week_columns(demanda, "fecha_forecast")
    cruce = add_week_columns(cruce, "fecha_forecast")
    historico_reciente = add_week_columns(historico_reciente, "fecha")
    scope_title, scope_detail = scope_label(analysis_scope)

    if demanda.empty:
        demand_line = empty_figure(f"Demanda futura - {scope_title}")
        demand_week = empty_figure(f"Demanda por semana - {scope_title}")
        demand_mix = empty_figure(f"Composicion - {scope_title}")
    else:
        by_date = demanda.groupby(["fecha_forecast", "fecha_semana", "semana_label", "fuente_demanda"], as_index=False)["tallos_estimados"].sum()
        demand_line = px.area(
            by_date,
            x="fecha_forecast",
            y="tallos_estimados",
            color="fuente_demanda",
            color_discrete_map=color_map_for(by_date, "fuente_demanda"),
            hover_data=["fecha_semana", "semana_label"],
            title=f"Demanda futura por fecha, semana y fuente - {scope_title}",
        )
        apply_common_layout(demand_line, 400)

        by_week = demanda.groupby(["semana_label", "fuente_demanda"], as_index=False)["tallos_estimados"].sum()
        demand_week = px.bar(
            by_week,
            x="semana_label",
            y="tallos_estimados",
            color="fuente_demanda",
            color_discrete_map=color_map_for(by_week, "fuente_demanda"),
            barmode="group",
            title=f"Demanda futura por semana - {scope_title}",
        )
        demand_week.update_layout(xaxis_tickangle=-35)
        apply_common_layout(demand_week, 400)

        mix_path = ["familia_analisis_operativa", "tipo_pedido_operativo", "producto", "color"]
        mix_path = [col for col in mix_path if col in demanda.columns]
        mix = (
            demanda.groupby(mix_path, dropna=False, as_index=False)["tallos_estimados"]
            .sum()
            .sort_values("tallos_estimados", ascending=False)
            .head(max(top_n, 15))
        )
        demand_mix = px.sunburst(mix, path=mix_path, values="tallos_estimados", title=f"Composicion de demanda - {scope_title}")
        apply_common_layout(demand_mix, 480)

    if historico_reciente.empty:
        recent_line = empty_figure(f"Demanda real ultimas 3 semanas - {scope_title}")
    else:
        recent = historico_reciente.groupby(["fecha", "fecha_semana", "semana_label", "producto"], dropna=False, as_index=False)["tallos_historicos"].sum()
        recent_line = px.line(
            recent,
            x="fecha",
            y="tallos_historicos",
            color="producto",
            color_discrete_map=color_map_for(recent, "producto"),
            markers=True,
            hover_data=["fecha_semana", "semana_label"],
            title=f"Demanda real recibida en las 3 semanas previas - {scope_title}",
        )
        apply_common_layout(recent_line, 400)

    if cruce.empty:
        risk = empty_figure("Riesgo de disponibilidad")
        priority = empty_figure("Prioridad de compra")
        cruce_table = pd.DataFrame()
    else:
        risk_df = cruce.groupby(["riesgo_disponibilidad"], dropna=False, as_index=False).agg(
            tallos=("tallos_estimados", "sum"),
            faltante=("faltante_proyectado_item", "sum"),
        )
        risk = px.bar(risk_df, x="riesgo_disponibilidad", y=["tallos", "faltante"], barmode="group", title="Riesgo de disponibilidad")
        risk.update_layout(xaxis_tickangle=-35)
        apply_common_layout(risk, 380)

        priority_df = cruce.groupby(["prioridad_compra"], dropna=False, as_index=False)["tallos_prioridad_compra_cliente"].sum()
        priority = px.bar(priority_df, x="prioridad_compra", y="tallos_prioridad_compra_cliente", color="prioridad_compra", color_discrete_map=color_map_for(priority_df, "prioridad_compra"), title="Tallos sugeridos por prioridad de compra")
        priority.update_layout(xaxis_tickangle=-35)
        apply_common_layout(priority, 380)

        cruce_table = (
            cruce.sort_values(["tallos_prioridad_compra_cliente", "tallos_estimados"], ascending=False)
            .head(200)[
                [
                    col
                    for col in [
                        "fecha_forecast",
                        "fecha_semana",
                        "semana_label",
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
                        "tallos_estimados",
                        "inventario_total",
                        "riesgo_disponibilidad",
                        "tallos_prioridad_compra_cliente",
                        "prioridad_compra",
                    ]
                    if col in cruce.columns
                ]
            ]
        )

    last_year_section = []
    if compare_mode and compare_mode != "none":
        last_year_section = build_last_year_demand_section(data, demanda, historico, compare_mode)

    detail_cols = [
        "fecha_forecast",
        "fecha_semana",
        "semana_label",
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
        "fuente_demanda",
        "tallos_estimados",
        "confianza_estimacion",
        "recomendacion_compra",
    ]
    demand_detail = demanda[[col for col in detail_cols if col in demanda.columns]].sort_values(
        ["fecha_forecast", "tallos_estimados"], ascending=[True, False]
    ).head(500) if not demanda.empty else pd.DataFrame()
    producto_label = solid_product if solid_product else "todos los productos"

    return html.Div(
        [
            html.Div(
                [
                    make_card("Lectura", scope_title, scope_detail),
                    make_card("Producto", producto_label, "filtro opcional"),
                    make_card("Lineas demanda", moneyless_number(len(demanda)), "forecast + pendientes"),
                    make_card("Tallos demanda", moneyless_number(demanda["tallos_estimados"].sum() if not demanda.empty else 0), "periodo futuro"),
                    make_card("Lineas inventario", moneyless_number(len(cruce)), "cruce disponible"),
                    make_card(
                        "Ventana",
                        f"{visible_weeks} semanas",
                        window_detail(filter_operational_scope(data["demanda"], analysis_scope, solid_product), week_offset, visible_weeks),
                    ),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div(dcc.Graph(figure=recent_line), className="panel"), html.Div(dcc.Graph(figure=demand_line), className="panel")], className="grid-2"),
            html.Div([html.Div(dcc.Graph(figure=demand_week), className="panel"), html.Div(dcc.Graph(figure=demand_mix), className="panel")], className="grid-2 section-gap"),
            *last_year_section,
            html.Div([html.Div(dcc.Graph(figure=risk), className="panel"), html.Div(dcc.Graph(figure=priority), className="panel")], className="grid-2 section-gap"),
            html.Div([html.Div("Detalle demanda futura", className="panel-title"), make_table(demand_detail, 15)], className="table-panel"),
            html.Div([html.Div("Detalle priorizado inventario", className="panel-title"), make_table(cruce_table, 12)], className="table-panel"),
        ]
    )


def build_last_year_demand_section(data: dict[str, pd.DataFrame], demanda: pd.DataFrame, historico: pd.DataFrame, compare_mode: str):
    if demanda.empty or historico.empty:
        return [html.Div("No hay demanda o historico solido para comparar contra ano anterior.", className="table-panel")]

    demand_week = demanda.copy()
    demand_week["anio_forecast"] = demand_week["fecha_forecast"].dt.isocalendar().year.astype(int)
    demand_week["semana_iso"] = demand_week["fecha_forecast"].dt.isocalendar().week.astype(int)
    demand_week["anio_comparacion"] = demand_week["anio_forecast"] - 1

    future = (
        demand_week.groupby(["anio_forecast", "anio_comparacion", "semana_iso"], as_index=False)["tallos_estimados"]
        .sum()
        .rename(columns={"tallos_estimados": "demanda_modelo_final"})
    )
    if compare_mode == "same_dates":
        start = demanda["fecha_forecast"].min() - pd.DateOffset(years=1)
        end = demanda["fecha_forecast"].max() - pd.DateOffset(years=1)
        hist = historico[(historico["fecha"] >= start) & (historico["fecha"] <= end)].copy()
        if hist.empty:
            return [html.Div("No hay historico solido para las mismas fechas del ano anterior.", className="table-panel")]
        hist["fecha_forecast"] = hist["fecha"] + pd.DateOffset(years=1)
        hist = add_week_columns(hist, "fecha_forecast")
        history = (
            hist.groupby(["fecha_forecast", "semana_label"], as_index=False)["tallos_historicos"]
            .sum()
            .rename(columns={"tallos_historicos": "tallos_anio_anterior"})
        )
        future_dates = demanda.groupby(["fecha_forecast", "semana_label"], as_index=False)["tallos_estimados"].sum().rename(columns={"tallos_estimados": "demanda_modelo_final"})
        comp = future_dates.merge(history, on=["fecha_forecast", "semana_label"], how="left")
        comp["periodo_label"] = comp["fecha_forecast"].dt.strftime("%Y-%m-%d") + " | " + comp["semana_label"]
        title = "Demanda solida vs ano anterior por mismas fechas"
        table_label = "Comparacion por mismas fechas del ano anterior"
    else:
        history = (
            historico.groupby(["anio_iso", "semana_iso"], as_index=False)["tallos_historicos"]
            .sum()
            .rename(columns={"anio_iso": "anio_comparacion", "tallos_historicos": "tallos_anio_anterior"})
        )
        comp = future.merge(history, on=["anio_comparacion", "semana_iso"], how="left")
        comp["periodo_label"] = comp["anio_forecast"].astype(str) + "-W" + comp["semana_iso"].astype(str).str.zfill(2)
        title = "Demanda solida vs ano anterior por mismas semanas"
        table_label = "Comparacion por mismas semanas del ano anterior"

    comp["tallos_anio_anterior"] = comp["tallos_anio_anterior"].fillna(0)
    comp["diferencia_vs_anio_anterior"] = comp["demanda_modelo_final"] - comp["tallos_anio_anterior"]
    comp["pct_vs_anio_anterior"] = np.where(
        comp["tallos_anio_anterior"] > 0,
        comp["diferencia_vs_anio_anterior"] / comp["tallos_anio_anterior"],
        np.nan,
    )
    long = comp.melt(
        id_vars=[col for col in ["periodo_label", "semana_label", "anio_forecast", "anio_comparacion", "semana_iso", "fecha_forecast"] if col in comp.columns],
        value_vars=["demanda_modelo_final", "tallos_anio_anterior"],
        var_name="serie",
        value_name="tallos",
    )
    line = px.line(long, x="periodo_label", y="tallos", color="serie", markers=True, title=title)
    line.update_layout(xaxis_tickangle=-35)
    apply_common_layout(line, 430)

    gap = px.bar(
        comp,
        x="periodo_label",
        y="diferencia_vs_anio_anterior",
        color="diferencia_vs_anio_anterior",
        color_continuous_scale="RdBu",
        title="Diferencia de tallos contra ano anterior",
    )
    gap.update_layout(xaxis_tickangle=-35)
    apply_common_layout(gap, 430)

    detail = comp[
        [
            col
            for col in [
                "periodo_label",
                "semana_label",
                "fecha_forecast",
                "anio_comparacion",
                "semana_iso",
                "demanda_modelo_final",
                "tallos_anio_anterior",
                "diferencia_vs_anio_anterior",
                "pct_vs_anio_anterior",
            ]
            if col in comp.columns
        ]
    ].sort_values("periodo_label")

    return [
        html.Div([html.Div(dcc.Graph(figure=line), className="panel"), html.Div(dcc.Graph(figure=gap), className="panel")], className="grid-2 section-gap"),
        html.Div([html.Div(table_label, className="panel-title"), make_table(detail, 12)], className="table-panel"),
    ]


def render_reserved_module(title: str, message: str) -> html.Div:
    """Muestra una pestaña reservada sin activar flujos que aun no son oficiales."""
    return html.Div(
        [
            html.Div(title, className="panel-title"),
            html.Div(message, className="reading-text"),
        ],
        className="reading-panel",
    )


def render_estructuras_componentes_tab(
    data: dict[str, pd.DataFrame],
    selected_code: str | None,
    top_n: int,
    products=None,
    colors=None,
    years=None,
    week_range=None,
):
    """Resume la orden regular de un cliente a partir de estructuras confirmadas.

    Esta vista deliberadamente no reemplaza el visualizador general. Identifica
    las estructuras repetidas y sus componentes habituales para el cliente y
    periodo seleccionado.
    """
    estructura_caja = data.get("estructura_caja", pd.DataFrame()).copy()
    componentes = data.get("estructura_componentes", pd.DataFrame()).copy()
    catalogo = data.get("catalogo_estructura_version", pd.DataFrame()).copy()

    if not selected_code:
        return html.Div(
            [
                html.Div("Orden regular del cliente", className="panel-title"),
                html.Div("Selecciona un cliente en el panel lateral para ver sus estructuras base mas repetidas.", className="reading-text"),
            ],
            className="reading-panel",
        )
    for name, frame in [("estructura_caja", estructura_caja), ("componentes", componentes), ("catalogo", catalogo)]:
        if not frame.empty and "cod_cliente" in frame.columns:
            subset = frame[frame["cod_cliente"].astype(str).eq(str(selected_code))].copy()
            if name == "estructura_caja":
                estructura_caja = subset
            elif name == "componentes":
                componentes = subset
            else:
                catalogo = subset

    if estructura_caja.empty:
        return html.Div(
            "No hay estructura_caja.csv disponible. Corre el pipeline descriptivo actualizado para generar estructuras y componentes.",
            className="table-panel",
        )

    selected_products = selected_values(products)
    selected_colors = selected_values(colors)
    if not componentes.empty and (selected_products or selected_colors):
        component_scope = componentes.copy()
        if selected_products and "producto" in component_scope.columns:
            component_scope = component_scope[component_scope["producto"].astype(str).isin(selected_products)]
        if selected_colors and "color" in component_scope.columns:
            component_scope = component_scope[component_scope["color"].astype(str).isin(selected_colors)]
        valid_structures = component_scope["estructura_caja_id"].dropna().unique() if "estructura_caja_id" in component_scope else []
        estructura_caja = estructura_caja[estructura_caja["estructura_caja_id"].isin(valid_structures)].copy()
        componentes = componentes[componentes["estructura_caja_id"].isin(valid_structures)].copy()
    if "fecha" in estructura_caja.columns:
        estructura_caja["fecha"] = pd.to_datetime(estructura_caja["fecha"], errors="coerce")
        date_scope = estructura_caja.copy()
        if years:
            date_scope = date_scope[date_scope["fecha"].dt.year.isin([int(year) for year in years])]
        if week_range and len(week_range) == 2:
            iso_week = date_scope["fecha"].dt.isocalendar().week
            date_scope = date_scope[iso_week.between(int(week_range[0]), int(week_range[1]))]
        valid_structures = date_scope["estructura_caja_id"].dropna().unique()
        estructura_caja = date_scope
        if not componentes.empty:
            componentes = componentes[componentes["estructura_caja_id"].isin(valid_structures)].copy()
    if estructura_caja.empty:
        return html.Div("No hay ordenes regulares para los filtros seleccionados.", className="table-panel")

    for frame in [estructura_caja, componentes, catalogo]:
        if not frame.empty:
            for col in [
                "tallos_estructura", "ramos_estimados", "tallos_analisis",
                "participacion_tallos_estructura", "veces_observada",
                "repeticiones_estructura", "estructuras_componente",
            ]:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    regular_agg = {
        "repeticiones": ("repeticiones_estructura", "sum")
        if "repeticiones_estructura" in estructura_caja.columns
        else ("estructura_caja_id", "nunique"),
        "tallos": ("tallos_estructura", "sum"),
        "ramos_estimados": ("ramos_estimados", "sum"),
        "versiones": ("composicion_version_id", "nunique"),
    }
    regular_structures = (
        estructura_caja.groupby(["tipo_pedido_operativo", "sku_operativo", "productos", "colores"], dropna=False, as_index=False)
        .agg(**regular_agg)
        .sort_values(["repeticiones", "tallos"], ascending=False)
        .head(max(top_n, 10))
    )
    fig_top = px.bar(regular_structures, y="sku_operativo", x="repeticiones", color="tipo_pedido_operativo", color_discrete_map=color_map_for(regular_structures, "tipo_pedido_operativo"), orientation="h", title="Ordenes base mas repetidas")
    fig_top.update_layout(yaxis=dict(categoryorder="total ascending"))
    apply_common_layout(fig_top, 430)

    componentes_top = pd.DataFrame()
    if not componentes.empty:
        component_agg = {
            "tallos": ("tallos_analisis", "sum"),
            "estructuras": ("estructuras_componente", "sum")
            if "estructuras_componente" in componentes.columns
            else ("estructura_caja_id", "nunique"),
        }
        componentes_top = (
            componentes.groupby(["tipo_pedido_operativo", "producto", "color", "variedad"], dropna=False, as_index=False)
            .agg(**component_agg)
            .sort_values("tallos", ascending=False)
            .head(max(top_n, 15))
        )

    total_tallos = estructura_caja["tallos_estructura"].sum() if "tallos_estructura" in estructura_caja.columns else 0
    regular = regular_structures.iloc[0] if not regular_structures.empty else None
    regular_name = str(regular["sku_operativo"]) if regular is not None else "sin estructura"
    return html.Div(
        [
            html.Div(
                [
                    html.Div("Orden regular del cliente", className="panel-title"),
                    html.Div(
                        "Esta vista resume la estructura que el cliente repite con mayor frecuencia dentro del periodo filtrado. Usa el Visualizador general para explorar el historial completo.",
                        className="reading-text",
                    ),
                ],
                className="reading-panel",
            ),
            html.Div(
                [
                    make_card("Orden base", regular_name, "estructura mas repetida"),
                    make_card("Repeticiones", moneyless_number(regular["repeticiones"] if regular is not None else 0), "en periodo visible"),
                    make_card(
                        "Estructuras observadas",
                        moneyless_number(
                            estructura_caja["repeticiones_estructura"].sum()
                            if "repeticiones_estructura" in estructura_caja.columns
                            else estructura_caja["estructura_caja_id"].nunique()
                        ),
                        "confirmadas",
                    ),
                    make_card("Tallos", moneyless_number(total_tallos), "periodo filtrado"),
                ],
                className="metrics-grid",
            ),
            html.Div([html.Div([dcc.Graph(figure=fig_top), panel_note("Ordena las estructuras que mas veces se repiten. La primera barra corresponde a la orden regular identificada para el cliente.")], className="panel")], className="section-gap"),
            html.Div([html.Div("Estructuras base habituales", className="panel-title"), panel_note("Resumen de las estructuras recurrentes del cliente; sirve para describir su pedido regular sin entrar al detalle de cada orden."), make_table(regular_structures, 12)], className="table-panel"),
            html.Div([html.Div("Composicion habitual de la orden", className="panel-title"), panel_note("Productos, colores y variedades que componen las estructuras repetidas visibles."), make_table(componentes_top, 15)], className="table-panel"),
        ]
    )


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
    if start_date:
        out = out[out["week_start"] >= pd.to_datetime(start_date)]
    if end_date:
        out = out[out["week_start"] <= pd.to_datetime(end_date)]
    if week_range and len(week_range) == 2 and "semana_iso" in out.columns:
        out = out[
            out["semana_iso"].between(int(week_range[0]), int(week_range[1]), inclusive="both")
        ]
    selections = [
        ("anio", [int(year) for year in (years or [])]),
        ("mercado_cluster", selected_values(markets)),
        ("pais", selected_values(countries)),
        ("cod_cliente", selected_values(clients)),
        ("producto", selected_values(products)),
        ("color", selected_values(colors)),
    ]
    for col, values in selections:
        if values and col in out.columns:
            out = out[out[col].isin(values)]
    return out


def valid_validation_window_starts(frame: pd.DataFrame, year: int | None, window_weeks: int = 8) -> list[int]:
    """Return starts of complete selectable validation windows within an ISO year."""
    if frame.empty or year is None or "anio" not in frame.columns or "semana_iso" not in frame.columns:
        return []
    year_weeks = set(
        pd.to_numeric(frame.loc[frame["anio"].eq(int(year)), "semana_iso"], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )
    return [
        week
        for week in sorted(year_weeks)
        if week + window_weeks - 1 <= 53
        and all((week + offset) in year_weeks for offset in range(window_weeks))
    ]


def forecast_reading_guide() -> html.Div:
    return html.Div(
        [
            html.Div("Guia para leer el forecast de solidos", className="panel-title"),
            html.Div(
                [
                    html.P("1. Alcance comercial: mercado, pais, cliente, producto y color cambian la proyeccion, la validacion y las tablas de demanda."),
                    html.P("2. Proyeccion futura: elige 2, 5 u 8 semanas segun el plazo en el que vas a tomar decisiones."),
                    html.P("3. Historia comparativa: selecciona anos y semanas solo para contrastar el comportamiento real contra la linea futura."),
                    html.P("4. Validacion historica: escoge una ventana ocurrida y revisa WAPE y bias; el backtest final del modelo permanece identificado aparte."),
                    html.P("5. Escenario comercial: modifica probabilidad o volumen para estudiar una hipotesis de negocio; no reentrena el modelo."),
                    html.P("El universo es pedido SOLIDO confirmado y la unidad pronosticada es cliente + producto + color + semana. Grado, caja y tallos por ramo no se predicen en esta etapa."),
                ],
                className="reading-text",
            ),
        ],
        className="reading-panel",
    )


def _forecast_wape(frame: pd.DataFrame, grouping: list[str]) -> float:
    if frame.empty:
        return np.nan
    grouped = frame.groupby(grouping, as_index=False).agg(real=("tallos", "sum"), pred=("prediccion", "sum"))
    total = float(grouped["real"].sum())
    return float((grouped["real"] - grouped["pred"]).abs().sum() / total) if total > 0 else np.nan


def forecast_business_interpretation(block: str, stage: str) -> str:
    """Traduce bloques predictivos a una accion comprensible para negocio."""
    action = {
        "Historia reciente": "Refleja continuidad o cambios recientes en la compra.",
        "Ocurrencia": "Indica recurrencia y probabilidad de que vuelva a comprar.",
        "Estacionalidad": "Captura semanas del ano con patrones repetitivos.",
        "Estacionalidad anual": "Contrasta con la misma temporada del ano anterior.",
        "Estacionalidad de mercado": "Refleja comportamiento estacional del producto-color en el mercado.",
        "Producto-color": "Diferencia la demanda esperada por portafolio y color.",
        "Cliente": "Reconoce patrones propios de la cuenta.",
        "Perfil cliente": "Incorpora cumplimiento y comportamiento comercial historico.",
        "Perfil historico": "Representa el volumen habitual de esa combinacion.",
        "Perfil reciente": "Da contexto al nivel de compra mas reciente.",
        "Cobertura historica": "Mide cuanta evidencia existe para esa combinacion.",
        "Destino comercial": "Distingue dinamicas del mercado o pais destino.",
        "Calendario": "Ubica la prediccion dentro del periodo anual.",
    }.get(str(block), "Aporta senal para diferenciar el comportamiento esperado.")
    use = "ocurre la compra" if str(stage) == "probabilidad_compra" else "volumen esperado"
    return f"{action} Incide en si {use}."


def build_forecast_notes_table(importance: pd.DataFrame) -> pd.DataFrame:
    """Resume predictores globales mas relevantes sin saturar la vista."""
    if importance.empty:
        return pd.DataFrame()
    work = importance.copy()
    work["Importancia"] = pd.to_numeric(work["importancia_positiva"], errors="coerce").fillna(0)
    work = work[work["Importancia"] > 0].copy()
    work = work.sort_values(["etapa_modelo", "Importancia"], ascending=[True, False]).groupby(
        "etapa_modelo", group_keys=False
    ).head(4)
    work["Etapa"] = work["etapa_modelo"].replace(
        {"probabilidad_compra": "Probabilidad de compra", "volumen_si_compra": "Volumen si compra"}
    )
    work["Variable"] = work["variable"]
    work["Que toma el modelo"] = work["descripcion"]
    work["Lectura de negocio"] = [
        forecast_business_interpretation(block, stage)
        for block, stage in zip(work["bloque"], work["etapa_modelo"])
    ]
    return work[["Etapa", "Variable", "Importancia", "Que toma el modelo", "Lectura de negocio"]]


def build_forecast_market_importance_table(
    market_importance: pd.DataFrame,
    markets,
) -> pd.DataFrame:
    """Presenta los predictores mas influyentes del boosting por mercado."""
    if market_importance.empty:
        return pd.DataFrame()
    work = market_importance.copy()
    selected_markets = selected_values(markets)
    if selected_markets:
        work = work[work["mercado_cluster"].astype(str).isin(selected_markets)].copy()
    work["Importancia"] = pd.to_numeric(work["importancia_positiva"], errors="coerce").fillna(0)
    work = work[work["Importancia"] > 0].copy()
    work = work.sort_values(
        ["mercado_cluster", "etapa_modelo", "Importancia"], ascending=[True, True, False]
    ).groupby(["mercado_cluster", "etapa_modelo"], group_keys=False).head(2)
    work["Mercado"] = work["mercado_cluster"].astype(str).str.replace("_", " ", regex=False)
    work["Etapa"] = work["etapa_modelo"].replace(
        {"probabilidad_compra": "Probabilidad de compra", "volumen_si_compra": "Volumen si compra"}
    )
    work["Variable"] = work["variable"]
    work["Interpretacion de negocio"] = [
        forecast_business_interpretation(block, stage)
        for block, stage in zip(work["bloque"], work["etapa_modelo"])
    ]
    return work[["Mercado", "Etapa", "Variable", "Importancia", "Interpretacion de negocio"]]


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
    separado de descriptivos y clusters.
    """
    history = data.get("solid_forecast_weekly", pd.DataFrame())
    future = data.get("solid_forecast_future", pd.DataFrame())
    test = data.get("solid_forecast_test", pd.DataFrame())
    historical_validation = data.get("solid_forecast_historical_validation", pd.DataFrame())
    evaluation = data.get("solid_forecast_eval", pd.DataFrame()).copy()
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
                    html.Div([dcc.Graph(figure=client_fig), panel_note("Prioriza cuentas con mayor volumen previsto en el filtro actual. Confirma primero los clientes con mayor exposición comercial.")], className="panel"),
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
    clusters = data["clusters"]
    if selected_code and not clusters.empty:
        clusters = clusters[clusters["cod_cliente"] == selected_code]

    return html.Div(
        [
            html.Div(
                [
                    html.Div([html.Div("Perfil clientes filtrado", className="panel-title"), make_table(profile_table, 15)], className="table-panel"),
                    html.Div([html.Div("Estado de ordenes", className="panel-title"), make_table(estado, 10)], className="table-panel"),
                ],
                className="grid-2",
            ),
            html.Div([html.Div("Cluster del cliente seleccionado", className="panel-title"), make_table(clusters.head(100), 10)], className="table-panel"),
        ]
    )


if __name__ == "__main__":
    args = parse_args()
    app = build_app(Path(args.data_dir), Path(args.forecast_dir), Path(args.clusters_dir))
    app.run(host=args.host, port=args.port, debug=args.debug)
