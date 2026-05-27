from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .forecast import _date_range_from_args

CLIENT_KEYS = ["cod_cliente", "cliente"]

FORECAST_KEYS = CLIENT_KEYS + [
    "pais",
    "ciudad",
    "tipo_pedido_operativo",
    "subtipo_pedido_operativo",
    "tipo_orden_empaque",
    "tipo_empaque",
    "receta",
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
    "estructura_pedido",
    "sku_terminado",
    "sku_flexible",
    "llave_analisis_operativo",
    "color_componente_key",
    "receta_estructura_key",
]

CATEGORICAL_FEATURES = [
    "cod_cliente",
    "pais",
    "ciudad",
    "tipo_pedido_operativo",
    "subtipo_pedido_operativo",
    "tipo_orden_empaque",
    "tipo_empaque",
    "receta",
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
    "estructura_pedido",
    "sku_flexible",
    "llave_analisis_operativo",
]

NUMERIC_FEATURES = [
    "anio",
    "semana_iso",
    "mes_num",
    "dia_semana_num",
    "semana_sin",
    "semana_cos",
    "mes_sin",
    "mes_cos",
    "dias_desde_inicio",
    "es_semana_floral_pico",
    "lag_1w",
    "lag_2w",
    "lag_4w",
    "lag_8w",
    "same_week_last_year",
    "mediana_key_4w",
    "mediana_key_8w",
    "mediana_key_12w",
    "mediana_key_52w",
    "mediana_key_total",
    "mediana_cliente_semana",
    "mediana_pais_semana_producto_color",
    "observaciones_key_total",
    "observaciones_key_52w",
    "score_compra_terminada",
    "cumplimiento_tallos",
]


@dataclass
class SeasonalModelArtifacts:
    category_maps: dict[str, dict[str, int]]
    first_date: pd.Timestamp
    key_lookup: pd.DataFrame
    seasonal_client_week: pd.DataFrame
    seasonal_country_color: pd.DataFrame
    profiles: pd.DataFrame


def _ensure_forecast_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in FORECAST_KEYS:
        if col not in out.columns:
            out[col] = "sin_info"
    return out


def _peak_week_flag(week: pd.Series) -> pd.Series:
    """Commercial floral peak windows by ISO week.

    This is intentionally broad: it marks weeks where flower demand or color mix
    often changes materially by market, without hardcoding a single country rule.
    """
    return week.isin([5, 6, 7, 8, 18, 19, 20, 21, 22, 44, 45, 46, 47, 48, 49, 50, 51]).astype(int)


def _aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_forecast_columns(df)
    daily = df.groupby(FORECAST_KEYS + ["fecha"], as_index=False).agg(
        tallos_dia=("tallos_analisis", "sum"),
        tallos_confirmados_dia=("tallos_confirmados", "sum"),
        faltante_dia=("faltante_tallos", "sum"),
    )
    iso = daily["fecha"].dt.isocalendar()
    daily["anio"] = iso.year.astype(int)
    daily["semana_iso"] = iso.week.astype(int)
    daily["mes_num"] = daily["fecha"].dt.month.astype(int)
    daily["dia_semana_num"] = daily["fecha"].dt.dayofweek + 1
    return daily


def _build_category_maps(df: pd.DataFrame, max_categories_per_feature: int = 180) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for col in CATEGORICAL_FEATURES:
        values = df[col].fillna("sin_info").astype(str)
        top_values = values.value_counts().head(max_categories_per_feature - 2).index.tolist()
        mapping = {"__otros__": 0, "sin_info": 1}
        for value in top_values:
            if value not in mapping:
                mapping[value] = len(mapping)
        maps[col] = mapping
    return maps


def _encode_categories(df: pd.DataFrame, category_maps: dict[str, dict[str, int]]) -> pd.DataFrame:
    out = df.copy()
    for col, mapping in category_maps.items():
        raw = out[col].fillna("sin_info").astype(str)
        out[col] = raw.map(mapping).fillna(mapping["__otros__"]).astype("int16")
    return out


def _history_stats(daily: pd.DataFrame, as_of_date: pd.Timestamp, lookback_weeks: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    key_cols = FORECAST_KEYS
    hist = daily[daily["fecha"] <= as_of_date].copy()
    recent_52 = hist[hist["fecha"] >= as_of_date - timedelta(weeks=52)]

    stats = hist.groupby(key_cols, as_index=False).agg(
        mediana_key_total=("tallos_dia", "median"),
        observaciones_key_total=("fecha", "nunique"),
    )
    for weeks in [4, 8, 12, 52]:
        tmp = hist[hist["fecha"] >= as_of_date - timedelta(weeks=weeks)].groupby(key_cols, as_index=False).agg(
            **{f"mediana_key_{weeks}w": ("tallos_dia", "median")}
        )
        stats = stats.merge(tmp, on=key_cols, how="left")

    obs_52 = recent_52.groupby(key_cols, as_index=False).agg(observaciones_key_52w=("fecha", "nunique"))
    stats = stats.merge(obs_52, on=key_cols, how="left")

    seasonal_client_week = hist.groupby(CLIENT_KEYS + ["semana_iso"], as_index=False).agg(
        mediana_cliente_semana=("tallos_dia", "median")
    )
    seasonal_country_color = hist.groupby(["pais", "semana_iso", "producto", "color"], as_index=False).agg(
        mediana_pais_semana_producto_color=("tallos_dia", "median")
    )

    same_week_year = hist.groupby(key_cols + ["semana_iso"], as_index=False).agg(
        same_week_last_year=("tallos_dia", "median")
    )
    return stats, seasonal_client_week, seasonal_country_color, same_week_year


def _add_lag_features(rows: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    lookup_small = lookup[FORECAST_KEYS + ["fecha", "tallos_dia"]].copy()
    for weeks, name in [(1, "lag_1w"), (2, "lag_2w"), (4, "lag_4w"), (8, "lag_8w")]:
        lag = lookup_small.rename(columns={"fecha": "_lag_fecha", "tallos_dia": name})
        out["_lag_fecha"] = out["fecha"] - pd.to_timedelta(7 * weeks, unit="D")
        out = out.merge(lag, on=FORECAST_KEYS + ["_lag_fecha"], how="left").drop(columns=["_lag_fecha"])
    return out


def _add_time_features(rows: pd.DataFrame, first_date: pd.Timestamp) -> pd.DataFrame:
    out = rows.copy()
    iso = out["fecha"].dt.isocalendar()
    out["anio"] = iso.year.astype(int)
    out["semana_iso"] = iso.week.astype(int)
    out["mes_num"] = out["fecha"].dt.month.astype(int)
    out["dia_semana_num"] = out["fecha"].dt.dayofweek + 1
    out["semana_sin"] = np.sin(2 * np.pi * out["semana_iso"] / 52.0)
    out["semana_cos"] = np.cos(2 * np.pi * out["semana_iso"] / 52.0)
    out["mes_sin"] = np.sin(2 * np.pi * out["mes_num"] / 12.0)
    out["mes_cos"] = np.cos(2 * np.pi * out["mes_num"] / 12.0)
    out["dias_desde_inicio"] = (out["fecha"] - first_date).dt.days.clip(lower=0)
    out["es_semana_floral_pico"] = _peak_week_flag(out["semana_iso"])
    return out


def _make_feature_frame(rows: pd.DataFrame, artifacts: SeasonalModelArtifacts) -> pd.DataFrame:
    out = _add_time_features(rows, artifacts.first_date)
    out = _add_lag_features(out, artifacts.key_lookup)
    out = out.merge(artifacts.seasonal_client_week, on=CLIENT_KEYS + ["semana_iso"], how="left")
    out = out.merge(artifacts.seasonal_country_color, on=["pais", "semana_iso", "producto", "color"], how="left")
    out = out.merge(artifacts.profiles, on=CLIENT_KEYS, how="left")
    for col in NUMERIC_FEATURES:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out = _encode_categories(out, artifacts.category_maps)
    return out[CATEGORICAL_FEATURES + NUMERIC_FEATURES]


def _candidate_structures(
    daily: pd.DataFrame,
    dates: pd.DatetimeIndex,
    lookback_weeks: int,
    max_candidate_structures: int,
    active_clients: pd.DataFrame,
) -> pd.DataFrame:
    max_hist_date = daily["fecha"].max()
    min_recent = max_hist_date - timedelta(weeks=max(lookback_weeks, 12))
    target_weeks = set(pd.Series(dates).dt.isocalendar().week.astype(int).tolist())
    seasonal_weeks = set()
    for week in target_weeks:
        seasonal_weeks.update([((week - 2 - 1) % 52) + 1, ((week - 1 - 1) % 52) + 1, week, (week % 52) + 1, ((week + 1) % 52) + 1])

    recent = daily[daily["fecha"] >= min_recent].merge(active_clients, on=CLIENT_KEYS, how="inner")
    seasonal = daily[daily["semana_iso"].isin(seasonal_weeks)]
    seasonal = seasonal.merge(active_clients, on=CLIENT_KEYS, how="inner")
    recent_keys = recent[FORECAST_KEYS].drop_duplicates().assign(_seen_recent=1)
    candidate_source = pd.concat([recent, seasonal], ignore_index=True)

    ranked = candidate_source.groupby(FORECAST_KEYS, as_index=False).agg(
        tallos_base=("tallos_dia", "sum"),
        observaciones_candidato=("fecha", "nunique"),
        ultima_fecha=("fecha", "max"),
    )
    ranked = ranked.merge(recent_keys, on=FORECAST_KEYS, how="left")
    ranked = ranked[(ranked["_seen_recent"].eq(1)) | (ranked["ultima_fecha"] >= min_recent)].copy()
    ranked = ranked.sort_values(["ultima_fecha", "observaciones_candidato", "tallos_base"], ascending=[False, False, False])
    ranked = ranked.head(max_candidate_structures)

    return ranked[FORECAST_KEYS].drop_duplicates().reset_index(drop=True)


def _fit_model(train_features: pd.DataFrame, target: pd.Series, sample_weight: pd.Series) -> HistGradientBoostingRegressor:
    categorical_mask = [col in CATEGORICAL_FEATURES for col in train_features.columns]
    model = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.06,
        max_iter=180,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        min_samples_leaf=25,
        categorical_features=categorical_mask,
        random_state=42,
    )
    model.fit(train_features, np.log1p(target.clip(lower=0)), sample_weight=sample_weight)
    return model


def build_seasonal_boosting_forecast(
    df: pd.DataFrame,
    client_profile: pd.DataFrame,
    baseline_forecast: pd.DataFrame | None = None,
    target_start: Optional[str] = None,
    target_end: Optional[str] = None,
    horizon_days: int = 7,
    lookback_weeks: int = 8,
    min_score: float = 0,
    max_client_inactive_weeks: int = 16,
    min_recent_active_weeks: int = 2,
    max_train_rows: int = 250_000,
    max_candidate_structures: int = 80_000,
) -> pd.DataFrame:
    """Forecast structural demand with a seasonal gradient boosting model.

    The model keeps the business semantics of the MVP: it learns only from
    Confirmado rows, uses recent behavior with higher weight, and adds explicit
    seasonality by ISO week, country, product/color and floral peak windows.
    """
    if df.empty or client_profile.empty:
        return pd.DataFrame()

    daily = _aggregate_daily(df)
    if daily.empty or len(daily) < 50:
        fallback = baseline_forecast.copy() if baseline_forecast is not None else pd.DataFrame()
        if not fallback.empty:
            fallback["fuente_demanda"] = "FORECAST_MODELO_ESTACIONAL_FALLBACK_BASELINE"
            fallback["version_modelo"] = "fallback_baseline_por_poca_historia"
        return fallback

    dates = _date_range_from_args(df, target_start, target_end, horizon_days)
    max_hist_date = daily["fecha"].max()
    min_hist_date = max_hist_date - timedelta(weeks=lookback_weeks)
    active_cutoff = max_hist_date - timedelta(weeks=max_client_inactive_weeks)
    recent_daily = daily[daily["fecha"] >= min_hist_date]
    client_activity = daily.groupby(CLIENT_KEYS, as_index=False).agg(ultima_fecha_confirmada=("fecha", "max"))
    recent_activity = recent_daily.groupby(CLIENT_KEYS, as_index=False).agg(semanas_activas_recientes=("fecha", "nunique"))
    client_activity = client_activity.merge(recent_activity, on=CLIENT_KEYS, how="left").fillna({"semanas_activas_recientes": 0})
    active_clients = client_activity[
        (client_activity["ultima_fecha_confirmada"] >= active_cutoff)
        & (client_activity["semanas_activas_recientes"] >= min_recent_active_weeks)
    ][CLIENT_KEYS]
    if active_clients.empty:
        return pd.DataFrame()
    daily = daily.merge(active_clients, on=CLIENT_KEYS, how="inner")
    profiles = client_profile[CLIENT_KEYS + ["score_compra_terminada", "recomendacion_compra", "cumplimiento_tallos"]].copy()
    profiles["score_compra_terminada"] = pd.to_numeric(profiles["score_compra_terminada"], errors="coerce").fillna(0)
    profiles["cumplimiento_tallos"] = pd.to_numeric(profiles["cumplimiento_tallos"], errors="coerce").fillna(0)

    stats, seasonal_client_week, seasonal_country_color, same_week_year = _history_stats(daily, max_hist_date, lookback_weeks)
    training = daily.merge(stats, on=FORECAST_KEYS, how="left")
    training = training.merge(same_week_year, on=FORECAST_KEYS + ["semana_iso"], how="left")

    # Keep the model tractable for large operational extracts while preserving
    # recent and high-volume behavior.
    training["_recency_days"] = (max_hist_date - training["fecha"]).dt.days
    training["_rank_weight"] = training["tallos_dia"] * 0.3 + np.maximum(365 - training["_recency_days"], 0)
    if len(training) > max_train_rows:
        recent_cutoff = max_hist_date - timedelta(weeks=52)
        recent = training[training["fecha"] >= recent_cutoff]
        older = training[training["fecha"] < recent_cutoff].sort_values("_rank_weight", ascending=False)
        training = pd.concat([recent, older.head(max(max_train_rows - len(recent), 0))], ignore_index=True).head(max_train_rows)

    artifacts = SeasonalModelArtifacts(
        category_maps=_build_category_maps(training),
        first_date=daily["fecha"].min(),
        key_lookup=daily,
        seasonal_client_week=seasonal_client_week,
        seasonal_country_color=seasonal_country_color,
        profiles=profiles,
    )
    train_features = _make_feature_frame(training, artifacts)
    target = training["tallos_dia"].astype(float)
    recency_weight = 1 + 3 * np.exp(-training["_recency_days"].clip(lower=0) / 180)
    peak_weight = 1 + 0.2 * _peak_week_flag(training["semana_iso"])
    sample_weight = recency_weight * peak_weight
    model = _fit_model(train_features, target, sample_weight)

    candidates = _candidate_structures(daily, dates, lookback_weeks, max_candidate_structures, active_clients)
    if candidates.empty:
        return pd.DataFrame()
    rows = []
    for target_date in dates:
        tmp = candidates.copy()
        tmp["fecha"] = target_date
        rows.append(tmp)
    future = pd.concat(rows, ignore_index=True)
    future = future.merge(stats, on=FORECAST_KEYS, how="left")
    future = _add_time_features(future, artifacts.first_date)
    future = future.merge(same_week_year, on=FORECAST_KEYS + ["semana_iso"], how="left")
    future = future.merge(seasonal_country_color, on=["pais", "semana_iso", "producto", "color"], how="left")

    features = _make_feature_frame(future, artifacts)
    predicted = np.expm1(model.predict(features))
    future["tallos_estimados"] = np.maximum(predicted, 0).round(0).astype(int)
    recent_cap = future[["mediana_key_4w", "mediana_key_8w", "mediana_key_12w", "same_week_last_year", "mediana_key_52w"]].max(axis=1).fillna(0)
    fallback_cap = future["mediana_key_total"].fillna(0)
    cap = np.maximum(recent_cap, fallback_cap.where(recent_cap.gt(0), 0)) * 1.35
    future = future[cap > 0].copy()
    cap = cap.loc[future.index]
    future["tallos_estimados"] = np.minimum(future["tallos_estimados"], np.ceil(cap)).astype(int)
    future = future[future["tallos_estimados"] > 0].copy()

    future = future.merge(profiles, on=CLIENT_KEYS, how="left", suffixes=("", "_perfil"))
    future["score_compra_terminada"] = future["score_compra_terminada"].fillna(0)
    future = future[future["score_compra_terminada"] >= min_score].copy()
    if future.empty:
        return future

    obs_total = future["observaciones_key_total"].fillna(0)
    obs_recent = future["observaciones_key_52w"].fillna(0)
    season_signal = future["mediana_pais_semana_producto_color"].fillna(0).gt(0).astype(float) * 15
    confidence = (
        np.minimum(obs_recent / max(lookback_weeks, 1), 1) * 35
        + np.minimum(obs_total / 10, 1) * 20
        + future["score_compra_terminada"].fillna(0) * 0.30
        + season_signal
    )
    future["confianza_estimacion"] = confidence.clip(0, 100).round(2)
    future["fecha_forecast"] = future["fecha"]
    future["anio_forecast"] = future["fecha_forecast"].dt.isocalendar().year.astype(int)
    future["semana_forecast"] = future["fecha_forecast"].dt.isocalendar().week.astype(int)
    future["dia_semana_forecast"] = future["fecha_forecast"].dt.dayofweek + 1
    future["fuente_demanda"] = "FORECAST_MODELO_ESTACIONAL"
    future["version_modelo"] = f"hist_gradient_boosting_seasonal_country_week_lags_{lookback_weeks}w"
    future["observaciones_mismo_dia"] = future["observaciones_key_52w"].fillna(0)
    future["observaciones_generales"] = future["observaciones_key_total"].fillna(0)

    cols = [
        "fecha_forecast",
        "anio_forecast",
        "semana_forecast",
        "dia_semana_forecast",
        *FORECAST_KEYS,
        "fuente_demanda",
        "tallos_estimados",
        "observaciones_mismo_dia",
        "observaciones_generales",
        "score_compra_terminada",
        "recomendacion_compra",
        "cumplimiento_tallos",
        "confianza_estimacion",
        "version_modelo",
    ]
    return future[cols].sort_values(["fecha_forecast", "cod_cliente", "tallos_estimados"], ascending=[True, True, False]).reset_index(drop=True)

