from __future__ import annotations

import numpy as np
import pandas as pd

CLIENT_KEYS = ["cod_cliente", "cliente"]


def _client_share_matrix(df: pd.DataFrame, feature_col: str, value_col: str = "tallos_analisis", max_features: int = 300) -> pd.DataFrame:
    tmp = df.groupby(CLIENT_KEYS + [feature_col], as_index=False)[value_col].sum()
    top_features = tmp.groupby(feature_col)[value_col].sum().sort_values(ascending=False).head(max_features).index
    tmp = tmp[tmp[feature_col].isin(top_features)]
    tmp["cliente_key"] = tmp["cod_cliente"].astype(str) + " | " + tmp["cliente"].astype(str)
    pivot = tmp.pivot_table(index="cliente_key", columns=feature_col, values=value_col, aggfunc="sum", fill_value=0)
    row_sums = pivot.sum(axis=1).replace(0, np.nan)
    return pivot.div(row_sums, axis=0).fillna(0)


def _split_key(cliente_key: str) -> tuple[str, str]:
    if " | " in cliente_key:
        cod, cliente = cliente_key.split(" | ", 1)
        return cod, cliente
    return cliente_key, cliente_key


def _cosine_similarity(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.eye(values.shape[0])
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    normalized = np.divide(values, norms, out=np.zeros_like(values, dtype=float), where=norms != 0)
    return normalized @ normalized.T


def compute_client_similarity(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if df.empty or df["cod_cliente"].nunique() < 2:
        return pd.DataFrame()
    matrices = {
        "producto_color": _client_share_matrix(df, "producto_color"),
        "sku_flexible": _client_share_matrix(df, "sku_flexible"),
        "sku_terminado": _client_share_matrix(df, "sku_terminado"),
        "empaque": _client_share_matrix(df, "empaque_operativo"),
        "tipo_pedido": _client_share_matrix(df, "tipo_pedido_operativo"),
    }
    clients = sorted(set().union(*[set(m.index) for m in matrices.values()]))
    sim_components = {}
    for name, mat in matrices.items():
        mat = mat.reindex(clients).fillna(0)
        sim = _cosine_similarity(mat.values.astype(float)) if mat.shape[1] else np.eye(len(clients))
        sim_components[name] = pd.DataFrame(sim, index=clients, columns=clients)

    total = (
        0.35 * sim_components["producto_color"]
        + 0.23 * sim_components["sku_flexible"]
        + 0.18 * sim_components["sku_terminado"]
        + 0.14 * sim_components["empaque"]
        + 0.10 * sim_components["tipo_pedido"]
    )

    rows = []
    for client in clients:
        cod_base, cliente_base = _split_key(client)
        ranked = total.loc[client].drop(index=client, errors="ignore").sort_values(ascending=False).head(top_n)
        for other, score in ranked.items():
            cod_sim, cliente_sim = _split_key(other)
            rows.append({
                "cod_cliente_base": cod_base,
                "cliente_base": cliente_base,
                "cod_cliente_similar": cod_sim,
                "cliente_similar": cliente_sim,
                "similitud_total": round(float(score), 4),
                "similitud_producto_color": round(float(sim_components["producto_color"].loc[client, other]), 4),
                "similitud_sku_flexible": round(float(sim_components["sku_flexible"].loc[client, other]), 4),
                "similitud_sku_terminado": round(float(sim_components["sku_terminado"].loc[client, other]), 4),
                "similitud_empaque": round(float(sim_components["empaque"].loc[client, other]), 4),
                "similitud_tipo_pedido": round(float(sim_components["tipo_pedido"].loc[client, other]), 4),
                "compatibilidad_operativa": _compatibility_label(float(score)),
            })
    return pd.DataFrame(rows)


def _compatibility_label(score: float) -> str:
    if score >= 0.80:
        return "ALTA_COMPATIBILIDAD_TERMINADO"
    if score >= 0.65:
        return "COMPATIBLE_PARA_PILOTO"
    if score >= 0.50:
        return "COMPATIBLE_SOLO_COLOR_BASE"
    return "BAJA_COMPATIBILIDAD"


def cluster_clients(df: pd.DataFrame, client_profile: pd.DataFrame, n_clusters: int = 5) -> pd.DataFrame:
    if df.empty or client_profile.empty:
        return pd.DataFrame()
    mix = _client_share_matrix(df, "producto_color", max_features=100)
    if mix.empty:
        return pd.DataFrame()
    profile_cols = ["pct_semanas_activas", "cv_volumen", "cumplimiento_tallos", "share_top3_color", "share_top5_sku_terminado", "share_top3_empaque", "score_compra_terminada"]
    prof = client_profile.copy()
    prof["cliente_key"] = prof["cod_cliente"].astype(str) + " | " + prof["cliente"].astype(str)
    prof = prof.set_index("cliente_key")[profile_cols].reindex(mix.index).fillna(0)
    x = pd.concat([prof, mix], axis=1).fillna(0)
    if len(x) < 2:
        cod, cliente = _split_key(x.index[0])
        return pd.DataFrame({"cod_cliente": [cod], "cliente": [cliente], "cluster_id": [0], "nombre_cluster": ["SIN_CLUSTER"]})

    k = min(max(2, n_clusters), len(x))
    numeric = x.astype(float)
    std = numeric.std(axis=0).replace(0, 1)
    x_scaled = ((numeric - numeric.mean(axis=0)) / std).fillna(0).to_numpy()
    try:
        from sklearn.cluster import KMeans

        labels = KMeans(n_clusters=k, random_state=42, n_init="auto").fit_predict(x_scaled)
    except Exception:
        labels = pd.qcut(prof["score_compra_terminada"].rank(method="first"), q=k, labels=False, duplicates="drop").fillna(0).astype(int).to_numpy()
    out = pd.DataFrame({"cliente_key": x.index, "cluster_id": labels})
    out[["cod_cliente", "cliente"]] = out["cliente_key"].apply(lambda v: pd.Series(_split_key(v)))
    out = out.merge(client_profile[["cod_cliente", "cliente", "score_compra_terminada", "score_color", "score_sku_terminado", "cumplimiento_tallos"]], on=CLIENT_KEYS, how="left")
    out["nombre_cluster"] = out.groupby("cluster_id")["score_compra_terminada"].transform(lambda s: _cluster_name(s.mean()))
    return out.drop(columns=["cliente_key"]).sort_values(["cluster_id", "score_compra_terminada"], ascending=[True, False]).reset_index(drop=True)


def _cluster_name(avg_score: float) -> str:
    if avg_score >= 75:
        return "CLIENTES_ESTABLES_PARA_TERMINADO"
    if avg_score >= 60:
        return "CLIENTES_PILOTO"
    if avg_score >= 45:
        return "CLIENTES_COMPRA_COLOR_BASE"
    return "CLIENTES_VARIABLES_NO_ANTICIPAR"
