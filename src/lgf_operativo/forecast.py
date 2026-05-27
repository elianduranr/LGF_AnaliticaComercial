from __future__ import annotations

from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd

CLIENT_KEYS = ["cod_cliente", "cliente"]


def _date_range_from_args(df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str], horizon_days: int) -> pd.DatetimeIndex:
    if start_date:
        start = pd.to_datetime(start_date)
    else:
        start = df["fecha"].max() + timedelta(days=1)
    if end_date:
        end = pd.to_datetime(end_date)
    else:
        end = start + timedelta(days=horizon_days - 1)
    return pd.date_range(start=start, end=end, freq="D")


def build_structural_forecast(
    df: pd.DataFrame,
    client_profile: pd.DataFrame,
    target_start: Optional[str] = None,
    target_end: Optional[str] = None,
    horizon_days: int = 7,
    lookback_weeks: int = 8,
    min_score: float = 0,
    max_client_inactive_weeks: int = 16,
    min_recent_active_weeks: int = 2,
) -> pd.DataFrame:
    """Forecast future order structure by client/date/SKU.

    Use ONLY confirmed historical orders as input. Pending orders are not forecast; they are real future demand.
    """
    if df.empty or client_profile.empty:
        return pd.DataFrame()

    dates = _date_range_from_args(df, target_start, target_end, horizon_days)
    max_hist_date = df["fecha"].max()
    min_hist_date = max_hist_date - timedelta(weeks=lookback_weeks)
    recent = df[(df["fecha"] >= min_hist_date) & (df["fecha"] <= max_hist_date)].copy()
    if recent.empty:
        recent = df.copy()

    active_cutoff = max_hist_date - timedelta(weeks=max_client_inactive_weeks)
    client_activity = df.groupby(CLIENT_KEYS, as_index=False).agg(ultima_fecha_confirmada=("fecha", "max"))
    recent_activity = recent.groupby(CLIENT_KEYS, as_index=False).agg(semanas_activas_recientes=("anio_semana", "nunique"))
    client_activity = client_activity.merge(recent_activity, on=CLIENT_KEYS, how="left").fillna({"semanas_activas_recientes": 0})
    active_clients = client_activity[
        (client_activity["ultima_fecha_confirmada"] >= active_cutoff)
        & (client_activity["semanas_activas_recientes"] >= min_recent_active_weeks)
    ][CLIENT_KEYS]
    recent = recent.merge(active_clients, on=CLIENT_KEYS, how="inner")
    if recent.empty:
        return pd.DataFrame()

    key_cols = CLIENT_KEYS + [
        "pais", "ciudad",
        "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta",
        "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo",
        "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo",
        "capuchon", "comida", "empaque", "estructura_pedido", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key",
    ]
    recent_daily = recent.groupby(key_cols + ["dia_semana_num", "fecha"], as_index=False).agg(
        tallos_dia=("tallos_analisis", "sum"),
        tallos_confirmados_dia=("tallos_confirmados", "sum"),
        faltante_dia=("faltante_tallos", "sum"),
    )

    profiles = client_profile[CLIENT_KEYS + ["score_compra_terminada", "recomendacion_compra", "cumplimiento_tallos"]].copy()
    rows = []
    for target_date in dates:
        dow = target_date.dayofweek + 1
        same_dow = recent_daily[recent_daily["dia_semana_num"] == dow]
        if same_dow.empty:
            same_dow = recent_daily

        agg_same = same_dow.groupby(key_cols, as_index=False).agg(
            tallos_estimados=("tallos_dia", "median"),
            observaciones_mismo_dia=("fecha", "nunique"),
            promedio_mismo_dia=("tallos_dia", "mean"),
        )
        agg_any = recent_daily.groupby(key_cols, as_index=False).agg(
            mediana_reciente_general=("tallos_dia", "median"),
            observaciones_generales=("fecha", "nunique"),
        )
        f = agg_same.merge(agg_any, on=key_cols, how="outer")
        f["tallos_estimados"] = f["tallos_estimados"].fillna(f["mediana_reciente_general"]).fillna(0)
        f["observaciones_mismo_dia"] = f["observaciones_mismo_dia"].fillna(0)
        f["observaciones_generales"] = f["observaciones_generales"].fillna(0)
        f = f[f["tallos_estimados"] > 0].copy()
        f["fecha_forecast"] = target_date
        rows.append(f)

    if not rows:
        return pd.DataFrame()
    forecast = pd.concat(rows, ignore_index=True)
    forecast = forecast.merge(profiles, on=CLIENT_KEYS, how="left")
    forecast["score_compra_terminada"] = forecast["score_compra_terminada"].fillna(0)
    forecast = forecast[forecast["score_compra_terminada"] >= min_score].copy()

    obs_score = np.minimum(forecast["observaciones_mismo_dia"].fillna(0) / max(lookback_weeks, 1), 1) * 100
    forecast["confianza_estimacion"] = (0.55 * obs_score + 0.45 * forecast["score_compra_terminada"]).round(2)
    forecast["tallos_estimados"] = forecast["tallos_estimados"].round(0).astype(int)
    forecast["anio_forecast"] = forecast["fecha_forecast"].dt.isocalendar().year.astype(int)
    forecast["semana_forecast"] = forecast["fecha_forecast"].dt.isocalendar().week.astype(int)
    forecast["dia_semana_forecast"] = forecast["fecha_forecast"].dt.dayofweek + 1
    forecast["version_modelo"] = f"baseline_median_confirmed_{lookback_weeks}w_same_weekday"
    forecast["fuente_demanda"] = "FORECAST_HISTORICO_CONFIRMADO"

    cols = [
        "fecha_forecast", "anio_forecast", "semana_forecast", "dia_semana_forecast",
        "cod_cliente", "cliente", "pais", "ciudad", "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta",
        "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo",
        "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo",
        "capuchon", "comida", "empaque", "estructura_pedido", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key", "fuente_demanda",
        "tallos_estimados", "observaciones_mismo_dia", "observaciones_generales",
        "score_compra_terminada", "recomendacion_compra", "cumplimiento_tallos", "confianza_estimacion", "version_modelo",
    ]
    return forecast[cols].sort_values(["fecha_forecast", "cod_cliente", "tallos_estimados"], ascending=[True, True, False]).reset_index(drop=True)


def pending_orders_to_forecast_format(pending: pd.DataFrame, client_profile: pd.DataFrame | None = None) -> pd.DataFrame:
    """Convert real future pending orders into the same structure used by forecast/inventory cross.

    These rows must be treated as stronger than historical forecast because Pendiente = real order received.
    """
    if pending is None or pending.empty:
        return pd.DataFrame()
    keys = CLIENT_KEYS + [
        "pais", "ciudad",
        "fecha", "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta",
        "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo",
        "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo",
        "capuchon", "comida", "empaque", "estructura_pedido", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key",
    ]
    out = pending.groupby(keys, as_index=False).agg(
        tallos_estimados=("tallos_analisis", "sum"),
        tallos_confirmados_pendiente=("tallos_confirmados", "sum"),
        lineas=("sku_terminado", "size"),
    ).rename(columns={"fecha": "fecha_forecast"})

    out["anio_forecast"] = out["fecha_forecast"].dt.isocalendar().year.astype(int)
    out["semana_forecast"] = out["fecha_forecast"].dt.isocalendar().week.astype(int)
    out["dia_semana_forecast"] = out["fecha_forecast"].dt.dayofweek + 1
    out["observaciones_mismo_dia"] = np.nan
    out["observaciones_generales"] = np.nan
    out["fuente_demanda"] = "PENDIENTE_REAL_CLIENTE"
    out["version_modelo"] = "orden_pendiente_real_cliente"
    out["confianza_estimacion"] = 100.0

    if client_profile is not None and not client_profile.empty:
        prof = client_profile[CLIENT_KEYS + ["score_compra_terminada", "recomendacion_compra", "cumplimiento_tallos"]]
        out = out.merge(prof, on=CLIENT_KEYS, how="left")
    else:
        out["score_compra_terminada"] = np.nan
        out["recomendacion_compra"] = "PENDIENTE_REAL_CLIENTE"
        out["cumplimiento_tallos"] = np.nan

    out["score_compra_terminada"] = out["score_compra_terminada"].fillna(0)
    out["recomendacion_compra"] = out["recomendacion_compra"].fillna("PENDIENTE_REAL_CLIENTE")
    cols = [
        "fecha_forecast", "anio_forecast", "semana_forecast", "dia_semana_forecast",
        "cod_cliente", "cliente", "pais", "ciudad", "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta",
        "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo",
        "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo",
        "capuchon", "comida", "empaque", "estructura_pedido", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key", "fuente_demanda",
        "tallos_estimados", "observaciones_mismo_dia", "observaciones_generales",
        "score_compra_terminada", "recomendacion_compra", "cumplimiento_tallos", "confianza_estimacion", "version_modelo",
    ]
    return out[cols].sort_values(["fecha_forecast", "cod_cliente", "tallos_estimados"], ascending=[True, True, False]).reset_index(drop=True)


def combine_pending_and_forecast(pending_forecast: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    """Use pending real orders first; add forecast only for client/date combinations without pending."""
    if pending_forecast is None or pending_forecast.empty:
        return forecast.copy() if forecast is not None else pd.DataFrame()
    if forecast is None or forecast.empty:
        return pending_forecast.copy()

    pending_keys = pending_forecast[["fecha_forecast", "cod_cliente"]].drop_duplicates()
    fc = forecast.merge(pending_keys.assign(_has_pending=1), on=["fecha_forecast", "cod_cliente"], how="left")
    fc = fc[fc["_has_pending"].isna()].drop(columns=["_has_pending"])
    out = pd.concat([pending_forecast, fc], ignore_index=True)
    return out.sort_values(["fecha_forecast", "cod_cliente", "fuente_demanda", "tallos_estimados"], ascending=[True, True, True, False]).reset_index(drop=True)


def compare_forecast_vs_real(forecast: pd.DataFrame, real_clean: pd.DataFrame) -> pd.DataFrame:
    if forecast.empty or real_clean.empty:
        return pd.DataFrame()
    key_cols = CLIENT_KEYS + ["pais", "ciudad", "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta", "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo", "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque", "estructura_pedido", "sku_terminado", "llave_analisis_operativo", "color_componente_key", "receta_estructura_key"]
    real = real_clean.copy().rename(columns={"fecha": "fecha_forecast"})
    real_agg = real.groupby(["fecha_forecast"] + key_cols, as_index=False).agg(
        tallos_reales=("tallos_analisis", "sum"),
        tallos_confirmados_reales=("tallos_confirmados", "sum"),
        faltante_real=("faltante_tallos", "sum"),
    )
    fcst = forecast.groupby(["fecha_forecast"] + key_cols, as_index=False).agg(
        tallos_estimados=("tallos_estimados", "sum"),
        confianza_estimacion=("confianza_estimacion", "mean"),
    )
    out = fcst.merge(real_agg, on=["fecha_forecast"] + key_cols, how="outer").fillna({
        "tallos_estimados": 0,
        "tallos_reales": 0,
        "tallos_confirmados_reales": 0,
        "faltante_real": 0,
    })
    out["diferencia_estimado_real"] = out["tallos_estimados"] - out["tallos_reales"]
    out["error_abs"] = out["diferencia_estimado_real"].abs()
    out["error_pct"] = np.where(out["tallos_reales"] > 0, out["error_abs"] / out["tallos_reales"], np.nan)
    out["bias"] = np.where(out["diferencia_estimado_real"] > 0, "SOBRE_ESTIMA", np.where(out["diferencia_estimado_real"] < 0, "SUB_ESTIMA", "OK"))
    out["match_sku"] = (out["tallos_estimados"] > 0) & (out["tallos_reales"] > 0)
    return out.sort_values(["fecha_forecast", "cod_cliente", "error_abs"], ascending=[True, True, False]).reset_index(drop=True)
