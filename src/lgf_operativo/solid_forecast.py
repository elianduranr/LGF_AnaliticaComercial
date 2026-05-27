from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .clustering import classify_market
from .io_utils import write_outputs


CLIENT_KEYS = ["cod_cliente", "cliente"]

KEY_COLS = [
    "cod_cliente",
    "cliente",
    "mercado_cluster",
    "pais",
    "producto",
    "color",
]

CATEGORICAL_FEATURES = [
    "cod_cliente",
    "mercado_cluster",
    "pais",
    "producto",
    "color",
    "fase_temporada_floral",
]

NUMERIC_FEATURES = [
    "anio",
    "semana_iso",
    "mes_num",
    "semana_sin",
    "semana_cos",
    "mes_sin",
    "mes_cos",
    "es_semana_floral_pico",
    "es_semana_post_fiesta",
    "distancia_pico_floral",
    "tallos_lag_1w",
    "tallos_lag_2w",
    "tallos_lag_4w",
    "tallos_same_week_prev_year",
    "factor_tendencia_mercado",
    "tallos_same_week_prev_year_ajustado_mercado",
    "rolling_mean_4w",
    "rolling_median_8w",
    "rolling_median_12w",
    "activo_lag_1w",
    "activo_lag_2w",
    "actividad_rolling_8w",
    "actividad_rolling_26w",
    "mediana_key_total",
    "mediana_key_recent",
    "mediana_cliente_producto_color",
    "mediana_mercado_producto_color_semana",
    "indice_estacional_mercado_producto_color_semana",
    "observaciones_key",
    "semanas_activas_cliente",
    "score_compra_terminada",
    "cumplimiento_tallos",
]

FEATURE_METADATA = {
    "cod_cliente": ("Cliente", "Identidad del cliente y sus patrones historicos."),
    "mercado_cluster": ("Destino comercial", "Grupo de mercado definido comercialmente."),
    "pais": ("Destino comercial", "Pais destino del pedido."),
    "producto": ("Producto-color", "Producto solido solicitado."),
    "color": ("Producto-color", "Color solicitado dentro del producto."),
    "fase_temporada_floral": ("Estacionalidad", "Fase comercial de temporada: preparacion, pico, salida posterior o semana regular."),
    "anio": ("Calendario", "Ano de la semana observada."),
    "semana_iso": ("Estacionalidad", "Numero de semana del ano."),
    "mes_num": ("Calendario", "Mes calendario."),
    "semana_sin": ("Estacionalidad", "Representacion ciclica de semana del ano."),
    "semana_cos": ("Estacionalidad", "Representacion ciclica de semana del ano."),
    "mes_sin": ("Estacionalidad", "Representacion ciclica de mes."),
    "mes_cos": ("Estacionalidad", "Representacion ciclica de mes."),
    "es_semana_floral_pico": ("Estacionalidad", "Semana asociada a temporadas florales comerciales."),
    "es_semana_post_fiesta": ("Estacionalidad", "Semana inmediatamente posterior a una temporada floral, donde la demanda suele normalizarse."),
    "distancia_pico_floral": ("Estacionalidad", "Distancia en semanas al pico floral mas cercano para aprender subidas y caidas alrededor de la fecha."),
    "tallos_lag_1w": ("Historia reciente", "Tallos observados una semana antes."),
    "tallos_lag_2w": ("Historia reciente", "Tallos observados dos semanas antes."),
    "tallos_lag_4w": ("Historia reciente", "Tallos observados cuatro semanas antes."),
    "tallos_same_week_prev_year": ("Estacionalidad anual", "Tallos de la misma semana del ano anterior."),
    "factor_tendencia_mercado": ("Tendencia de mercado", "Cambio de nivel del mercado observado entre los dos anos completos previos."),
    "tallos_same_week_prev_year_ajustado_mercado": ("Estacionalidad anual", "Misma semana del ano anterior ajustada por tendencia previa del mercado."),
    "rolling_mean_4w": ("Historia reciente", "Promedio de tallos de las ultimas cuatro semanas."),
    "rolling_median_8w": ("Historia reciente", "Mediana de tallos de las ultimas ocho semanas."),
    "rolling_median_12w": ("Historia reciente", "Mediana de tallos de las ultimas doce semanas."),
    "activo_lag_1w": ("Ocurrencia", "Indica compra en la semana previa."),
    "activo_lag_2w": ("Ocurrencia", "Indica compra dos semanas antes."),
    "actividad_rolling_8w": ("Ocurrencia", "Frecuencia de semanas con compra en ocho semanas."),
    "actividad_rolling_26w": ("Ocurrencia", "Frecuencia de semanas con compra en veintiseis semanas."),
    "mediana_key_total": ("Perfil historico", "Mediana historica del cliente-producto-color."),
    "mediana_key_recent": ("Perfil reciente", "Mediana reciente del cliente-producto-color."),
    "mediana_cliente_producto_color": ("Perfil historico", "Mediana del color-producto para el cliente."),
    "mediana_mercado_producto_color_semana": ("Estacionalidad de mercado", "Mediana del producto-color en el mercado para esa semana."),
    "indice_estacional_mercado_producto_color_semana": ("Estacionalidad de mercado", "Nivel habitual de la semana frente al nivel normal del producto-color dentro del mercado."),
    "observaciones_key": ("Cobertura historica", "Semanas historicas con compra de la combinacion."),
    "semanas_activas_cliente": ("Cobertura historica", "Semanas activas del cliente."),
    "score_compra_terminada": ("Perfil cliente", "Score descriptivo del cliente, si esta disponible."),
    "cumplimiento_tallos": ("Perfil cliente", "Cumplimiento historico del cliente, si esta disponible."),
}


@dataclass(frozen=True)
class SolidForecastConfig:
    test_weeks: int = 8
    lookback_weeks: int = 8
    horizon_weeks: int = 8
    min_train_weeks: int = 52
    min_nonzero_observations: int = 3
    min_total_tallos_key: int = 500
    active_key_weeks: int = 52
    max_rows: int = 150_000
    random_state: int = 42


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _floral_phase(week: pd.Series) -> pd.Series:
    """Label commercial phases inferred from recurrent weekly demand peaks."""
    phase = pd.Series("REGULAR", index=week.index, dtype="object")
    phase.loc[week.eq(4)] = "PRE_SAN_VALENTIN"
    phase.loc[week.eq(5)] = "PICO_SAN_VALENTIN"
    phase.loc[week.isin([6, 7])] = "POST_SAN_VALENTIN"
    phase.loc[week.eq(8)] = "PRE_DIA_MUJER"
    phase.loc[week.eq(9)] = "PICO_DIA_MUJER"
    phase.loc[week.eq(10)] = "POST_DIA_MUJER"
    phase.loc[week.isin([16, 17])] = "PRE_MADRES"
    phase.loc[week.isin([18, 19])] = "PICO_MADRES"
    phase.loc[week.isin([20, 21, 22])] = "POST_MADRES"
    phase.loc[week.isin([48])] = "PRE_FIN_ANO"
    phase.loc[week.isin([49, 50])] = "PICO_FIN_ANO"
    phase.loc[week.isin([51, 52])] = "POST_FIN_ANO"
    return phase


def _peak_week_flag(week: pd.Series) -> pd.Series:
    phase = _floral_phase(week)
    return phase.str.startswith(("PRE_", "PICO_")).astype(int)


def _post_floral_flag(week: pd.Series) -> pd.Series:
    return _floral_phase(week).str.startswith("POST_").astype(int)


def _distance_to_floral_peak(week: pd.Series) -> pd.Series:
    peaks = np.array([5, 9, 18, 19, 49, 50])
    values = pd.to_numeric(week, errors="coerce").fillna(0).astype(int).to_numpy()
    return pd.Series(np.min(np.abs(values[:, None] - peaks), axis=1), index=week.index)


def _market_year_growth(history: pd.DataFrame) -> pd.DataFrame:
    """Return market growth usable for each target year without future leakage."""
    if history.empty:
        return pd.DataFrame(columns=["mercado_cluster", "anio", "factor_tendencia_mercado"])
    annual = (
        history.groupby(["mercado_cluster", "anio"], as_index=False)["tallos"]
        .sum()
        .sort_values(["mercado_cluster", "anio"])
    )
    annual["previous_total"] = annual.groupby("mercado_cluster")["tallos"].shift(1)
    annual["factor_tendencia_mercado"] = (
        annual["tallos"] / annual["previous_total"].replace(0, np.nan)
    ).clip(lower=0.75, upper=1.35)
    annual["anio"] = annual["anio"] + 1
    return annual[["mercado_cluster", "anio", "factor_tendencia_mercado"]]


def _seasonal_hybrid_prediction(frame: pd.DataFrame, boosting_col: str) -> pd.Series:
    """Blend boosting with adjusted annual seasonality only before/during peaks."""
    boosting = _safe_num(frame[boosting_col])
    seasonal = _safe_num(frame["tallos_same_week_prev_year_ajustado_mercado"])
    seasonal_weight = np.where(
        frame["es_semana_floral_pico"].gt(0),
        0.80,
        np.where(frame["es_semana_post_fiesta"].gt(0), 0.0, 0.40),
    )
    blended = seasonal_weight * seasonal + (1 - seasonal_weight) * boosting
    return pd.Series(np.where(seasonal > 0, blended, boosting), index=frame.index)


def _boosting_volume_cap(frame: pd.DataFrame) -> pd.Series:
    """Limit unstable extremes without suppressing an observed annual peak."""
    anchor_cols = [
        "rolling_median_8w",
        "rolling_median_12w",
        "mediana_key_total",
        "mediana_mercado_producto_color_semana",
        "tallos_same_week_prev_year_ajustado_mercado",
    ]
    available = [col for col in anchor_cols if col in frame.columns]
    base = frame[available].max(axis=1).fillna(0) if available else pd.Series(0, index=frame.index)
    multiplier = np.where(frame["es_semana_floral_pico"].gt(0), 2.4, 1.8)
    return base * multiplier


def _prepare_solids(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for col in [
        "fecha",
        "cod_cliente",
        "cliente",
        "pais",
        "producto",
        "color",
        "variedad",
        "grado",
        "tipo_caja",
        "tallos_x_ramo",
        "capuchon",
        "comida",
        "empaque",
        "sku_operativo",
        "sku_terminado",
        "tipo_pedido_operativo",
        "tallos_analisis",
        "tallos_confirmados",
        "faltante_tallos",
    ]:
        if col not in work.columns:
            work[col] = np.nan
    work["fecha"] = pd.to_datetime(work["fecha"], errors="coerce")
    work = work[work["fecha"].notna()].copy()
    work["tipo_pedido_operativo"] = work["tipo_pedido_operativo"].fillna("").astype(str).str.upper()
    structure_text = pd.Series("", index=work.index, dtype="object")
    for col in ["empaque", "sku_operativo", "sku_terminado"]:
        structure_text = structure_text.str.cat(work[col].fillna("").astype(str), sep=" ")
    mixed_marker = structure_text.str.lower().str.contains(r"\bcombo\b|\bbqt\b|\bbouquet\b", regex=True, na=False)
    # Defense for old cleaned files: a line with a mixed-structure marker is
    # never forecast as SOLIDO, even if its former label says SOLIDO.
    work = work[work["tipo_pedido_operativo"].eq("SOLIDO") & ~mixed_marker].copy()
    if work.empty:
        return work
    work["cod_cliente"] = work["cod_cliente"].astype(str).str.replace(r"\.0$", "", regex=True)
    work["cliente"] = work["cliente"].fillna("sin_info").astype(str)
    for col in ["pais", "producto", "color", "variedad", "grado", "tipo_caja", "capuchon", "comida", "empaque", "sku_operativo", "sku_terminado"]:
        work[col] = work[col].fillna("sin_info").astype(str)
    work["sku_operativo"] = work["sku_operativo"].where(~work["sku_operativo"].isin(["", "nan", "None"]), work["sku_terminado"])
    work["tallos_analisis"] = _safe_num(work["tallos_analisis"])
    work["tallos_confirmados"] = _safe_num(work["tallos_confirmados"])
    work["faltante_tallos"] = _safe_num(work["faltante_tallos"])
    work["tallos_x_ramo"] = _safe_num(work["tallos_x_ramo"]).round(2)
    work["mercado_cluster"] = work["pais"].map(classify_market)
    return work


def build_solid_weekly_demand(df: pd.DataFrame, perfil_cliente: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrega pedidos SOLIDO confirmados a cliente-producto-color-semana.

    La granularidad excluye caja y grado deliberadamente: el objetivo del
    modulo es anticipar tallos comerciales por color, no asignar presentaciones
    operativas intermitentes.
    """
    solids = _prepare_solids(df)
    if solids.empty:
        return pd.DataFrame()
    iso = solids["fecha"].dt.isocalendar()
    solids["anio"] = iso.year.astype(int)
    solids["semana_iso"] = iso.week.astype(int)
    solids["week_start"] = pd.to_datetime(
        solids["anio"].astype(str) + "-W" + solids["semana_iso"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u",
        errors="coerce",
    )
    weekly = solids.groupby(KEY_COLS + ["week_start", "anio", "semana_iso"], dropna=False, as_index=False).agg(
        tallos=("tallos_analisis", "sum"),
        tallos_confirmados=("tallos_confirmados", "sum"),
        faltante_tallos=("faltante_tallos", "sum"),
        lineas=("sku_operativo", "size"),
    )
    if perfil_cliente is not None and not perfil_cliente.empty:
        prof = perfil_cliente.copy()
        prof["cod_cliente"] = prof["cod_cliente"].astype(str).str.replace(r"\.0$", "", regex=True)
        keep = [col for col in ["cod_cliente", "cliente", "score_compra_terminada", "cumplimiento_tallos"] if col in prof.columns]
        weekly = weekly.merge(prof[keep].drop_duplicates("cod_cliente"), on="cod_cliente", how="left", suffixes=("", "_perfil"))
        if "cliente_perfil" in weekly.columns:
            weekly["cliente"] = weekly["cliente"].where(weekly["cliente"].ne("sin_info"), weekly["cliente_perfil"])
            weekly = weekly.drop(columns=["cliente_perfil"])
    for col in ["score_compra_terminada", "cumplimiento_tallos"]:
        if col not in weekly.columns:
            weekly[col] = 0
        weekly[col] = _safe_num(weekly[col])
    return weekly.sort_values(["week_start", "cod_cliente", "tallos"], ascending=[True, True, False]).reset_index(drop=True)


def _complete_week_panel(weekly: pd.DataFrame, config: SolidForecastConfig) -> pd.DataFrame:
    if weekly.empty:
        return weekly
    min_week = weekly["week_start"].min()
    max_week = weekly["week_start"].max()
    weeks = pd.DataFrame({"week_start": pd.date_range(min_week, max_week, freq="W-MON")})
    key_strength = weekly.groupby(KEY_COLS, dropna=False, as_index=False).agg(
        observaciones_key_panel=("week_start", "nunique"),
        tallos_key_panel=("tallos", "sum"),
    )
    recent_cutoff = max_week - pd.Timedelta(weeks=config.active_key_weeks - 1)
    recent_keys = weekly[weekly["week_start"] >= recent_cutoff][KEY_COLS].drop_duplicates()
    key_strength = key_strength[
        (key_strength["observaciones_key_panel"] >= config.min_nonzero_observations)
        | (key_strength["tallos_key_panel"] >= config.min_total_tallos_key)
    ].copy()
    key_strength = key_strength.merge(recent_keys, on=KEY_COLS, how="inner")
    keys = weekly[KEY_COLS + ["score_compra_terminada", "cumplimiento_tallos"]].drop_duplicates()
    keys = keys.merge(key_strength[KEY_COLS], on=KEY_COLS, how="inner")
    panel = keys.merge(weeks, how="cross")
    out = panel.merge(
        weekly[KEY_COLS + ["week_start", "tallos", "tallos_confirmados", "faltante_tallos", "lineas"]],
        on=KEY_COLS + ["week_start"],
        how="left",
    )
    for col in ["tallos", "tallos_confirmados", "faltante_tallos", "lineas"]:
        out[col] = _safe_num(out[col])
    iso = out["week_start"].dt.isocalendar()
    out["anio"] = iso.year.astype(int)
    out["semana_iso"] = iso.week.astype(int)
    out["mes_num"] = out["week_start"].dt.month.astype(int)
    return out


def _add_features(panel: pd.DataFrame, history_only: pd.DataFrame | None = None) -> pd.DataFrame:
    out = panel.sort_values(KEY_COLS + ["week_start"]).copy()
    group = out.groupby(KEY_COLS, dropna=False)["tallos"]
    out["activo"] = out["tallos"].gt(0).astype(int)
    active_group = out.groupby(KEY_COLS, dropna=False)["activo"]
    out["tallos_lag_1w"] = group.shift(1)
    out["tallos_lag_2w"] = group.shift(2)
    out["tallos_lag_4w"] = group.shift(4)
    prior_year = out[KEY_COLS + ["anio", "semana_iso", "tallos"]].copy()
    prior_year["anio"] = prior_year["anio"] + 1
    prior_year = prior_year.rename(columns={"tallos": "tallos_same_week_prev_year"})
    out = out.merge(prior_year, on=KEY_COLS + ["anio", "semana_iso"], how="left")
    out["rolling_mean_4w"] = group.transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
    out["rolling_median_8w"] = group.transform(lambda s: s.shift(1).rolling(8, min_periods=1).median())
    out["rolling_median_12w"] = group.transform(lambda s: s.shift(1).rolling(12, min_periods=1).median())
    out["activo_lag_1w"] = active_group.shift(1)
    out["activo_lag_2w"] = active_group.shift(2)
    out["actividad_rolling_8w"] = active_group.transform(lambda s: s.shift(1).rolling(8, min_periods=1).mean())
    out["actividad_rolling_26w"] = active_group.transform(lambda s: s.shift(1).rolling(26, min_periods=1).mean())

    history_panel = history_only.copy() if history_only is not None else out.copy()
    market_week_totals = history_panel.groupby(
        ["mercado_cluster", "producto", "color", "anio", "semana_iso"],
        dropna=False,
        as_index=False,
    ).agg(tallos_semana_mercado_producto_color=("tallos", "sum"))
    seasonal_level = market_week_totals.groupby(
        ["mercado_cluster", "producto", "color", "semana_iso"],
        dropna=False,
        as_index=False,
    ).agg(nivel_semana=("tallos_semana_mercado_producto_color", "median"))
    seasonal_base = market_week_totals.groupby(
        ["mercado_cluster", "producto", "color"],
        dropna=False,
        as_index=False,
    ).agg(nivel_base=("tallos_semana_mercado_producto_color", "median"))
    seasonal_level = seasonal_level.merge(
        seasonal_base, on=["mercado_cluster", "producto", "color"], how="left"
    )
    seasonal_level["indice_estacional_mercado_producto_color_semana"] = (
        seasonal_level["nivel_semana"] / seasonal_level["nivel_base"].replace(0, np.nan)
    ).clip(lower=0, upper=5).fillna(1.0)
    hist = history_panel.copy()
    hist = hist[hist["tallos"] > 0].copy()
    key_stats = hist.groupby(KEY_COLS, dropna=False, as_index=False).agg(
        mediana_key_total=("tallos", "median"),
        observaciones_key=("week_start", "nunique"),
    )
    recent_cutoff = hist["week_start"].max() - pd.Timedelta(weeks=12) if not hist.empty else out["week_start"].min()
    recent_stats = hist[hist["week_start"] >= recent_cutoff].groupby(KEY_COLS, dropna=False, as_index=False).agg(
        mediana_key_recent=("tallos", "median")
    )
    client_pc = hist.groupby(["cod_cliente", "producto", "color"], dropna=False, as_index=False).agg(
        mediana_cliente_producto_color=("tallos", "median")
    )
    market_pc_week = hist.groupby(["mercado_cluster", "producto", "color", "semana_iso"], dropna=False, as_index=False).agg(
        mediana_mercado_producto_color_semana=("tallos", "median")
    )
    client_weeks = hist.groupby("cod_cliente", as_index=False).agg(semanas_activas_cliente=("week_start", "nunique"))
    out = out.merge(key_stats, on=KEY_COLS, how="left")
    out = out.merge(recent_stats, on=KEY_COLS, how="left")
    out = out.merge(client_pc, on=["cod_cliente", "producto", "color"], how="left")
    out = out.merge(market_pc_week, on=["mercado_cluster", "producto", "color", "semana_iso"], how="left")
    out = out.merge(
        seasonal_level[
            ["mercado_cluster", "producto", "color", "semana_iso", "indice_estacional_mercado_producto_color_semana"]
        ],
        on=["mercado_cluster", "producto", "color", "semana_iso"],
        how="left",
    )
    out = out.merge(client_weeks, on="cod_cliente", how="left")
    out = out.merge(_market_year_growth(hist), on=["mercado_cluster", "anio"], how="left")
    out["factor_tendencia_mercado"] = out["factor_tendencia_mercado"].fillna(1.0)
    out["tallos_same_week_prev_year_ajustado_mercado"] = (
        _safe_num(out["tallos_same_week_prev_year"]) * out["factor_tendencia_mercado"]
    )
    out["semana_sin"] = np.sin(2 * np.pi * out["semana_iso"] / 52.0)
    out["semana_cos"] = np.cos(2 * np.pi * out["semana_iso"] / 52.0)
    out["mes_sin"] = np.sin(2 * np.pi * out["mes_num"] / 12.0)
    out["mes_cos"] = np.cos(2 * np.pi * out["mes_num"] / 12.0)
    out["fase_temporada_floral"] = _floral_phase(out["semana_iso"])
    out["es_semana_floral_pico"] = _peak_week_flag(out["semana_iso"])
    out["es_semana_post_fiesta"] = _post_floral_flag(out["semana_iso"])
    out["distancia_pico_floral"] = _distance_to_floral_peak(out["semana_iso"])
    for col in NUMERIC_FEATURES:
        if col not in out.columns:
            out[col] = 0
        out[col] = _safe_num(out[col])
    return out


def _freeze_recent_features(target: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Use only information available before the forecast/backtest horizon."""
    recent_features = []
    for _, frame in history.sort_values("week_start").groupby(KEY_COLS, dropna=False):
        values = frame["tallos"].to_numpy(dtype=float)
        active = (values > 0).astype(float)
        row = {col: frame.iloc[0][col] for col in KEY_COLS}
        row.update({
            "anchor_tallos_lag_1w": values[-1] if len(values) >= 1 else 0,
            "anchor_tallos_lag_2w": values[-2] if len(values) >= 2 else 0,
            "anchor_tallos_lag_4w": values[-4] if len(values) >= 4 else 0,
            "anchor_rolling_mean_4w": float(np.mean(values[-4:])) if len(values) else 0,
            "anchor_rolling_median_8w": float(np.median(values[-8:])) if len(values) else 0,
            "anchor_rolling_median_12w": float(np.median(values[-12:])) if len(values) else 0,
            "anchor_activo_lag_1w": active[-1] if len(active) >= 1 else 0,
            "anchor_activo_lag_2w": active[-2] if len(active) >= 2 else 0,
            "anchor_actividad_rolling_8w": float(np.mean(active[-8:])) if len(active) else 0,
            "anchor_actividad_rolling_26w": float(np.mean(active[-26:])) if len(active) else 0,
        })
        recent_features.append(row)
    anchor = pd.DataFrame(recent_features)
    out = target.merge(anchor, on=KEY_COLS, how="left")
    for col in [
        "tallos_lag_1w",
        "tallos_lag_2w",
        "tallos_lag_4w",
        "rolling_mean_4w",
        "rolling_median_8w",
        "rolling_median_12w",
        "activo_lag_1w",
        "activo_lag_2w",
        "actividad_rolling_8w",
        "actividad_rolling_26w",
    ]:
        out[col] = _safe_num(out[f"anchor_{col}"])
    return out.drop(columns=[col for col in out.columns if col.startswith("anchor_")])


def _encode_frame(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, int]]]:
    maps: dict[str, dict[str, int]] = {}
    train_out = train.copy()
    test_out = test.copy()
    for col in CATEGORICAL_FEATURES:
        values = train_out[col].fillna("sin_info").astype(str)
        top = values.value_counts().head(250).index.tolist()
        mapping = {"__otros__": 0, "sin_info": 1}
        for val in top:
            if val not in mapping:
                mapping[val] = len(mapping)
        maps[col] = mapping
        train_out[col] = values.map(mapping).fillna(0).astype("int16")
        test_out[col] = test_out[col].fillna("sin_info").astype(str).map(mapping).fillna(0).astype("int16")
    return train_out[CATEGORICAL_FEATURES + NUMERIC_FEATURES], test_out[CATEGORICAL_FEATURES + NUMERIC_FEATURES], maps


def _sample_training_frame(train: pd.DataFrame, config: SolidForecastConfig) -> pd.DataFrame:
    if len(train) <= config.max_rows:
        return train.copy()
    # Keep the observed purchase rate; artificial balancing inflates demand on inactive weeks.
    return train.sample(n=config.max_rows, random_state=config.random_state).copy()


def _metrics_frame(df: pd.DataFrame, model_name: str) -> dict[str, float | str]:
    actual = _safe_num(df["tallos"])
    pred = _safe_num(df["prediccion"])
    mae = mean_absolute_error(actual, pred)
    rmse = float(np.sqrt(mean_squared_error(actual, pred)))
    wape = (actual - pred).abs().sum() / actual.sum() if actual.sum() else np.nan
    bias = (pred.sum() - actual.sum()) / actual.sum() if actual.sum() else np.nan
    nonzero = df[actual > 0]
    mape_nonzero = ((nonzero["tallos"] - nonzero["prediccion"]).abs() / nonzero["tallos"]).mean() if not nonzero.empty else np.nan
    return {
        "modelo": model_name,
        "filas_test": len(df),
        "tallos_reales": float(actual.sum()),
        "tallos_predichos": float(pred.sum()),
        "MAE": float(mae),
        "RMSE": float(rmse),
        "WAPE": float(wape),
        "MAPE_no_cero": float(mape_nonzero) if pd.notna(mape_nonzero) else np.nan,
        "bias_pct": float(bias) if pd.notna(bias) else np.nan,
    }


def build_predictor_catalog() -> pd.DataFrame:
    rows = []
    for variable in CATEGORICAL_FEATURES + NUMERIC_FEATURES:
        block, description = FEATURE_METADATA.get(variable, ("Otros", variable))
        rows.append({
            "variable": variable,
            "tipo": "categorica" if variable in CATEGORICAL_FEATURES else "numerica",
            "bloque": block,
            "descripcion": description,
            "uso_modelo": "ocurrencia y volumen",
        })
    return pd.DataFrame(rows)


def _importance_table(
    model,
    x: pd.DataFrame,
    y: pd.Series,
    stage: str,
    scoring: str,
    config: SolidForecastConfig,
) -> pd.DataFrame:
    if x.empty:
        return pd.DataFrame()
    sample_size = min(len(x), 4_000)
    selected = x.sample(n=sample_size, random_state=config.random_state).index if len(x) > sample_size else x.index
    result = permutation_importance(
        model,
        x.loc[selected],
        y.loc[selected],
        scoring=scoring,
        n_repeats=2,
        random_state=config.random_state,
        n_jobs=1,
    )
    out = pd.DataFrame({
        "etapa_modelo": stage,
        "variable": x.columns,
        "importancia": result.importances_mean,
        "desviacion_importancia": result.importances_std,
        "filas_muestra": len(selected),
    })
    metadata = build_predictor_catalog()[["variable", "tipo", "bloque", "descripcion"]]
    out = out.merge(metadata, on="variable", how="left")
    out["importancia_positiva"] = out["importancia"].clip(lower=0)
    return out.sort_values("importancia", ascending=False).reset_index(drop=True)


def _market_importance_tables(
    occurrence,
    volume,
    x_test: pd.DataFrame,
    x_test_volume: pd.DataFrame,
    test_feat: pd.DataFrame,
    config: SolidForecastConfig,
) -> pd.DataFrame:
    """Calcula importancia del mismo boosting dentro de cada mercado de test.

    El modelo no se reentrena por mercado: la tabla explica que predictores
    sostienen mejor sus resultados cuando se observa cada mercado por separado.
    """
    rows: list[pd.DataFrame] = []
    for market, frame in test_feat.groupby("mercado_cluster", dropna=False):
        indexes = frame.index
        occurred = frame["tallos"].gt(0).astype(int)
        if len(frame) >= 20 and occurred.nunique() > 1:
            stage = _importance_table(
                occurrence,
                x_test.loc[indexes],
                occurred,
                "probabilidad_compra",
                "neg_log_loss",
                config,
            )
            stage["mercado_cluster"] = market
            rows.append(stage)
        positive_indexes = frame[frame["tallos"].gt(0)].index
        if len(positive_indexes) >= 20:
            stage = _importance_table(
                volume,
                x_test_volume.loc[positive_indexes],
                np.log1p(test_feat.loc[positive_indexes, "tallos"]),
                "volumen_si_compra",
                "neg_mean_absolute_error",
                config,
            )
            stage["mercado_cluster"] = market
            rows.append(stage)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def evaluate_solid_forecast_models(weekly: pd.DataFrame, config: SolidForecastConfig | None = None) -> dict[str, pd.DataFrame]:
    """Compara baseline, estacional anual y boosting sobre semanas de test.

    El boosting tiene dos etapas: probabilidad de compra y volumen condicionado
    a compra. El volumen se ajusta en escala logaritmica y recupera su nivel
    con un factor de retransformacion aprendido solo en entrenamiento, para no
    castigar artificialmente los picos al volver a tallos. Ademas exporta
    importancia por permutacion calculada en test.
    """
    config = config or SolidForecastConfig()
    if weekly.empty:
        return {"solid_forecast_model_evaluation": pd.DataFrame(), "solid_forecast_test_predictions": pd.DataFrame(), "solid_forecast_feature_importance": pd.DataFrame(), "solid_forecast_market_feature_importance": pd.DataFrame(), "solid_forecast_predictors": build_predictor_catalog()}
    panel = _complete_week_panel(weekly, config)
    max_week = panel["week_start"].max()
    test_start = max_week - pd.Timedelta(weeks=config.test_weeks - 1)
    train_panel = panel[panel["week_start"] < test_start].copy()
    test_panel = panel[panel["week_start"] >= test_start].copy()
    if train_panel["week_start"].nunique() < config.min_train_weeks or test_panel.empty:
        return {"solid_forecast_model_evaluation": pd.DataFrame(), "solid_forecast_test_predictions": pd.DataFrame(), "solid_forecast_feature_importance": pd.DataFrame(), "solid_forecast_market_feature_importance": pd.DataFrame(), "solid_forecast_predictors": build_predictor_catalog()}
    train_feat = _add_features(train_panel, train_panel)
    test_feat = _add_features(pd.concat([train_panel, test_panel], ignore_index=True), train_panel)
    test_feat = test_feat[test_feat["week_start"] >= test_start].copy()
    test_feat = _freeze_recent_features(test_feat, train_panel)

    predictions = []
    baseline = test_feat.copy()
    baseline["prediccion"] = baseline["rolling_median_8w"].where(baseline["rolling_median_8w"] > 0, baseline["mediana_key_recent"])
    baseline["prediccion"] = baseline["prediccion"].where(baseline["prediccion"] > 0, baseline["mediana_cliente_producto_color"]).fillna(0)
    baseline["modelo"] = "baseline_mediana_reciente_8w"
    predictions.append(baseline)

    seasonal = test_feat.copy()
    seasonal["prediccion"] = seasonal["tallos_same_week_prev_year"].fillna(0)
    seasonal["modelo"] = "estacional_anual_cliente_producto_color"
    predictions.append(seasonal)

    model_train = _sample_training_frame(train_feat, config)
    x_train, x_test, _ = _encode_frame(model_train, test_feat)
    categorical_mask = [col in CATEGORICAL_FEATURES for col in x_train.columns]
    occurrence = HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_iter=100,
        max_leaf_nodes=31,
        min_samples_leaf=30,
        l2_regularization=0.1,
        categorical_features=categorical_mask,
        random_state=config.random_state,
    )
    recency = (model_train["week_start"].max() - model_train["week_start"]).dt.days.clip(lower=0)
    weights = 1 + 2 * np.exp(-recency / 180) + _peak_week_flag(model_train["semana_iso"]) * 0.15
    occurred = model_train["tallos"].gt(0).astype(int)
    occurrence.fit(x_train, occurred, sample_weight=weights)

    positive_train = model_train[model_train["tallos"] > 0].copy()
    x_positive, x_test_volume, _ = _encode_frame(positive_train, test_feat)
    volume = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.06,
        max_iter=100,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=0.05,
        categorical_features=categorical_mask,
        random_state=config.random_state,
    )
    positive_recency = (positive_train["week_start"].max() - positive_train["week_start"]).dt.days.clip(lower=0)
    positive_weights = 1 + 3 * np.exp(-positive_recency / 180) + _peak_week_flag(positive_train["semana_iso"]) * 0.25
    positive_target = np.log1p(positive_train["tallos"])
    volume.fit(x_positive, positive_target, sample_weight=positive_weights)
    volume_smearing = float(
        np.average(
            np.exp(positive_target - volume.predict(x_positive)),
            weights=positive_weights,
        )
    )
    volume_smearing = float(np.clip(volume_smearing, 1.0, 1.35))
    boosting = test_feat.copy()
    boosting["probabilidad_compra"] = occurrence.predict_proba(x_test)[:, 1]
    boosting["volumen_si_compra"] = np.expm1(volume.predict(x_test_volume)).clip(0) * volume_smearing
    boosting["prediccion"] = boosting["probabilidad_compra"] * boosting["volumen_si_compra"]
    cap = _boosting_volume_cap(boosting)
    boosting["prediccion"] = np.where(cap > 0, np.minimum(boosting["prediccion"], cap), boosting["prediccion"])
    boosting["modelo"] = "boosting_ocurrencia_volumen_color"
    predictions.append(boosting)

    hybrid = boosting.copy()
    hybrid["prediccion"] = _seasonal_hybrid_prediction(hybrid, "prediccion")
    hybrid["modelo"] = "hibrido_boosting_estacional_mercado"
    predictions.append(hybrid)
    occurrence_importance = _importance_table(
        occurrence, x_test, test_feat["tallos"].gt(0).astype(int), "probabilidad_compra", "neg_log_loss", config
    )
    positive_test_mask = test_feat["tallos"].gt(0)
    volume_importance = _importance_table(
        volume,
        x_test_volume.loc[positive_test_mask],
        np.log1p(test_feat.loc[positive_test_mask, "tallos"]),
        "volumen_si_compra",
        "neg_mean_absolute_error",
        config,
    )
    importance = pd.concat([occurrence_importance, volume_importance], ignore_index=True)
    market_importance = _market_importance_tables(
        occurrence, volume, x_test, x_test_volume, test_feat, config
    )

    pred = pd.concat(predictions, ignore_index=True)
    pred["prediccion"] = pred["prediccion"].fillna(0).round(0).astype(int)
    pred["error"] = pred["prediccion"] - pred["tallos"]
    pred["error_abs"] = pred["error"].abs()
    evaluation = pd.DataFrame([_metrics_frame(frame, model_name) for model_name, frame in pred.groupby("modelo", sort=False)])
    best_model = evaluation.sort_values(["WAPE", "RMSE"], ascending=[True, True]).iloc[0]["modelo"] if not evaluation.empty else ""
    evaluation["modelo_seleccionado"] = evaluation["modelo"].eq(best_model)
    return {
        "solid_forecast_model_evaluation": evaluation.sort_values("WAPE").reset_index(drop=True),
        "solid_forecast_test_predictions": pred.reset_index(drop=True),
        "solid_forecast_feature_importance": importance,
        "solid_forecast_market_feature_importance": market_importance,
        "solid_forecast_predictors": build_predictor_catalog(),
    }


def build_future_solid_forecast(weekly: pd.DataFrame, selected_model: str, config: SolidForecastConfig | None = None) -> pd.DataFrame:
    """Proyecta tallos futuros usando el modelo elegido por validacion."""
    config = config or SolidForecastConfig()
    if weekly.empty:
        return pd.DataFrame()
    panel = _complete_week_panel(weekly, config)
    max_week = panel["week_start"].max()
    future_weeks = pd.DataFrame({"week_start": pd.date_range(max_week + pd.Timedelta(weeks=1), periods=config.horizon_weeks, freq="W-MON")})
    keys = weekly[KEY_COLS + ["score_compra_terminada", "cumplimiento_tallos"]].drop_duplicates()
    future = keys.merge(future_weeks, how="cross")
    future["tallos"] = 0.0
    future["tallos_confirmados"] = 0.0
    future["faltante_tallos"] = 0.0
    future["lineas"] = 0.0
    iso = future["week_start"].dt.isocalendar()
    future["anio"] = iso.year.astype(int)
    future["semana_iso"] = iso.week.astype(int)
    future["mes_num"] = future["week_start"].dt.month.astype(int)
    full = pd.concat([panel, future], ignore_index=True)
    feat = _add_features(full, panel)
    future_feat = feat[feat["week_start"] > max_week].copy()
    future_feat = _freeze_recent_features(future_feat, panel)

    if selected_model == "estacional_anual_cliente_producto_color":
        future_feat["tallos_estimados"] = future_feat["tallos_same_week_prev_year"].fillna(0)
    elif selected_model in {"boosting_ocurrencia_volumen_color", "hibrido_boosting_estacional_mercado"}:
        train_feat = _add_features(panel, panel)
        model_train = _sample_training_frame(train_feat, config)
        x_train, x_future, _ = _encode_frame(model_train, future_feat)
        categorical_mask = [col in CATEGORICAL_FEATURES for col in x_train.columns]
        occurrence = HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=100,
            max_leaf_nodes=31,
            min_samples_leaf=30,
            l2_regularization=0.1,
            categorical_features=categorical_mask,
            random_state=config.random_state,
        )
        recency = (model_train["week_start"].max() - model_train["week_start"]).dt.days.clip(lower=0)
        weights = 1 + 2 * np.exp(-recency / 180) + _peak_week_flag(model_train["semana_iso"]) * 0.15
        occurred = model_train["tallos"].gt(0).astype(int)
        occurrence.fit(x_train, occurred, sample_weight=weights)
        positive_train = model_train[model_train["tallos"] > 0].copy()
        x_positive, x_future_volume, _ = _encode_frame(positive_train, future_feat)
        volume = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.06,
            max_iter=100,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=0.05,
            categorical_features=categorical_mask,
            random_state=config.random_state,
        )
        positive_recency = (positive_train["week_start"].max() - positive_train["week_start"]).dt.days.clip(lower=0)
        positive_weights = 1 + 3 * np.exp(-positive_recency / 180) + _peak_week_flag(positive_train["semana_iso"]) * 0.25
        positive_target = np.log1p(positive_train["tallos"])
        volume.fit(x_positive, positive_target, sample_weight=positive_weights)
        volume_smearing = float(
            np.average(
                np.exp(positive_target - volume.predict(x_positive)),
                weights=positive_weights,
            )
        )
        volume_smearing = float(np.clip(volume_smearing, 1.0, 1.35))
        future_feat["probabilidad_compra"] = occurrence.predict_proba(x_future)[:, 1]
        future_feat["volumen_si_compra"] = np.expm1(volume.predict(x_future_volume)).clip(0) * volume_smearing
        future_feat["tallos_estimados"] = future_feat["probabilidad_compra"] * future_feat["volumen_si_compra"]
        cap = _boosting_volume_cap(future_feat)
        future_feat["tallos_estimados"] = np.where(cap > 0, np.minimum(future_feat["tallos_estimados"], cap), future_feat["tallos_estimados"])
        if selected_model == "hibrido_boosting_estacional_mercado":
            future_feat["tallos_estimados"] = _seasonal_hybrid_prediction(future_feat, "tallos_estimados")
    else:
        future_feat["tallos_estimados"] = future_feat["rolling_median_8w"].where(future_feat["rolling_median_8w"] > 0, future_feat["mediana_key_recent"])
        future_feat["tallos_estimados"] = future_feat["tallos_estimados"].where(future_feat["tallos_estimados"] > 0, future_feat["mediana_cliente_producto_color"]).fillna(0)

    keep = KEY_COLS + [
        "week_start", "anio", "semana_iso", "tallos_estimados", "observaciones_key",
        "score_compra_terminada", "cumplimiento_tallos", "fase_temporada_floral",
        "es_semana_floral_pico", "es_semana_post_fiesta", "distancia_pico_floral",
        "factor_tendencia_mercado", "tallos_same_week_prev_year",
        "tallos_same_week_prev_year_ajustado_mercado",
        "indice_estacional_mercado_producto_color_semana",
    ]
    for col in ["probabilidad_compra", "volumen_si_compra"]:
        if col in future_feat.columns:
            keep.append(col)
    out = future_feat[keep].copy()
    out["tallos_estimados"] = out["tallos_estimados"].fillna(0).round(0).astype(int)
    out = out[out["tallos_estimados"] > 0].copy()
    out["modelo"] = selected_model
    out["fuente_demanda"] = "FORECAST_SOLIDOS_SEMANAL"
    return out.sort_values(["week_start", "tallos_estimados"], ascending=[True, False]).reset_index(drop=True)


def build_market_volume_calibration(
    test_predictions: pd.DataFrame,
    selected_model: str,
) -> pd.DataFrame:
    """Detecta subpronostico sostenido por mercado para ajustar volumen futuro.

    La correccion se activa solo si el modelo queda por debajo del real en
    ambas mitades temporales del backtest. El factor usa las ocho semanas
    completas y se limita para no convertir ruido puntual en una proyeccion.
    """
    pred = test_predictions[test_predictions["modelo"].astype(str).eq(str(selected_model))].copy()
    if pred.empty or selected_model not in {"boosting_ocurrencia_volumen_color", "hibrido_boosting_estacional_mercado"}:
        return pd.DataFrame()
    weeks = sorted(pred["week_start"].dropna().unique())
    if len(weeks) < 4:
        return pd.DataFrame()
    cut = max(1, len(weeks) // 2)
    first_weeks, second_weeks = set(weeks[:cut]), set(weeks[cut:])

    def aggregate(scope: pd.DataFrame, suffix: str) -> pd.DataFrame:
        result = scope.groupby("mercado_cluster", as_index=False).agg(
            **{
                f"tallos_reales_{suffix}": ("tallos", "sum"),
                f"tallos_predichos_{suffix}": ("prediccion", "sum"),
            }
        )
        result[f"ratio_real_predicho_{suffix}"] = np.where(
            result[f"tallos_predichos_{suffix}"] > 0,
            result[f"tallos_reales_{suffix}"] / result[f"tallos_predichos_{suffix}"],
            np.nan,
        )
        return result

    total = aggregate(pred, "total")
    first = aggregate(pred[pred["week_start"].isin(first_weeks)], "primera_mitad")
    second = aggregate(pred[pred["week_start"].isin(second_weeks)], "segunda_mitad")
    calibration = total.merge(first, on="mercado_cluster", how="left").merge(second, on="mercado_cluster", how="left")
    calibration["subpronostico_sostenido"] = (
        calibration["ratio_real_predicho_primera_mitad"].ge(1.05)
        & calibration["ratio_real_predicho_segunda_mitad"].ge(1.05)
        & calibration["tallos_reales_total"].ge(100_000)
    )
    calibration["factor_calibracion_mercado"] = np.where(
        calibration["subpronostico_sostenido"],
        calibration["ratio_real_predicho_total"].clip(lower=1.0, upper=2.0),
        1.0,
    )
    calibration["sesgo_base_pct"] = np.where(
        calibration["tallos_reales_total"] > 0,
        (calibration["tallos_predichos_total"] - calibration["tallos_reales_total"])
        / calibration["tallos_reales_total"],
        np.nan,
    )
    calibration["lectura_negocio"] = np.where(
        calibration["subpronostico_sostenido"],
        "El modelo subestimo volumen de forma consistente; se corrige el nivel futuro sin cambiar su composicion.",
        "Sin correccion: no hay evidencia estable de subpronostico en ambas mitades del test.",
    )
    return calibration.sort_values("factor_calibracion_mercado", ascending=False).reset_index(drop=True)


def apply_market_volume_calibration(future: pd.DataFrame, calibration: pd.DataFrame) -> pd.DataFrame:
    """Aplica al forecast futuro el ajuste de nivel aprobado por mercado."""
    if future.empty or calibration.empty:
        return future
    out = future.merge(
        calibration[["mercado_cluster", "factor_calibracion_mercado", "subpronostico_sostenido"]],
        on="mercado_cluster",
        how="left",
    )
    out["factor_calibracion_mercado"] = out["factor_calibracion_mercado"].fillna(1.0)
    out["subpronostico_sostenido"] = out["subpronostico_sostenido"].fillna(False)
    out["tallos_estimados_base"] = out["tallos_estimados"]
    out["tallos_estimados"] = (
        out["tallos_estimados_base"] * out["factor_calibracion_mercado"]
    ).round(0).astype(int)
    out["fuente_demanda"] = np.where(
        out["factor_calibracion_mercado"].gt(1.0),
        "FORECAST_SOLIDOS_SEMANAL_CALIBRADO_MERCADO",
        out["fuente_demanda"],
    )
    return out


def apply_floral_seasonal_overlay(future: pd.DataFrame) -> pd.DataFrame:
    """Reinforce preparation/peak weeks using observed annual seasonality.

    The selected model continues to provide the base trajectory. Only weeks
    commercially marked as preparation or peak, with prior-year evidence, are
    blended toward the prior equivalent week, already adjusted with market
    growth known before the forecast year. Post-event weeks remain controlled
    by the trained model so it can represent the historical demand drop.
    """
    if future.empty or "tallos_same_week_prev_year_ajustado_mercado" not in future.columns:
        return future
    out = future.copy()
    seasonal = _safe_num(out["tallos_same_week_prev_year_ajustado_mercado"])
    floral = out["es_semana_floral_pico"].fillna(0).astype(int).eq(1) & seasonal.gt(0)
    out["tallos_estimados_pre_ajuste_floral"] = out["tallos_estimados"]
    out["ajuste_estacional_floral_aplicado"] = floral
    out.loc[floral, "tallos_estimados"] = (
        0.75 * seasonal.loc[floral] + 0.25 * _safe_num(out.loc[floral, "tallos_estimados"])
    ).round(0).astype(int)
    out["fuente_demanda"] = np.where(
        floral,
        "FORECAST_SOLIDOS_AJUSTE_ESTACIONAL_FLORAL",
        out["fuente_demanda"],
    )
    return out


def build_historical_seasonal_validation(weekly: pd.DataFrame) -> pd.DataFrame:
    """Backtest every comparable historical season using only prior-year signals.

    For each observed target year, the prediction is the same customer-product-
    color week in the previous year, adjusted by market growth known before the
    target year. This makes holidays inspectable in the dashboard even when the
    final forecast horizon changes as new annual data is appended.
    """
    if weekly.empty:
        return pd.DataFrame()
    base = weekly.copy()
    growth = _market_year_growth(base)
    prior = base[KEY_COLS + ["anio", "semana_iso", "tallos"]].copy()
    prior["anio"] = prior["anio"] + 1
    prior["week_start"] = pd.to_datetime(
        prior["anio"].astype(str) + "-W" + prior["semana_iso"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u",
        errors="coerce",
    )
    prior = prior.rename(columns={"tallos": "prediccion_base_anio_anterior"})
    prior = prior.merge(growth, on=["mercado_cluster", "anio"], how="left")
    prior["factor_tendencia_mercado"] = prior["factor_tendencia_mercado"].fillna(1.0)
    prior["prediccion"] = (
        prior["prediccion_base_anio_anterior"] * prior["factor_tendencia_mercado"]
    )
    actual = base[KEY_COLS + ["week_start", "anio", "semana_iso", "tallos"]].copy()
    validation = prior.merge(
        actual,
        on=KEY_COLS + ["week_start", "anio", "semana_iso"],
        how="outer",
    )
    min_year = int(base["anio"].min()) + 1
    max_year = int(base["anio"].max())
    validation = validation[validation["anio"].between(min_year, max_year)].copy()
    validation["tallos"] = _safe_num(validation["tallos"])
    validation["prediccion"] = _safe_num(validation["prediccion"])
    validation["prediccion_base_anio_anterior"] = _safe_num(validation["prediccion_base_anio_anterior"])
    validation["factor_tendencia_mercado"] = validation["factor_tendencia_mercado"].fillna(1.0)
    validation["fase_temporada_floral"] = _floral_phase(validation["semana_iso"])
    validation["es_semana_floral_pico"] = _peak_week_flag(validation["semana_iso"])
    validation["es_semana_post_fiesta"] = _post_floral_flag(validation["semana_iso"])
    validation["distancia_pico_floral"] = _distance_to_floral_peak(validation["semana_iso"])
    validation["modelo"] = "retrospectivo_estacional_ajustado_mercado"
    validation["error"] = validation["prediccion"] - validation["tallos"]
    validation["error_abs"] = validation["error"].abs()
    validation["prediccion"] = validation["prediccion"].round(0).astype(int)
    return validation.sort_values(["week_start", "mercado_cluster", "prediccion"], ascending=[True, True, False]).reset_index(drop=True)


def summarize_solid_forecast(future: pd.DataFrame, evaluation: pd.DataFrame, test_predictions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Construye resumenes semanales, comerciales y de error para el Dash."""
    by_week = future.groupby(["week_start", "anio", "semana_iso", "modelo"], as_index=False).agg(
        tallos_estimados=("tallos_estimados", "sum"),
        clientes=("cod_cliente", "nunique"),
        combinaciones=("producto", "size"),
    ) if not future.empty else pd.DataFrame()
    by_market = future.groupby(["mercado_cluster", "producto", "color"], as_index=False).agg(
        tallos_estimados=("tallos_estimados", "sum"),
        clientes=("cod_cliente", "nunique"),
        combinaciones=("producto", "size"),
    ).sort_values("tallos_estimados", ascending=False) if not future.empty else pd.DataFrame()
    error_by_market = test_predictions.groupby(["modelo", "mercado_cluster"], as_index=False).agg(
        tallos_reales=("tallos", "sum"),
        tallos_predichos=("prediccion", "sum"),
        error_abs=("error_abs", "sum"),
    ) if not test_predictions.empty else pd.DataFrame()
    if not error_by_market.empty:
        error_by_market["WAPE"] = np.where(error_by_market["tallos_reales"] > 0, error_by_market["error_abs"] / error_by_market["tallos_reales"], np.nan)
    return {
        "solid_forecast_future_week": by_week,
        "solid_forecast_future_market_color": by_market,
        "solid_forecast_error_by_market": error_by_market,
    }


def run_solid_forecast_pipeline(
    historico_confirmado: pd.DataFrame,
    perfil_cliente: pd.DataFrame | None = None,
    output_dir: str | Path | None = None,
    config: SolidForecastConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Ejecuta el forecast SOLIDO completo y opcionalmente escribe sus salidas.

    Parameters
    ----------
    historico_confirmado:
        Pedidos limpios confirmados; el ejecutor filtra y prepara solo SOLIDO.
    perfil_cliente:
        Tabla descriptiva opcional para enriquecer señales del cliente.
    output_dir:
        Ruta donde se escriben CSV/XLSX si se solicita.
    config:
        Ventanas de validacion, horizonte y controles de modelado.
    """
    config = config or SolidForecastConfig()
    weekly = build_solid_weekly_demand(historico_confirmado, perfil_cliente)
    eval_outputs = evaluate_solid_forecast_models(weekly, config)
    evaluation = eval_outputs["solid_forecast_model_evaluation"]
    selected = "baseline_mediana_reciente_8w"
    if not evaluation.empty and "modelo_seleccionado" in evaluation.columns:
        selected_rows = evaluation[evaluation["modelo_seleccionado"]]
        if not selected_rows.empty:
            selected = str(selected_rows.iloc[0]["modelo"])
    future = build_future_solid_forecast(weekly, selected, config)
    calibration = build_market_volume_calibration(eval_outputs["solid_forecast_test_predictions"], selected)
    future = apply_market_volume_calibration(future, calibration)
    future = apply_floral_seasonal_overlay(future)
    historical_validation = build_historical_seasonal_validation(weekly)
    summaries = summarize_solid_forecast(future, evaluation, eval_outputs["solid_forecast_test_predictions"])
    outputs = {
        "solid_forecast_weekly_demand": weekly,
        **eval_outputs,
        "solid_forecast_market_calibration": calibration,
        "solid_forecast_historical_validation": historical_validation,
        "solid_forecast_future": future,
        **summaries,
    }
    if output_dir is not None:
        write_outputs(outputs, output_dir, excel_name="LGF_Forecast_Solidos.xlsx")
    return outputs
