from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .io_utils import write_outputs


CLIENT_KEYS = ["cod_cliente", "cliente"]

MARKET_US_CANADA = "01_ESTADOS_UNIDOS_CANADA"
MARKET_NETHERLANDS = "02_THE_NETHERLANDS"
MARKET_POLAND = "03_POLONIA"
MARKET_ASIA = "04_ASIA"
MARKET_OTHER = "05_OTROS"

ASIA_COUNTRIES = {
    "china",
    "hong kong",
    "japan",
    "singapore",
    "south korea",
    "korea",
    "taiwan",
    "thailand",
    "vietnam",
    "malaysia",
    "indonesia",
    "philippines",
    "india",
    "united arab emirates",
    "uae",
    "qatar",
    "saudi arabia",
}


@dataclass(frozen=True)
class ClusterConfig:
    min_clients_market: int = 4
    max_k: int = 6
    random_state: int = 42
    top_colors: int = 20
    top_products: int = 15
    top_types: int = 8
    top_packaging: int = 10
    top_skus: int = 20
    weight_constancy: float = 1.6
    weight_color_mix: float = 2.4
    weight_product_mix: float = 2.0
    weight_type_mix: float = 1.7
    weight_operational: float = 1.0
    weight_sku_mix: float = 0.8
    weight_volume: float = 0.8
    weight_fulfillment: float = 0.5
    singleton_penalty: float = 0.18
    dominance_penalty: float = 0.12


def classify_market(pais: object) -> str:
    """Asigna cada pais a uno de los cinco mercados definidos por negocio."""
    text = str(pais or "").strip().lower()
    if text in {"united states", "usa", "u.s.a.", "us", "canada"}:
        return MARKET_US_CANADA
    if text in {"the netherlands", "netherlands", "holland", "holanda"}:
        return MARKET_NETHERLANDS
    if text in {"poland", "polonia"}:
        return MARKET_POLAND
    if text in ASIA_COUNTRIES:
        return MARKET_ASIA
    return MARKET_OTHER


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    values = _safe_numeric(values)
    weights = _safe_numeric(weights)
    total = weights.sum()
    if total <= 0:
        positive = values[values > 0]
        return float(positive.mean()) if not positive.empty else 0.0
    return float((values * weights).sum() / total)


def _entropy(shares: pd.Series) -> float:
    values = shares[shares > 0].astype(float).to_numpy()
    if values.size == 0:
        return 0.0
    return float(-(values * np.log(values)).sum())


def _normalized_entropy(shares: pd.Series) -> float:
    values = shares[shares > 0].astype(float)
    if values.empty or len(values) <= 1:
        return 0.0
    return float(_entropy(values) / np.log(len(values)))


def _top_value(frame: pd.DataFrame, col: str, weight_col: str = "tallos_analisis") -> str:
    if frame.empty or col not in frame.columns:
        return "sin_info"
    top = frame.groupby(col, dropna=False)[weight_col].sum().sort_values(ascending=False)
    return str(top.index[0]) if not top.empty else "sin_info"


def _mode_value(series: pd.Series) -> str:
    values = series.dropna().astype(str)
    if values.empty:
        return "sin_info"
    mode = values.mode()
    return str(mode.iloc[0]) if not mode.empty else "sin_info"


def _share_matrix(
    df: pd.DataFrame,
    feature_col: str,
    prefix: str,
    max_features: int,
    value_col: str = "tallos_analisis",
) -> pd.DataFrame:
    if df.empty or feature_col not in df.columns:
        return pd.DataFrame()
    tmp = df.groupby(CLIENT_KEYS + [feature_col], dropna=False, as_index=False)[value_col].sum()
    top_features = (
        tmp.groupby(feature_col, dropna=False)[value_col]
        .sum()
        .sort_values(ascending=False)
        .head(max_features)
        .index
    )
    tmp = tmp[tmp[feature_col].isin(top_features)].copy()
    tmp["cliente_key"] = tmp["cod_cliente"].astype(str) + " | " + tmp["cliente"].astype(str)
    pivot = tmp.pivot_table(index="cliente_key", columns=feature_col, values=value_col, aggfunc="sum", fill_value=0)
    raw_cols = [f"{prefix}__{str(col)[:80]}" for col in pivot.columns]
    used: dict[str, int] = {}
    unique_cols = []
    for col in raw_cols:
        count = used.get(col, 0)
        used[col] = count + 1
        unique_cols.append(col if count == 0 else f"{col}__{count + 1}")
    pivot.columns = unique_cols
    row_sums = pivot.sum(axis=1).replace(0, np.nan)
    return pivot.div(row_sums, axis=0).fillna(0)


def _make_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    used: dict[str, int] = {}
    cols = []
    for col in df.columns:
        count = used.get(str(col), 0)
        used[str(col)] = count + 1
        cols.append(str(col) if count == 0 else f"{col}__{count + 1}")
    out = df.copy()
    out.columns = cols
    return out


def _client_key(df: pd.DataFrame) -> pd.Series:
    return df["cod_cliente"].astype(str) + " | " + df["cliente"].astype(str)


def _split_client_key(cliente_key: str) -> tuple[str, str]:
    if " | " in str(cliente_key):
        cod, cliente = str(cliente_key).split(" | ", 1)
        return cod, cliente
    return str(cliente_key), str(cliente_key)


def build_client_clustering_dataset(
    historico: pd.DataFrame,
    perfil_cliente: pd.DataFrame | None = None,
    config: ClusterConfig | None = None,
) -> pd.DataFrame:
    """Construye una fila de atributos comerciales y operativos por cliente.

    La ventana temporal se hereda del historico confirmado recibido. Por ello
    los clusters pueden representar un ano particular o un periodo consolidado
    sin cambiar el algoritmo.
    """
    """Create one analytical row per client for market-level clustering."""
    config = config or ClusterConfig()
    if historico.empty:
        return pd.DataFrame()

    df = historico.copy()
    for col in CLIENT_KEYS:
        if col not in df.columns:
            raise ValueError(f"Falta columna obligatoria para clustering: {col}")
    for col in [
        "pais",
        "fecha",
        "tallos_analisis",
        "tallos_confirmados",
        "faltante_tallos",
        "ventas_usd",
        "color",
        "producto",
        "tipo_pedido_operativo",
        "empaque_operativo",
        "sku_operativo",
        "sku_terminado",
        "tallos_x_ramo",
        "ramos_x_caja",
        "pedido",
        "caja_id",
        "tipo_caja",
    ]:
        if col not in df.columns:
            df[col] = np.nan

    df["cod_cliente"] = df["cod_cliente"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["cliente"] = df["cliente"].astype(str)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["tallos_analisis"] = _safe_numeric(df["tallos_analisis"])
    df["tallos_confirmados"] = _safe_numeric(df["tallos_confirmados"])
    df["faltante_tallos"] = _safe_numeric(df["faltante_tallos"])
    df["ventas_usd"] = _safe_numeric(df["ventas_usd"])
    df["tallos_x_ramo"] = _safe_numeric(df["tallos_x_ramo"])
    df["ramos_x_caja"] = _safe_numeric(df["ramos_x_caja"])
    iso = df["fecha"].dt.isocalendar()
    df["anio_semana"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    df["cliente_key"] = _client_key(df)
    max_date = df["fecha"].max()
    recent_start = max_date - pd.Timedelta(days=55) if pd.notna(max_date) else pd.NaT
    previous_start = max_date - pd.Timedelta(days=111) if pd.notna(max_date) else pd.NaT

    rows = []
    for cliente_key, frame in df.groupby("cliente_key", sort=False):
        cod, cliente = _split_client_key(cliente_key)
        weekly = frame.groupby("anio_semana", dropna=False)["tallos_analisis"].sum()
        tallos = frame["tallos_analisis"].sum()
        confirmed = frame["tallos_confirmados"].sum()
        missing = frame["faltante_tallos"].sum()
        sales_usd = frame["ventas_usd"].sum()
        recent_stems = frame.loc[frame["fecha"].between(recent_start, max_date), "tallos_analisis"].sum() if pd.notna(max_date) else 0
        previous_stems = frame.loc[
            frame["fecha"].between(previous_start, recent_start - pd.Timedelta(days=1)),
            "tallos_analisis",
        ].sum() if pd.notna(max_date) else 0
        recent_change = (recent_stems / previous_stems - 1) if previous_stems > 0 else np.nan
        country = _mode_value(frame["pais"])
        color_shares = frame.groupby("color", dropna=False)["tallos_analisis"].sum() / tallos if tallos else pd.Series(dtype=float)
        product_shares = frame.groupby("producto", dropna=False)["tallos_analisis"].sum() / tallos if tallos else pd.Series(dtype=float)
        type_shares = frame.groupby("tipo_pedido_operativo", dropna=False)["tallos_analisis"].sum() / tallos if tallos else pd.Series(dtype=float)
        sku_col = "sku_operativo" if frame["sku_operativo"].notna().any() else "sku_terminado"
        sku_shares = frame.groupby(sku_col, dropna=False)["tallos_analisis"].sum() / tallos if tallos else pd.Series(dtype=float)
        weekly_mean = weekly.mean() if not weekly.empty else 0
        cv_volumen = weekly.std(ddof=0) / weekly_mean if weekly_mean else 0
        rows.append(
            {
                "cod_cliente": cod,
                "cliente": cliente,
                "pais_principal": country,
                "mercado_cluster": classify_market(country),
                "tallos_total": tallos,
                "tallos_confirmados": confirmed,
                "faltante_tallos": missing,
                "cumplimiento_tallos": confirmed / tallos if tallos else 0,
                "ventas_usd_total": sales_usd,
                "ventas_usd_por_tallo": sales_usd / tallos if tallos else 0,
                "tallos_ultimas_8_semanas": recent_stems,
                "tallos_8_semanas_previas": previous_stems,
                "variacion_reciente_vs_previa": recent_change,
                "pedidos": frame["pedido"].nunique(),
                "cajas": frame["caja_id"].nunique(),
                "semanas_activas": weekly.size,
                "tallos_promedio_semana": weekly_mean,
                "tallos_mediana_semana": weekly.median() if not weekly.empty else 0,
                "cv_volumen": cv_volumen,
                "estabilidad_volumen": 1 / (1 + cv_volumen),
                "volumen_log": np.log1p(tallos),
                "colores_distintos": color_shares.shape[0],
                "productos_distintos": product_shares.shape[0],
                "tipos_pedido_distintos": type_shares.shape[0],
                "skus_distintos": sku_shares.shape[0],
                "share_top1_color": color_shares.sort_values(ascending=False).head(1).sum() if not color_shares.empty else 0,
                "share_top3_color": color_shares.sort_values(ascending=False).head(3).sum() if not color_shares.empty else 0,
                "share_top1_producto": product_shares.sort_values(ascending=False).head(1).sum() if not product_shares.empty else 0,
                "share_top3_producto": product_shares.sort_values(ascending=False).head(3).sum() if not product_shares.empty else 0,
                "share_top1_tipo_pedido": type_shares.sort_values(ascending=False).head(1).sum() if not type_shares.empty else 0,
                "share_top1_sku": sku_shares.sort_values(ascending=False).head(1).sum() if not sku_shares.empty else 0,
                "share_top5_sku": sku_shares.sort_values(ascending=False).head(5).sum() if not sku_shares.empty else 0,
                "entropia_color": _entropy(color_shares),
                "entropia_color_norm": _normalized_entropy(color_shares),
                "entropia_producto": _entropy(product_shares),
                "entropia_producto_norm": _normalized_entropy(product_shares),
                "entropia_tipo_pedido": _entropy(type_shares),
                "entropia_tipo_pedido_norm": _normalized_entropy(type_shares),
                "entropia_sku": _entropy(sku_shares),
                "entropia_sku_norm": _normalized_entropy(sku_shares),
                "tallos_x_ramo_promedio": _weighted_average(frame["tallos_x_ramo"], frame["tallos_analisis"]),
                "ramos_x_caja_promedio": _weighted_average(frame["ramos_x_caja"], frame["tallos_analisis"]),
                "producto_dominante": _top_value(frame, "producto"),
                "color_dominante": _top_value(frame, "color"),
                "tipo_pedido_dominante": _top_value(frame, "tipo_pedido_operativo"),
                "tipo_caja_dominante": _top_value(frame, "tipo_caja"),
            }
        )
    base = pd.DataFrame(rows)
    if base.empty:
        return base
    base["cliente_key"] = _client_key(base)
    market_total = base.groupby("mercado_cluster")["tallos_total"].transform("sum").replace(0, np.nan)
    base["participacion_tallos_mercado"] = (base["tallos_total"] / market_total).fillna(0)
    base["complejidad_operativa_score"] = 100 * (
        0.35 * base["entropia_tipo_pedido_norm"]
        + 0.25 * base["entropia_producto_norm"]
        + 0.25 * base["entropia_sku_norm"]
        + 0.15 * (1 - base["share_top1_tipo_pedido"])
    )
    base["complejidad_operativa"] = pd.cut(
        base["complejidad_operativa_score"],
        bins=[-np.inf, 30, 60, np.inf],
        labels=["BAJA", "MEDIA", "ALTA"],
    ).astype(str)
    base = base.set_index("cliente_key")

    matrices = [
        _share_matrix(df, "color", "share_color", config.top_colors),
        _share_matrix(df, "producto", "share_producto", config.top_products),
        _share_matrix(df, "tipo_pedido_operativo", "share_tipo", config.top_types),
        _share_matrix(df, "empaque_operativo", "share_empaque", config.top_packaging),
        _share_matrix(df, "sku_operativo", "share_sku", config.top_skus),
    ]
    for matrix in matrices:
        if not matrix.empty:
            base = base.join(matrix, how="left")

    if perfil_cliente is not None and not perfil_cliente.empty:
        prof = perfil_cliente.copy()
        prof["cod_cliente"] = prof["cod_cliente"].astype(str).str.replace(r"\.0$", "", regex=True)
        prof["cliente_key"] = _client_key(prof)
        keep_cols = [
            "pct_semanas_activas",
            "score_compra_terminada",
            "score_compra_terminada_operativo",
            "score_frecuencia",
            "score_volumen",
            "score_color",
            "score_sku_terminado",
            "score_empaque",
            "score_tipo_pedido",
            "recomendacion_compra",
            "segmento_cliente",
        ]
        prof_cols = [col for col in keep_cols if col in prof.columns]
        base = base.join(prof.set_index("cliente_key")[prof_cols], how="left", rsuffix="_perfil")

    base = _make_unique_columns(base)
    numeric_cols = base.select_dtypes(include=[np.number]).columns
    base[numeric_cols] = base[numeric_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    for col in ["recomendacion_compra", "segmento_cliente"]:
        if col not in base.columns:
            base[col] = "sin_info"
        base[col] = base[col].fillna("sin_info").astype(str)
    return base.reset_index(drop=True)


def _feature_columns(features: pd.DataFrame) -> list[str]:
    preferred = [
        "pct_semanas_activas",
        "semanas_activas",
        "estabilidad_volumen",
        "cv_volumen",
        "volumen_log",
        "tallos_promedio_semana",
        "cumplimiento_tallos",
        "share_top1_color",
        "share_top3_color",
        "entropia_color_norm",
        "colores_distintos",
        "share_top1_producto",
        "share_top3_producto",
        "entropia_producto_norm",
        "productos_distintos",
        "share_top1_tipo_pedido",
        "entropia_tipo_pedido_norm",
        "tipos_pedido_distintos",
        "share_top1_sku",
        "share_top5_sku",
        "entropia_sku_norm",
        "tallos_x_ramo_promedio",
        "ramos_x_caja_promedio",
    ]
    # Detailed SKU/empaque keys are too granular for strategic segmentation.
    # They remain as summarized variables, but the cluster geometry is driven by
    # color, product, order type and constancy.
    prefixes = ("share_color__", "share_producto__", "share_tipo__")
    cols = [col for col in preferred if col in features.columns]
    cols.extend([col for col in features.columns if str(col).startswith(prefixes)])
    numeric = set(features.select_dtypes(include=[np.number]).columns)
    seen = set()
    return [col for col in cols if col in numeric and not (col in seen or seen.add(col))]


def _feature_block(col: str) -> str:
    if col in {"pct_semanas_activas", "semanas_activas", "estabilidad_volumen", "cv_volumen"}:
        return "constancia"
    if col in {"volumen_log", "tallos_promedio_semana"}:
        return "volumen"
    if col in {"cumplimiento_tallos"}:
        return "cumplimiento"
    if col.startswith("share_color__") or col in {"share_top1_color", "share_top3_color", "entropia_color_norm", "colores_distintos"}:
        return "color"
    if col.startswith("share_producto__") or col in {"share_top1_producto", "share_top3_producto", "entropia_producto_norm", "productos_distintos"}:
        return "producto"
    if col.startswith("share_tipo__") or col in {"share_top1_tipo_pedido", "entropia_tipo_pedido_norm", "tipos_pedido_distintos"}:
        return "tipo_pedido"
    if col.startswith("share_sku__") or col in {"share_top1_sku", "share_top5_sku", "entropia_sku_norm"}:
        return "sku"
    if col.startswith("share_empaque__") or col in {"tallos_x_ramo_promedio", "ramos_x_caja_promedio"}:
        return "operativo"
    return "otros"


def _block_weights(config: ClusterConfig) -> dict[str, float]:
    return {
        "constancia": config.weight_constancy,
        "color": config.weight_color_mix,
        "producto": config.weight_product_mix,
        "tipo_pedido": config.weight_type_mix,
        "operativo": config.weight_operational,
        "sku": config.weight_sku_mix,
        "volumen": config.weight_volume,
        "cumplimiento": config.weight_fulfillment,
        "otros": 0.5,
    }


def _categorical_columns(features: pd.DataFrame) -> list[str]:
    return [
        col
        for col in [
            "pais_principal",
            "producto_dominante",
            "color_dominante",
            "tipo_pedido_dominante",
            "tipo_caja_dominante",
            "recomendacion_compra",
            "segmento_cliente",
        ]
        if col in features.columns
    ]


def _scaled_matrix(features: pd.DataFrame, cols: Iterable[str]) -> np.ndarray:
    x = features[list(cols)].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)
    std = x.std(axis=0, ddof=0).replace(0, 1)
    scaled = (x - x.mean(axis=0)) / std
    return scaled.fillna(0).to_numpy()


def _weighted_matrix(features: pd.DataFrame, cols: Iterable[str], config: ClusterConfig) -> np.ndarray:
    cols = list(cols)
    if not cols:
        return np.zeros((len(features), 0))
    x = pd.DataFrame(_scaled_matrix(features, cols), columns=cols, index=features.index)
    weights = _block_weights(config)
    for col in cols:
        x[col] = x[col] * np.sqrt(weights.get(_feature_block(col), 1.0))
    return x.to_numpy()


def _candidate_k(n_clients: int, max_k: int) -> list[int]:
    if n_clients < 4:
        return [1]
    upper = min(max_k, n_clients - 1)
    return list(range(2, upper + 1))


def _silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    unique = np.unique(labels)
    if x.shape[0] < 4 or len(unique) < 2 or len(unique) >= x.shape[0]:
        return np.nan
    try:
        from sklearn.metrics import silhouette_score

        return float(silhouette_score(x, labels))
    except Exception:
        return np.nan


def _calinski(x: np.ndarray, labels: np.ndarray) -> float:
    unique = np.unique(labels)
    if x.shape[0] < 4 or len(unique) < 2 or len(unique) >= x.shape[0]:
        return np.nan


def _cluster_size_metrics(labels: np.ndarray) -> dict[str, float]:
    if labels.size == 0:
        return {"min_cluster_size": 0, "max_cluster_share": 0.0, "singleton_clusters": 0}
    _, counts = np.unique(labels, return_counts=True)
    return {
        "min_cluster_size": int(counts.min()),
        "max_cluster_share": float(counts.max() / counts.sum()),
        "singleton_clusters": int((counts == 1).sum()),
    }


def _selection_score(silhouette: float, metrics: dict[str, float], config: ClusterConfig) -> float:
    base = -1.0 if pd.isna(silhouette) else float(silhouette)
    singleton_penalty = config.singleton_penalty * float(metrics.get("singleton_clusters", 0))
    dominance_penalty = config.dominance_penalty * max(0.0, float(metrics.get("max_cluster_share", 0)) - 0.80) / 0.20
    return base - singleton_penalty - dominance_penalty
    try:
        from sklearn.metrics import calinski_harabasz_score

        return float(calinski_harabasz_score(x, labels))
    except Exception:
        return np.nan


def _run_kmeans(x: np.ndarray, k: int, random_state: int) -> np.ndarray:
    from sklearn.cluster import KMeans

    return KMeans(n_clusters=k, random_state=random_state, n_init="auto").fit_predict(x)


def _run_hierarchical(x: np.ndarray, k: int) -> np.ndarray:
    from sklearn.cluster import AgglomerativeClustering

    return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(x)


def _run_kmodes(cat: pd.DataFrame, k: int, random_state: int, max_iter: int = 25) -> np.ndarray:
    values = cat.fillna("sin_info").astype(str).to_numpy()
    n = values.shape[0]
    if k <= 1 or n <= k:
        return np.zeros(n, dtype=int)
    rng = np.random.default_rng(random_state)
    seeds = rng.choice(n, size=k, replace=False)
    modes = values[seeds].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        distances = np.stack([(values != mode).sum(axis=1) for mode in modes], axis=1)
        new_labels = distances.argmin(axis=1)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        for cluster_id in range(k):
            cluster_values = values[labels == cluster_id]
            if cluster_values.size == 0:
                modes[cluster_id] = values[rng.integers(0, n)]
                continue
            for col_idx in range(values.shape[1]):
                counts = pd.Series(cluster_values[:, col_idx]).value_counts()
                modes[cluster_id, col_idx] = counts.index[0]
    return labels


def _kmodes_matrix(cat: pd.DataFrame) -> np.ndarray:
    if cat.empty:
        return np.zeros((0, 0))
    return pd.get_dummies(cat.fillna("sin_info").astype(str), dtype=float).to_numpy()


def _evaluate_market(features: pd.DataFrame, config: ClusterConfig) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    n_clients = len(features)
    numeric_cols = _feature_columns(features)
    cat_cols = _categorical_columns(features)
    x = _weighted_matrix(features, numeric_cols, config) if numeric_cols else np.zeros((n_clients, 0))
    cat = features[cat_cols].copy() if cat_cols else pd.DataFrame(index=features.index)
    cat_x = _kmodes_matrix(cat)
    evaluations = []
    labels_by_model: dict[str, np.ndarray] = {}

    if n_clients < config.min_clients_market:
        labels = np.zeros(n_clients, dtype=int)
        evaluations.append(
            {
                "metodo": "SIN_CLUSTER",
                "k": 1,
                "silhouette": np.nan,
                "calinski_harabasz": np.nan,
                "clientes": n_clients,
                "criterio": "menos_clientes_que_minimo",
            }
        )
        labels_by_model["SIN_CLUSTER__1"] = labels
        return pd.DataFrame(evaluations), labels_by_model

    for k in _candidate_k(n_clients, config.max_k):
        for method in ["K_MEDIAS", "JERARQUICO"]:
            try:
                labels = _run_kmeans(x, k, config.random_state) if method == "K_MEDIAS" else _run_hierarchical(x, k)
                key = f"{method}__{k}"
                labels_by_model[key] = labels
                silhouette = _silhouette(x, labels)
                size_metrics = _cluster_size_metrics(labels)
                evaluations.append(
                    {
                        "metodo": method,
                        "k": k,
                        "silhouette": silhouette,
                        "calinski_harabasz": _calinski(x, labels),
                        **size_metrics,
                        "selection_score": _selection_score(silhouette, size_metrics, config),
                        "clientes": n_clients,
                        "criterio": "matriz_ponderada_color_producto_tipo_constancia",
                    }
                )
            except Exception as exc:
                evaluations.append(
                    {
                        "metodo": method,
                        "k": k,
                        "silhouette": np.nan,
                        "calinski_harabasz": np.nan,
                        "clientes": n_clients,
                        "criterio": f"fallo: {exc}",
                    }
                )
        try:
            labels = _run_kmodes(cat, k, config.random_state) if cat_cols else np.zeros(n_clients, dtype=int)
            key = f"K_MODAS__{k}"
            labels_by_model[key] = labels
            silhouette = _silhouette(cat_x, labels)
            size_metrics = _cluster_size_metrics(labels)
            evaluations.append(
                {
                    "metodo": "K_MODAS",
                    "k": k,
                    "silhouette": silhouette,
                    "calinski_harabasz": _calinski(cat_x, labels),
                    **size_metrics,
                    "selection_score": _selection_score(silhouette, size_metrics, config),
                    "clientes": n_clients,
                    "criterio": "variables_categoricas_dominantes",
                }
            )
        except Exception as exc:
            evaluations.append(
                {
                    "metodo": "K_MODAS",
                    "k": k,
                    "silhouette": np.nan,
                    "calinski_harabasz": np.nan,
                    "clientes": n_clients,
                    "criterio": f"fallo: {exc}",
                }
            )
    return pd.DataFrame(evaluations), labels_by_model


def _pick_best(evaluation: pd.DataFrame) -> pd.Series:
    work = evaluation.copy()
    if work.empty:
        return pd.Series({"metodo": "SIN_CLUSTER", "k": 1})
    if "SIN_CLUSTER" in set(work["metodo"]):
        return work.iloc[0]
    if "selection_score" not in work.columns:
        work["selection_score"] = work["silhouette"].fillna(-999)
    work["selection_score_rank"] = work["selection_score"].fillna(-999)
    work["silhouette_rank"] = work["silhouette"].fillna(-999)
    work["calinski_rank"] = work["calinski_harabasz"].fillna(-999)
    method_preference = {"K_MEDIAS": 3, "JERARQUICO": 2, "K_MODAS": 1}
    work["preferencia_metodo"] = work["metodo"].map(method_preference).fillna(0)
    return work.sort_values(
        ["selection_score_rank", "silhouette_rank", "calinski_rank", "preferencia_metodo", "k"],
        ascending=[False, False, False, False, True],
    ).iloc[0]


def _cluster_name(frame: pd.DataFrame) -> str:
    if len(frame) == 1:
        row = frame.iloc[0]
        if float(row.get("tallos_total", 0) or 0) >= 1_000_000:
            return "ATIPICO_ALTO_VOLUMEN"
        if float(row.get("share_top5_sku", 0) or 0) >= 0.9 or float(row.get("share_top3_color", 0) or 0) >= 0.9:
            return "NICHO_ESPECIALIZADO"
        return "ATIPICO_BAJA_BASE"
    if len(frame) <= 3:
        if _safe_numeric(frame.get("share_top5_sku", pd.Series(dtype=float))).mean() >= 0.9:
            return "NICHO_ESPECIALIZADO"
        return "GRUPO_PEQUENO_ATIPICO"
    score = frame.get("score_compra_terminada_operativo", frame.get("score_compra_terminada", pd.Series(dtype=float)))
    avg_score = _safe_numeric(score).mean() if len(score) else 0
    frequency = _safe_numeric(frame.get("pct_semanas_activas", pd.Series(dtype=float))).mean()
    cv = _safe_numeric(frame.get("cv_volumen", pd.Series(dtype=float))).mean()
    top_color = _safe_numeric(frame.get("share_top3_color", pd.Series(dtype=float))).mean()
    top_sku = _safe_numeric(frame.get("share_top5_sku", pd.Series(dtype=float))).mean()
    if avg_score >= 75 and frequency >= 0.55 and cv <= 0.8:
        return "CONSTANTES_ESTRUCTURA_ESTABLE"
    if top_sku >= 0.75 and top_color >= 0.75:
        return "ESPECIALISTAS_SKU_COLOR"
    if frequency >= 0.45 and cv <= 1.2:
        return "RECURRENTES_VOLUMEN_MEDIO"
    if avg_score >= 60:
        return "PILOTO_COMPRA_TERMINADA"
    return "VARIABLES_O_BAJA_RECURRENCIA"


def _cluster_summary(assignments: pd.DataFrame) -> pd.DataFrame:
    if assignments.empty:
        return pd.DataFrame()
    rows = []
    for keys, frame in assignments.groupby(["mercado_cluster", "cluster_id", "nombre_cluster"], dropna=False):
        mercado, cluster_id, nombre = keys
        rows.append(
            {
                "mercado_cluster": mercado,
                "cluster_id": cluster_id,
                "nombre_cluster": nombre,
                "clientes": frame["cod_cliente"].nunique(),
                "tallos_total": frame["tallos_total"].sum(),
                "tallos_promedio_cliente": frame["tallos_total"].mean(),
                "ventas_usd_total": frame["ventas_usd_total"].sum(),
                "ventas_usd_promedio_cliente": frame["ventas_usd_total"].mean(),
                "semanas_activas_promedio": frame["semanas_activas"].mean(),
                "cv_volumen_promedio": frame["cv_volumen"].mean(),
                "variacion_reciente_vs_previa_promedio": frame["variacion_reciente_vs_previa"].mean(),
                "share_top3_color_promedio": frame["share_top3_color"].mean(),
                "share_top5_sku_promedio": frame["share_top5_sku"].mean(),
                "cumplimiento_promedio": frame["cumplimiento_tallos"].mean(),
                "complejidad_operativa_promedio": frame["complejidad_operativa_score"].mean(),
                "complejidad_operativa_dominante": _mode_value(frame["complejidad_operativa"]),
                "score_promedio": frame.get("score_compra_terminada_operativo", frame.get("score_compra_terminada", pd.Series(dtype=float))).mean(),
                "producto_dominante_cluster": _mode_value(frame["producto_dominante"]),
                "color_dominante_cluster": _mode_value(frame["color_dominante"]),
                "tipo_pedido_dominante_cluster": _mode_value(frame["tipo_pedido_dominante"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["mercado_cluster", "clientes"], ascending=[True, False])


FEATURE_LABELS = {
    "pct_semanas_activas": "constancia: % semanas activas",
    "semanas_activas": "constancia: semanas activas",
    "estabilidad_volumen": "constancia: estabilidad de volumen",
    "cv_volumen": "constancia: variabilidad semanal",
    "volumen_log": "volumen: escala total",
    "tallos_promedio_semana": "volumen: tallos promedio semana",
    "cumplimiento_tallos": "cumplimiento",
    "share_top1_color": "color: concentracion color principal",
    "share_top3_color": "color: concentracion top 3",
    "entropia_color_norm": "color: diversidad",
    "colores_distintos": "color: cantidad de colores",
    "share_top1_producto": "producto: concentracion producto principal",
    "share_top3_producto": "producto: concentracion top 3",
    "entropia_producto_norm": "producto: diversidad",
    "productos_distintos": "producto: cantidad de productos",
    "share_top1_tipo_pedido": "tipo pedido: concentracion formato principal",
    "entropia_tipo_pedido_norm": "tipo pedido: diversidad",
    "tipos_pedido_distintos": "tipo pedido: cantidad de formatos",
    "share_top1_sku": "SKU: concentracion SKU principal",
    "share_top5_sku": "SKU: repeticion top 5",
    "entropia_sku_norm": "SKU: diversidad",
    "tallos_x_ramo_promedio": "operativo: tallos por ramo",
    "ramos_x_caja_promedio": "operativo: ramos por caja",
}


def _feature_label(col: str) -> str:
    if col in FEATURE_LABELS:
        return FEATURE_LABELS[col]
    if col.startswith("share_color__"):
        return "color mix: " + col.split("__", 1)[1]
    if col.startswith("share_producto__"):
        return "producto mix: " + col.split("__", 1)[1]
    if col.startswith("share_tipo__"):
        return "tipo pedido mix: " + col.split("__", 1)[1]
    if col.startswith("share_empaque__"):
        return "empaque mix: " + col.split("__", 1)[1]
    if col.startswith("share_sku__"):
        return "SKU mix: " + col.split("__", 1)[1]
    return col


def explain_cluster_differences(assignments: pd.DataFrame, config: ClusterConfig | None = None, top_n: int = 10) -> pd.DataFrame:
    config = config or ClusterConfig()
    if assignments.empty:
        return pd.DataFrame()
    feature_cols = _feature_columns(assignments)
    if not feature_cols:
        return pd.DataFrame()
    rows = []
    weights = _block_weights(config)
    for market, market_frame in assignments.groupby("mercado_cluster", dropna=False):
        market_stats = market_frame[feature_cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)
        market_mean = market_stats.mean()
        market_std = market_stats.std(ddof=0).replace(0, 1)
        for keys, cluster_frame in market_frame.groupby(["cluster_id", "nombre_cluster"], dropna=False):
            cluster_id, cluster_name = keys
            cluster_mean = cluster_frame[feature_cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0).mean()
            delta = cluster_mean - market_mean
            z_delta = delta / market_std
            block_adjusted = z_delta.copy()
            for col in feature_cols:
                block_adjusted[col] = block_adjusted[col] * np.sqrt(weights.get(_feature_block(col), 1.0))
            top = block_adjusted.abs().sort_values(ascending=False).head(top_n).index
            for col in top:
                raw_delta = float(delta[col])
                z_value = float(z_delta[col])
                rows.append(
                    {
                        "mercado_cluster": market,
                        "cluster_id": cluster_id,
                        "nombre_cluster": cluster_name,
                        "bloque_variable": _feature_block(col),
                        "variable": col,
                        "lectura_variable": _feature_label(col),
                        "valor_cluster": float(cluster_mean[col]),
                        "promedio_mercado": float(market_mean[col]),
                        "diferencia": raw_delta,
                        "diferencia_estandarizada": z_value,
                        "peso_bloque": weights.get(_feature_block(col), 1.0),
                        "importancia_modelo": float(abs(block_adjusted[col])),
                        "lectura": "mas alto que su mercado" if raw_delta > 0 else "mas bajo que su mercado",
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["mercado_cluster", "cluster_id", "importancia_modelo"], ascending=[True, True, False])


def build_cluster_block_profile(assignments: pd.DataFrame, feature_importance: pd.DataFrame) -> pd.DataFrame:
    if assignments.empty:
        return pd.DataFrame()
    base_rows = []
    for keys, frame in assignments.groupby(["mercado_cluster", "cluster_id", "nombre_cluster"], dropna=False):
        market, cluster_id, name = keys
        base_rows.append(
            {
                "mercado_cluster": market,
                "cluster_id": cluster_id,
                "nombre_cluster": name,
                "clientes": frame["cod_cliente"].nunique(),
                "tipo_pedido_dominante_cluster": _mode_value(frame["tipo_pedido_dominante"]) if "tipo_pedido_dominante" in frame.columns else "sin_info",
                "producto_dominante_cluster": _mode_value(frame["producto_dominante"]) if "producto_dominante" in frame.columns else "sin_info",
                "color_dominante_cluster": _mode_value(frame["color_dominante"]) if "color_dominante" in frame.columns else "sin_info",
            }
        )
    base = pd.DataFrame(base_rows)
    if feature_importance.empty:
        return base
    block = (
        feature_importance.groupby(["mercado_cluster", "cluster_id", "nombre_cluster", "bloque_variable"], as_index=False)
        .agg(importancia_bloque=("importancia_modelo", "mean"), variables_clave=("lectura_variable", lambda s: "; ".join(s.head(3))))
    )
    pivot = block.pivot_table(
        index=["mercado_cluster", "cluster_id", "nombre_cluster"],
        columns="bloque_variable",
        values="importancia_bloque",
        aggfunc="mean",
        fill_value=0,
    ).reset_index()
    pivot.columns = [str(col) if not isinstance(col, tuple) else "_".join(col) for col in pivot.columns]
    out = base.merge(pivot, on=["mercado_cluster", "cluster_id", "nombre_cluster"], how="left")
    top_blocks = (
        block.sort_values(["mercado_cluster", "cluster_id", "importancia_bloque"], ascending=[True, True, False])
        .groupby(["mercado_cluster", "cluster_id"], as_index=False)
        .first()[["mercado_cluster", "cluster_id", "bloque_variable", "variables_clave"]]
        .rename(columns={"bloque_variable": "bloque_que_mas_diferencia", "variables_clave": "variables_clave_bloque"})
    )
    return out.merge(top_blocks, on=["mercado_cluster", "cluster_id"], how="left")


def _cosine_similarity(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return np.eye(x.shape[0])
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    normalized = np.divide(x, norms, out=np.zeros_like(x, dtype=float), where=norms != 0)
    return normalized @ normalized.T


def compute_market_similar_clients(assignments: pd.DataFrame, top_n: int = 10, config: ClusterConfig | None = None) -> pd.DataFrame:
    config = config or ClusterConfig()
    if assignments.empty:
        return pd.DataFrame()
    rows = []
    feature_cols = _feature_columns(assignments)
    for market, frame in assignments.groupby("mercado_cluster", dropna=False):
        if len(frame) < 2 or not feature_cols:
            continue
        x = _weighted_matrix(frame, feature_cols, config)
        sim = _cosine_similarity(x)
        local = frame.reset_index(drop=True)
        for idx, row in local.iterrows():
            scores = pd.Series(sim[idx], index=local.index).drop(index=idx).sort_values(ascending=False).head(top_n)
            for other_idx, score in scores.items():
                other = local.loc[other_idx]
                same_cluster = row.get("cluster_id") == other.get("cluster_id")
                rows.append(
                    {
                        "mercado_cluster": market,
                        "cluster_id_base": row.get("cluster_id"),
                        "nombre_cluster_base": row.get("nombre_cluster"),
                        "cod_cliente_base": row["cod_cliente"],
                        "cliente_base": row["cliente"],
                        "cod_cliente_similar": other["cod_cliente"],
                        "cliente_similar": other["cliente"],
                        "cluster_id_similar": other.get("cluster_id"),
                        "nombre_cluster_similar": other.get("nombre_cluster"),
                        "mismo_cluster": bool(same_cluster),
                        "similitud_total": round(float(score), 4),
                        "razon_mercado": "mismo mercado definido",
                        "razon_cluster": "mismo cluster final" if same_cluster else "parecido cercano fuera del cluster final",
                        "producto_base": row.get("producto_dominante"),
                        "producto_similar": other.get("producto_dominante"),
                        "color_base": row.get("color_dominante"),
                        "color_similar": other.get("color_dominante"),
                        "tipo_pedido_base": row.get("tipo_pedido_dominante"),
                        "tipo_pedido_similar": other.get("tipo_pedido_dominante"),
                    }
                )
    return pd.DataFrame(rows)


def run_cluster_pipeline(
    historico_confirmado: pd.DataFrame,
    perfil_cliente: pd.DataFrame | None = None,
    output_dir: str | Path | None = None,
    config: ClusterConfig | None = None,
    top_similar: int = 10,
) -> dict[str, pd.DataFrame]:
    """Segmenta clientes dentro de cada mercado y genera explicaciones.

    Evalua K-medias, K-modas y clustering jerarquico por mercado; selecciona
    la solucion de mejor calidad util y exporta asignaciones, perfiles,
    variables diferenciadoras y clientes similares.
    """
    config = config or ClusterConfig()
    features = build_client_clustering_dataset(historico_confirmado, perfil_cliente, config)
    if features.empty:
        outputs = {
            "cluster_features_cliente": features,
            "cluster_model_evaluation": pd.DataFrame(),
            "clusters_clientes": pd.DataFrame(),
            "cluster_resumen": pd.DataFrame(),
            "cluster_variables_diferenciadoras": pd.DataFrame(),
            "cluster_perfil_bloques": pd.DataFrame(),
            "clientes_similares": pd.DataFrame(),
        }
        if output_dir is not None:
            write_outputs(outputs, output_dir, excel_name="LGF_Clusters_Clientes.xlsx")
        return outputs

    evaluations = []
    assignments = []
    for market, frame in features.groupby("mercado_cluster", dropna=False):
        frame = frame.reset_index(drop=True)
        evaluation, labels_by_model = _evaluate_market(frame, config)
        evaluation["mercado_cluster"] = market
        best = _pick_best(evaluation)
        method = str(best.get("metodo", "SIN_CLUSTER"))
        k = int(best.get("k", 1))
        key = f"{method}__{k}"
        labels = labels_by_model.get(key, np.zeros(len(frame), dtype=int))
        local = frame.copy()
        local["metodo_cluster"] = method
        local["k_cluster"] = k
        local["cluster_local"] = labels.astype(int)
        local["cluster_id"] = local["mercado_cluster"] + "_C" + local["cluster_local"].astype(str).str.zfill(2)
        local["silhouette_modelo"] = best.get("silhouette", np.nan)
        local["calinski_modelo"] = best.get("calinski_harabasz", np.nan)
        local["nombre_cluster"] = (
            local.groupby("cluster_id", group_keys=False)
            .apply(lambda g: pd.Series(_cluster_name(g), index=g.index))
            .sort_index()
        )
        evaluations.append(evaluation)
        assignments.append(local)

    model_evaluation = pd.concat(evaluations, ignore_index=True) if evaluations else pd.DataFrame()
    clusters = pd.concat(assignments, ignore_index=True) if assignments else pd.DataFrame()
    similar = compute_market_similar_clients(clusters, top_n=top_similar, config=config)
    summary = _cluster_summary(clusters)
    feature_importance = explain_cluster_differences(clusters, config=config, top_n=12)
    block_profile = build_cluster_block_profile(clusters, feature_importance)

    dashboard_cols = [
        "mercado_cluster",
        "pais_principal",
        "metodo_cluster",
        "k_cluster",
        "cluster_id",
        "nombre_cluster",
        "cod_cliente",
        "cliente",
        "tallos_total",
        "ventas_usd_total",
        "ventas_usd_por_tallo",
        "participacion_tallos_mercado",
        "semanas_activas",
        "pct_semanas_activas",
        "tallos_promedio_semana",
        "cv_volumen",
        "tallos_ultimas_8_semanas",
        "tallos_8_semanas_previas",
        "variacion_reciente_vs_previa",
        "cumplimiento_tallos",
                "share_top3_color",
                "share_top1_color",
                "entropia_color_norm",
                "colores_distintos",
                "share_top1_producto",
                "share_top3_producto",
                "entropia_producto_norm",
                "productos_distintos",
                "share_top5_sku",
                "share_top1_sku",
                "entropia_sku_norm",
                "share_top1_tipo_pedido",
                "entropia_tipo_pedido_norm",
                "tallos_x_ramo_promedio",
        "ramos_x_caja_promedio",
        "complejidad_operativa_score",
        "complejidad_operativa",
        "producto_dominante",
        "color_dominante",
        "tipo_pedido_dominante",
        "tipo_caja_dominante",
        "score_compra_terminada",
        "score_compra_terminada_operativo",
        "recomendacion_compra",
        "segmento_cliente",
        "silhouette_modelo",
        "calinski_modelo",
    ]
    clusters_dashboard = clusters[[col for col in dashboard_cols if col in clusters.columns]].copy()
    clusters_dashboard = clusters_dashboard.sort_values(["mercado_cluster", "cluster_id", "tallos_total"], ascending=[True, True, False])

    outputs = {
        "cluster_features_cliente": features,
        "cluster_model_evaluation": model_evaluation.sort_values(["mercado_cluster", "metodo", "k"]).reset_index(drop=True),
        "clusters_clientes": clusters_dashboard.reset_index(drop=True),
        "cluster_resumen": summary.reset_index(drop=True),
        "cluster_variables_diferenciadoras": feature_importance.reset_index(drop=True),
        "cluster_perfil_bloques": block_profile.reset_index(drop=True),
        "clientes_similares": similar.reset_index(drop=True),
    }
    if output_dir is not None:
        write_outputs(outputs, output_dir, excel_name="LGF_Clusters_Clientes.xlsx")
    return outputs
