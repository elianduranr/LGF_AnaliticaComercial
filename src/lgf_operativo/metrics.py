from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

CLIENT_KEYS = ["cod_cliente", "cliente"]


def entropy_from_shares(shares: pd.Series) -> float:
    values = shares.astype(float).values
    values = values[values > 0]
    if len(values) <= 1:
        return 0.0
    ent = -np.sum(values * np.log(values))
    max_ent = np.log(len(values))
    return float(ent / max_ent) if max_ent > 0 else 0.0


def normalized_score_high_is_good(series: pd.Series) -> pd.Series:
    s = series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)
    if s.max() == s.min():
        return pd.Series(np.where(s.max() > 0, 100, 0), index=series.index)
    return ((s - s.min()) / (s.max() - s.min()) * 100).clip(0, 100)


def normalized_score_low_is_good(series: pd.Series) -> pd.Series:
    return 100 - normalized_score_high_is_good(series)


def consecutive_weekly_similarity(df: pd.DataFrame, value_col: str, item_col: str) -> pd.DataFrame:
    grouped = df.groupby(CLIENT_KEYS + ["anio_semana", item_col], as_index=False)[value_col].sum()
    totals = grouped.groupby(CLIENT_KEYS + ["anio_semana"], as_index=False)[value_col].sum().rename(columns={value_col: "total"})
    grouped = grouped.merge(totals, on=CLIENT_KEYS + ["anio_semana"], how="left")
    grouped["share"] = grouped[value_col] / grouped["total"].replace(0, np.nan)

    results = []
    for (cod_cliente, cliente), tmp in grouped.groupby(CLIENT_KEYS):
        pivot = tmp.pivot_table(index="anio_semana", columns=item_col, values="share", aggfunc="sum", fill_value=0)
        pivot = pivot.sort_index()
        if len(pivot) < 2:
            avg_sim = 0.0
            min_sim = 0.0
        else:
            sims = []
            arr = pivot.values
            for i in range(1, len(arr)):
                prev = arr[i - 1].astype(float)
                curr = arr[i].astype(float)
                denom = np.linalg.norm(prev) * np.linalg.norm(curr)
                sims.append(float(prev.dot(curr) / denom) if denom else 0.0)
            avg_sim = float(np.mean(sims)) if sims else 0.0
            min_sim = float(np.min(sims)) if sims else 0.0
        results.append({
            "cod_cliente": cod_cliente,
            "cliente": cliente,
            f"similitud_promedio_{item_col}_semanal": avg_sim,
            f"similitud_minima_{item_col}_semanal": min_sim,
        })
    return pd.DataFrame(results)


def build_client_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Build client-level operational characterization and scores.

    This must receive only confirmed historical orders for the base characterization.
    """
    if df.empty:
        return pd.DataFrame()

    weekly = df.groupby(CLIENT_KEYS + ["anio_semana"], as_index=False).agg(
        tallos_semana=("tallos_analisis", "sum"),
        tallos_confirmados_semana=("tallos_confirmados", "sum"),
        faltante_semana=("faltante_tallos", "sum"),
        productos_distintos=("producto", "nunique"),
        colores_distintos=("color", "nunique"),
        variedades_distintas=("variedad", "nunique"),
        skus_terminados_distintos=("sku_terminado", "nunique"),
        skus_flexibles_distintos=("sku_flexible", "nunique"),
        tipos_pedido_distintos=("tipo_pedido_operativo", "nunique"),
        fechas_distintas=("fecha", "nunique"),
    )

    total_weeks_observed = max(df["anio_semana"].nunique(), 1)
    base = weekly.groupby(CLIENT_KEYS, as_index=False).agg(
        semanas_activas=("anio_semana", "nunique"),
        tallos_total=("tallos_semana", "sum"),
        tallos_promedio_semana=("tallos_semana", "mean"),
        tallos_mediana_semana=("tallos_semana", "median"),
        tallos_std_semana=("tallos_semana", "std"),
        tallos_min_semana=("tallos_semana", "min"),
        tallos_max_semana=("tallos_semana", "max"),
        productos_promedio_semana=("productos_distintos", "mean"),
        colores_promedio_semana=("colores_distintos", "mean"),
        variedades_promedio_semana=("variedades_distintas", "mean"),
        skus_terminados_promedio_semana=("skus_terminados_distintos", "mean"),
        skus_flexibles_promedio_semana=("skus_flexibles_distintos", "mean"),
        tipos_pedido_promedio_semana=("tipos_pedido_distintos", "mean"),
        tallos_confirmados_total=("tallos_confirmados_semana", "sum"),
        faltante_total=("faltante_semana", "sum"),
    )
    max_hist_date = df["fecha"].max()
    client_recency = df.groupby(CLIENT_KEYS, as_index=False).agg(
        primera_fecha_confirmada=("fecha", "min"),
        ultima_fecha_confirmada=("fecha", "max"),
    )
    client_recency["dias_desde_ultima_compra"] = (max_hist_date - client_recency["ultima_fecha_confirmada"]).dt.days
    base = base.merge(client_recency, on=CLIENT_KEYS, how="left")
    for weeks in [8, 12, 26, 52]:
        recent = df[df["fecha"] >= max_hist_date - pd.Timedelta(weeks=weeks)]
        recent_summary = recent.groupby(CLIENT_KEYS, as_index=False).agg(
            **{
                f"semanas_activas_ult_{weeks}w": ("anio_semana", "nunique"),
                f"tallos_ult_{weeks}w": ("tallos_analisis", "sum"),
            }
        )
        base = base.merge(recent_summary, on=CLIENT_KEYS, how="left")
        base[f"semanas_activas_ult_{weeks}w"] = base[f"semanas_activas_ult_{weeks}w"].fillna(0).astype(int)
        base[f"tallos_ult_{weeks}w"] = base[f"tallos_ult_{weeks}w"].fillna(0)
    base["cliente_activo_ult_16w"] = base["dias_desde_ultima_compra"].fillna(99999).le(16 * 7)
    base["semanas_observadas_global"] = total_weeks_observed
    base["pct_semanas_activas"] = base["semanas_activas"] / total_weeks_observed
    base["cv_volumen"] = (base["tallos_std_semana"].fillna(0) / base["tallos_promedio_semana"].replace(0, np.nan)).fillna(0)
    base["cumplimiento_tallos"] = (base["tallos_confirmados_total"] / base["tallos_total"].replace(0, np.nan)).fillna(0).clip(0, 1)
    base["incumplimiento_tallos"] = 1 - base["cumplimiento_tallos"]

    def top_share(group_col: str, top_n: int, output_name: str) -> pd.DataFrame:
        tmp = df.groupby(CLIENT_KEYS + [group_col], as_index=False)["tallos_analisis"].sum()
        tmp = tmp.sort_values(CLIENT_KEYS + ["tallos_analisis"], ascending=[True, True, False])
        top = tmp.groupby(CLIENT_KEYS).head(top_n).groupby(CLIENT_KEYS, as_index=False)["tallos_analisis"].sum()
        total = df.groupby(CLIENT_KEYS, as_index=False)["tallos_analisis"].sum().rename(columns={"tallos_analisis": "total"})
        out = total.merge(top, on=CLIENT_KEYS, how="left")
        out[output_name] = (out["tallos_analisis"].fillna(0) / out["total"].replace(0, np.nan)).fillna(0)
        return out[CLIENT_KEYS + [output_name]]

    for col, n, name in [
        ("sku_terminado", 5, "share_top5_sku_terminado"),
        ("sku_flexible", 5, "share_top5_sku_flexible"),
        ("color", 3, "share_top3_color"),
        ("producto_color", 5, "share_top5_producto_color"),
        ("empaque_operativo", 3, "share_top3_empaque"),
        ("tipo_pedido_operativo", 1, "share_top1_tipo_pedido"),
        ("estructura_pedido", 3, "share_top3_estructura_pedido"),
        ("llave_analisis_operativo", 5, "share_top5_analisis_operativo"),
    ]:
        if col in df.columns:
            base = base.merge(top_share(col, n, name), on=CLIENT_KEYS, how="left")

    entropies = []
    for (cod_cliente, cliente), tmp in df.groupby(CLIENT_KEYS):
        total = tmp["tallos_analisis"].sum()
        row = {
            "cod_cliente": cod_cliente,
            "cliente": cliente,
            "entropia_color": entropy_from_shares(tmp.groupby("color")["tallos_analisis"].sum() / total),
            "entropia_sku_terminado": entropy_from_shares(tmp.groupby("sku_terminado")["tallos_analisis"].sum() / total),
            "entropia_empaque": entropy_from_shares(tmp.groupby("empaque_operativo")["tallos_analisis"].sum() / total),
            "entropia_tipo_pedido": entropy_from_shares(tmp.groupby("tipo_pedido_operativo")["tallos_analisis"].sum() / total),
            "entropia_estructura_pedido": entropy_from_shares(tmp.groupby("estructura_pedido")["tallos_analisis"].sum() / total),
        }
        if "llave_analisis_operativo" in tmp.columns:
            row["entropia_analisis_operativo"] = entropy_from_shares(tmp.groupby("llave_analisis_operativo")["tallos_analisis"].sum() / total)
        entropies.append(row)
    base = base.merge(pd.DataFrame(entropies), on=CLIENT_KEYS, how="left")

    for item_col in ["color", "sku_terminado", "sku_flexible", "tipo_pedido_operativo", "estructura_pedido", "llave_analisis_operativo"]:
        if item_col in df.columns:
            base = base.merge(consecutive_weekly_similarity(df, "tallos_analisis", item_col), on=CLIENT_KEYS, how="left")

    for col in ["similitud_promedio_color_semanal", "similitud_promedio_sku_terminado_semanal", "similitud_promedio_sku_flexible_semanal", "similitud_promedio_tipo_pedido_operativo_semanal", "similitud_promedio_estructura_pedido_semanal", "similitud_promedio_llave_analisis_operativo_semanal"]:
        if col in base.columns:
            base[col] = base[col].fillna(0)
    if "share_top5_analisis_operativo" not in base.columns:
        base["share_top5_analisis_operativo"] = base.get("share_top5_sku_terminado", 0)
    if "entropia_analisis_operativo" not in base.columns:
        base["entropia_analisis_operativo"] = base.get("entropia_estructura_pedido", 0)
    if "similitud_promedio_llave_analisis_operativo_semanal" not in base.columns:
        base["similitud_promedio_llave_analisis_operativo_semanal"] = base.get("similitud_promedio_estructura_pedido_semanal", 0)

    base["score_frecuencia"] = (base["pct_semanas_activas"] * 100).clip(0, 100)
    base["score_volumen"] = normalized_score_low_is_good(base["cv_volumen"].clip(0, 2))
    base["score_color"] = (
        0.45 * (base["share_top3_color"].fillna(0) * 100)
        + 0.35 * (base["similitud_promedio_color_semanal"].fillna(0) * 100)
        + 0.20 * normalized_score_low_is_good(base["entropia_color"].fillna(0))
    ).clip(0, 100)
    base["score_sku_terminado"] = (
        0.55 * (base["share_top5_sku_terminado"].fillna(0) * 100)
        + 0.30 * (base["similitud_promedio_sku_terminado_semanal"].fillna(0) * 100)
        + 0.15 * normalized_score_low_is_good(base["entropia_sku_terminado"].fillna(0))
    ).clip(0, 100)
    base["score_analisis_operativo"] = (
        0.50 * (base["share_top5_analisis_operativo"].fillna(0) * 100)
        + 0.35 * (base["similitud_promedio_llave_analisis_operativo_semanal"].fillna(0) * 100)
        + 0.15 * normalized_score_low_is_good(base["entropia_analisis_operativo"].fillna(0))
    ).clip(0, 100)
    base["score_empaque"] = (
        0.70 * (base["share_top3_empaque"].fillna(0) * 100)
        + 0.30 * normalized_score_low_is_good(base["entropia_empaque"].fillna(0))
    ).clip(0, 100)
    base["score_tipo_pedido"] = (
        0.55 * (base["share_top1_tipo_pedido"].fillna(0) * 100)
        + 0.30 * (base["similitud_promedio_tipo_pedido_operativo_semanal"].fillna(0) * 100)
        + 0.15 * normalized_score_low_is_good(base["entropia_tipo_pedido"].fillna(0))
    ).clip(0, 100)
    base["score_oportunidad_incumplimiento"] = (base["incumplimiento_tallos"].clip(0, 1) * 100).fillna(0)

    tipo_share = df.pivot_table(
        index=CLIENT_KEYS,
        columns="tipo_pedido_operativo",
        values="tallos_analisis",
        aggfunc="sum",
        fill_value=0,
    )
    tipo_total = tipo_share.sum(axis=1).replace(0, np.nan)
    for tipo_name in ["SOLIDO", "SURTIDO", "SURTIDO_M", "RAINBOW", "BQT", "COMBO", "BOUQUET", "BULK"]:
        col = f"share_{tipo_name.lower()}"
        base = base.merge(
            (tipo_share.get(tipo_name, pd.Series(0, index=tipo_share.index)) / tipo_total)
            .fillna(0)
            .rename(col)
            .reset_index(),
            on=CLIENT_KEYS,
            how="left",
        )
    base["share_facil_compra"] = base[["share_solido", "share_surtido", "share_surtido_m"]].sum(axis=1).clip(0, 1)
    base["share_estructuras_mixtas"] = base[
        ["share_surtido", "share_surtido_m", "share_rainbow", "share_bouquet", "share_bqt", "share_combo"]
    ].sum(axis=1).clip(0, 1)
    base["score_facilidad_compra_operativa"] = (base["share_facil_compra"] * 100 - base["share_rainbow"].fillna(0) * 40).clip(0, 100)

    base["score_compra_terminada"] = (
        0.14 * base["score_frecuencia"]
        + 0.14 * base["score_volumen"]
        + 0.23 * base["score_color"]
        + 0.18 * base["score_analisis_operativo"]
        + 0.08 * base["score_empaque"]
        + 0.08 * base["score_tipo_pedido"]
        + 0.15 * base["score_oportunidad_incumplimiento"]
    ).round(2)
    base["score_compra_terminada_operativo"] = (
        0.82 * base["score_compra_terminada"] + 0.18 * base["score_facilidad_compra_operativa"]
    ).round(2)

    base["recomendacion_compra"] = np.select(
        [
            base["score_compra_terminada"] >= 80,
            base["score_compra_terminada"].between(65, 79.999),
            base["score_compra_terminada"].between(50, 64.999),
        ],
        ["ALTA_PRIORIDAD_COMPRAR_TERMINADO", "PILOTO_SKUS_TOP", "COMPRAR_COLOR_O_BASE_VALIDAR"],
        default="NO_ANTICIPAR_TERMINADO",
    )

    base["segmento_cliente"] = np.select(
        [
            (base["score_frecuencia"] >= 70) & (base["score_color"] >= 70) & (base["score_sku_terminado"] >= 65),
            (base["score_frecuencia"] >= 70) & (base["score_color"] < 70),
            (base["score_frecuencia"] < 40),
        ],
        ["CONSTANTE_ESTRUCTURA_ESTABLE", "CONSTANTE_PERO_VARIABLE_COLOR_SKU", "OCASIONAL"],
        default="INTERMEDIO",
    )
    return base.sort_values("score_compra_terminada", ascending=False).reset_index(drop=True)


def build_mix_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    outputs = {}
    if df.empty:
        return outputs

    total_cliente = df.groupby(CLIENT_KEYS, as_index=False)["tallos_analisis"].sum().rename(columns={"tallos_analisis": "tallos_cliente"})
    definitions = {
        "mix_tipo_pedido": CLIENT_KEYS + ["tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta"],
        "mix_color": CLIENT_KEYS + ["color"],
        "mix_producto": CLIENT_KEYS + ["producto"],
        "mix_variedad": CLIENT_KEYS + ["producto", "variedad", "color"],
        "mix_sku_terminado": CLIENT_KEYS + ["sku_terminado", "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque", "receta"],
        "mix_sku_flexible": CLIENT_KEYS + ["sku_flexible", "tipo_pedido_operativo", "producto", "color", "grado", "tipo_caja", "tallos_x_ramo"],
        "mix_empaque": CLIENT_KEYS + ["empaque_operativo", "tipo_pedido_operativo", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque"],
    }
    optional_definitions = {
        "mix_analisis_operativo": CLIENT_KEYS + ["familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo", "llave_analisis_operativo", "tipo_pedido_operativo", "producto", "color", "tipo_caja", "receta"],
        "mix_color_rol": CLIENT_KEYS + ["familia_analisis_operativa", "rol_color_operativo", "tipo_pedido_operativo", "producto", "color"],
    }
    for name, cols in optional_definitions.items():
        if all(col in df.columns for col in cols):
            definitions[name] = cols
    for name, cols in definitions.items():
        tmp = df.groupby(cols, as_index=False).agg(
            tallos=("tallos_analisis", "sum"),
            tallos_confirmados=("tallos_confirmados", "sum"),
            faltante_tallos=("faltante_tallos", "sum"),
            semanas_activas=("anio_semana", "nunique"),
            fechas_activas=("fecha", "nunique"),
        )
        tmp = tmp.merge(total_cliente, on=CLIENT_KEYS, how="left")
        tmp["participacion_cliente"] = (tmp["tallos"] / tmp["tallos_cliente"].replace(0, np.nan)).fillna(0)
        tmp["cumplimiento"] = (tmp["tallos_confirmados"] / tmp["tallos"].replace(0, np.nan)).fillna(0).clip(0, 1)
        outputs[name] = tmp.sort_values(CLIENT_KEYS + ["tallos"], ascending=[True, True, False]).reset_index(drop=True)

    outputs["serie_cliente_semana"] = df.groupby(CLIENT_KEYS + ["anio_semana", "anio", "semana_iso"], as_index=False).agg(
        tallos=("tallos_analisis", "sum"),
        tallos_confirmados=("tallos_confirmados", "sum"),
        faltante_tallos=("faltante_tallos", "sum"),
        colores=("color", "nunique"),
        skus_terminados=("sku_terminado", "nunique"),
        productos=("producto", "nunique"),
        tipos_pedido=("tipo_pedido_operativo", "nunique"),
    )
    outputs["serie_cliente_mes_color"] = df.groupby(CLIENT_KEYS + ["anio", "mes_num", "color"], as_index=False).agg(
        tallos=("tallos_analisis", "sum"),
        faltante_tallos=("faltante_tallos", "sum"),
    )
    return outputs


def build_sales_visualizer_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build real-sales aggregates for the general client visualizer.

    Prices are calculated from confirmed stems:
    - USD price = ventas_usd / tallos_confirmados
    - Original currency price = valor_total_original / tallos_confirmados
    """
    outputs: dict[str, pd.DataFrame] = {}
    if df.empty:
        return outputs

    work = df.copy()
    for col in ["tallos_confirmados", "ventas_usd", "valor_total_original"]:
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    if "moneda_original" not in work.columns:
        work["moneda_original"] = "sin_info"
    for col in ["pedido", "caja_operativa", "producto", "color", "tipo_pedido_operativo"]:
        if col not in work.columns:
            work[col] = "sin_info"

    def summarize(group_cols: list[str]) -> pd.DataFrame:
        out = work.groupby(group_cols, dropna=False, as_index=False).agg(
            tallos_confirmados=("tallos_confirmados", "sum"),
            ventas_usd=("ventas_usd", "sum"),
            valor_total_original=("valor_total_original", "sum"),
            pedidos=("pedido", "nunique"),
            cajas_ids=("caja_operativa", "nunique"),
        )
        out["precio_usd_tallo"] = (
            out["ventas_usd"] / out["tallos_confirmados"].replace(0, np.nan)
        ).fillna(0)
        out["precio_moneda_original_tallo"] = (
            out["valor_total_original"] / out["tallos_confirmados"].replace(0, np.nan)
        ).fillna(0)
        return out

    outputs["ventas_semana_cliente_producto"] = summarize(
        [
            "anio",
            "semana_iso",
            "anio_semana",
            "cod_cliente",
            "cliente",
            "tipo_pedido_operativo",
            "producto",
            "color",
            "moneda_original",
        ]
    ).sort_values(["anio", "semana_iso", "cod_cliente", "tallos_confirmados"], ascending=[True, True, True, False])

    outputs["ventas_producto_periodo"] = summarize(
        ["anio", "semana_iso", "anio_semana", "tipo_pedido_operativo", "producto", "color", "moneda_original"]
    ).sort_values(["anio", "semana_iso", "tallos_confirmados"], ascending=[True, True, False])

    outputs["ventas_cliente_periodo"] = summarize(
        ["anio", "semana_iso", "anio_semana", "cod_cliente", "cliente", "moneda_original"]
    ).sort_values(["anio", "semana_iso", "tallos_confirmados"], ascending=[True, True, False])

    outputs["ventas_caja_periodo"] = summarize(
        [
            "anio",
            "semana_iso",
            "anio_semana",
            "cod_cliente",
            "cliente",
            "tipo_pedido_operativo",
            "producto",
            "color",
            "caja_operativa",
            "tipo_caja",
            "moneda_original",
        ]
    ).sort_values(["anio", "semana_iso", "tallos_confirmados"], ascending=[True, True, False])

    return {name: frame.reset_index(drop=True) for name, frame in outputs.items()}


def build_repeated_structures(df: pd.DataFrame) -> pd.DataFrame:
    """Detect active repeated structures by operational order type.

    Business rule: solids are evaluated by exact finished SKU. Assorted, rainbow,
    combo and bouquet formats are evaluated by composition/recipe key. Bulk is
    evaluated by product-color. This prevents penalizing assorted customers for
    not repeating a finished SKU that operationally should be read as a mix.
    """
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    max_date = work["fecha"].max()
    recent_12 = work[work["fecha"] >= max_date - pd.Timedelta(weeks=12)].copy()
    recent_4 = work[work["fecha"] >= max_date - pd.Timedelta(weeks=4)].copy()

    def pick_structure_key(row: pd.Series) -> str:
        tipo = str(row.get("tipo_pedido_operativo", "")).upper()
        if tipo == "SOLIDO":
            return str(row.get("sku_terminado", "sin_info"))
        if tipo in {"SURTIDO", "SURTIDO_M", "RAINBOW", "COMBO", "BOUQUET", "BQT"}:
            return str(row.get("receta_programa_key", row.get("receta_estructura_key", row.get("llave_analisis_operativo", "sin_info"))))
        if tipo == "BULK":
            return str(row.get("producto_color", row.get("llave_analisis_operativo", "sin_info")))
        return str(row.get("llave_analisis_operativo", row.get("estructura_pedido", "sin_info")))

    work["estructura_accionable"] = work.apply(pick_structure_key, axis=1)
    recent_12["estructura_accionable"] = recent_12.apply(pick_structure_key, axis=1) if not recent_12.empty else pd.Series(dtype="object")
    recent_4["estructura_accionable"] = recent_4.apply(pick_structure_key, axis=1) if not recent_4.empty else pd.Series(dtype="object")

    keys = CLIENT_KEYS + [
        "estructura_accionable",
        "tipo_pedido_operativo",
        "producto",
        "variedad",
        "color",
        "tipo_caja",
        "tallos_x_ramo",
        "capuchon",
        "comida",
        "empaque",
    ]
    keys = [col for col in keys if col in work.columns]

    base = work.groupby(keys, dropna=False, as_index=False).agg(
        tallos_historico=("tallos_analisis", "sum"),
        semanas_historico=("anio_semana", "nunique"),
        cumplimiento=("tallos_confirmados", "sum"),
        pedidos_historico=("pedido", "nunique") if "pedido" in work.columns else ("tallos_analisis", "size"),
    )
    pedidos_sum = work.groupby(keys, dropna=False, as_index=False)["tallos_analisis"].sum().rename(columns={"tallos_analisis": "tallos_pedidos_para_cumplimiento"})
    base = base.merge(pedidos_sum, on=keys, how="left")
    base["cumplimiento"] = (
        base["cumplimiento"] / base["tallos_pedidos_para_cumplimiento"].replace(0, np.nan)
    ).fillna(0).clip(0, 1)

    if not recent_12.empty:
        r12 = recent_12.groupby(keys, dropna=False, as_index=False).agg(
            tallos_ultimas_12_semanas=("tallos_analisis", "sum"),
            frecuencia_ultimas_12_semanas=("anio_semana", "nunique"),
        )
        base = base.merge(r12, on=keys, how="left")
    if not recent_4.empty:
        r4 = recent_4.groupby(keys, dropna=False, as_index=False).agg(
            tallos_ultimas_4_semanas=("tallos_analisis", "sum"),
            frecuencia_ultimas_4_semanas=("anio_semana", "nunique"),
        )
        base = base.merge(r4, on=keys, how="left")

    for col in ["tallos_ultimas_12_semanas", "frecuencia_ultimas_12_semanas", "tallos_ultimas_4_semanas", "frecuencia_ultimas_4_semanas"]:
        if col not in base.columns:
            base[col] = 0
        base[col] = base[col].fillna(0)

    base["vigencia_estructura"] = np.select(
        [
            (base["frecuencia_ultimas_4_semanas"] > 0) & (base["frecuencia_ultimas_12_semanas"] >= 2),
            (base["frecuencia_ultimas_12_semanas"] > 0) & (base["semanas_historico"] <= base["frecuencia_ultimas_12_semanas"] + 1),
            base["frecuencia_ultimas_12_semanas"] > 0,
        ],
        ["VIGENTE", "NUEVA_RECIENTE", "ACTIVA_RECIENTE"],
        default="HISTORICA_NO_RECIENTE",
    )

    tipo = base["tipo_pedido_operativo"].astype(str).str.upper()
    base["recomendacion"] = np.select(
        [
            tipo.eq("SOLIDO") & base["frecuencia_ultimas_12_semanas"].ge(3) & base["cumplimiento"].lt(0.98),
            tipo.eq("SOLIDO") & base["frecuencia_ultimas_12_semanas"].ge(2),
            tipo.isin(["SURTIDO", "SURTIDO_M"]) & base["frecuencia_ultimas_12_semanas"].ge(2),
            tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]) & base["frecuencia_ultimas_12_semanas"].ge(2),
            tipo.eq("BULK") & base["frecuencia_ultimas_12_semanas"].ge(2),
            base["frecuencia_ultimas_12_semanas"].eq(0),
        ],
        ["COMPRAR_TERMINADO", "PILOTO", "COMPRAR_COLOR_BASE", "REVISAR_MANUAL", "COMPRAR_COLOR_BASE", "NO_ANTICIPAR"],
        default="REVISAR_MANUAL",
    )

    base = base.rename(columns={"tallos_x_ramo": "tallos_por_ramo"})
    preferred = [
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
    cols = [col for col in preferred if col in base.columns]
    return base[cols].sort_values(
        ["cod_cliente", "tallos_ultimas_12_semanas", "frecuencia_ultimas_12_semanas", "tallos_historico"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)


def build_typical_week(df: pd.DataFrame) -> pd.DataFrame:
    """Build week-of-year behavior by client and operational structure."""
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    max_date = work["fecha"].max()
    recent = work[work["fecha"] >= max_date - pd.Timedelta(weeks=12)].copy()
    keys = CLIENT_KEYS + [
        "semana_iso",
        "producto",
        "tipo_pedido_operativo",
        "color",
        "variedad",
        "tipo_caja",
        "tallos_x_ramo",
    ]
    keys = [col for col in keys if col in work.columns]
    weekly = work.groupby(keys + ["anio"], dropna=False, as_index=False)["tallos_analisis"].sum()
    out = weekly.groupby(keys, dropna=False, as_index=False).agg(
        tallos_mediana_historica_semana=("tallos_analisis", "median"),
        tallos_promedio_historico_semana=("tallos_analisis", "mean"),
        veces_aparece_en_misma_semana=("anio", "nunique"),
        cv_semana=("tallos_analisis", lambda s: float(s.std() / s.mean()) if s.mean() else 0.0),
    )
    if not recent.empty:
        recent_summary = recent.groupby(keys, dropna=False, as_index=False).agg(
            comportamiento_reciente=("tallos_analisis", "sum"),
            semanas_recientes=("anio_semana", "nunique"),
        )
        out = out.merge(recent_summary, on=keys, how="left")
    else:
        out["comportamiento_reciente"] = 0
        out["semanas_recientes"] = 0
    out["comportamiento_reciente"] = out["comportamiento_reciente"].fillna(0)
    out["semanas_recientes"] = out["semanas_recientes"].fillna(0)
    out["confianza"] = np.select(
        [
            out["veces_aparece_en_misma_semana"].ge(3) & out["cv_semana"].le(0.45),
            out["veces_aparece_en_misma_semana"].ge(2) & out["cv_semana"].le(0.8),
            out["veces_aparece_en_misma_semana"].ge(1),
        ],
        ["ALTA", "MEDIA", "BAJA"],
        default="SIN_HISTORIA",
    )
    out["clasificacion_semana"] = np.select(
        [
            out["veces_aparece_en_misma_semana"].lt(1),
            out["veces_aparece_en_misma_semana"].eq(1),
            out["cv_semana"].le(0.45),
            out["cv_semana"].gt(1.2),
        ],
        ["SEMANA_SIN_HISTORIA", "SEMANA_SIN_PATRON", "SEMANA_ESTABLE", "SEMANA_PICO"],
        default="SEMANA_VARIABLE",
    )
    out = out.rename(columns={"semana_iso": "semana", "tallos_x_ramo": "tallos_por_ramo"})
    preferred = [
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
    cols = [col for col in preferred if col in out.columns]
    return out[cols].sort_values(
        ["cod_cliente", "semana", "tallos_mediana_historica_semana"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def _analysis_key_series(df: pd.DataFrame) -> pd.Series:
    if "sku_operativo" in df.columns:
        return df["sku_operativo"].astype(str)
    tipo = df["tipo_pedido_operativo"].astype(str).str.upper()
    return pd.Series(
        np.select(
            [
                tipo.eq("SOLIDO"),
                tipo.isin(["SURTIDO", "SURTIDO_M", "RAINBOW", "COMBO", "BOUQUET", "BQT"]),
                tipo.eq("BULK"),
            ],
            [
                df.get("producto_color", df.get("sku_terminado", pd.Series("sin_info", index=df.index))).astype(str),
                df.get("receta_programa_tamano_key", df.get("receta_programa_key", df.get("sku_composicion", df.get("receta_estructura_key", pd.Series("sin_info", index=df.index))))).astype(str),
                df.get("producto_color", pd.Series("sin_info", index=df.index)).astype(str),
            ],
            default=df.get("llave_analisis_operativo", pd.Series("sin_info", index=df.index)).astype(str),
        ),
        index=df.index,
    )


def build_operational_sku_summary(df: pd.DataFrame, recent_weeks: int = 12) -> pd.DataFrame:
    """Summarize the repeatable operational SKU used by Cliente 360 and forecast.

    SOLIDO is grouped by producto+color, with variedad kept as detail only.
    Mixed/recipe formats use sku_operativo so color lines are components of a
    repeated structure instead of independent SKUs.
    """
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["sku_operativo"] = _analysis_key_series(work)
    max_date = work["fecha"].max()
    recent = work[work["fecha"] >= max_date - pd.Timedelta(weeks=recent_weeks)].copy()
    if recent.empty:
        recent = work.copy()

    keys = CLIENT_KEYS + ["sku_operativo", "tipo_pedido_operativo"]
    keys = [col for col in keys if col in recent.columns]
    active_weeks = recent.groupby(CLIENT_KEYS, as_index=False)["anio_semana"].nunique().rename(columns={"anio_semana": "semanas_activas_cliente_ventana"})
    base = recent.groupby(keys, dropna=False, as_index=False).agg(
        tallos_ventana=("tallos_analisis", "sum"),
        tallos_confirmados_ventana=("tallos_confirmados", "sum"),
        ventas_usd_ventana=("ventas_usd", "sum") if "ventas_usd" in recent.columns else ("tallos_analisis", "size"),
        frecuencia_en_ventana=("anio_semana", "nunique"),
        pedidos_en_ventana=("pedido", "nunique") if "pedido" in recent.columns else ("sku_operativo", "size"),
        instancias_en_ventana=("instancia_pedido_operativo", "nunique") if "instancia_pedido_operativo" in recent.columns else ("sku_operativo", "size"),
        producto=("producto", lambda s: _top_join(s, 4)) if "producto" in recent.columns else ("sku_operativo", "size"),
        tallos_x_ramo=("tallos_x_ramo", lambda s: _top_join(s, 8)) if "tallos_x_ramo" in recent.columns else ("sku_operativo", "size"),
        subtipo_pedido_operativo=("subtipo_pedido_operativo", lambda s: _top_join(s, 3)) if "subtipo_pedido_operativo" in recent.columns else ("sku_operativo", "size"),
        tipo_caja=("tipo_caja", lambda s: _top_join(s, 3)) if "tipo_caja" in recent.columns else ("sku_operativo", "size"),
        capuchon=("capuchon", lambda s: _top_join(s, 3)) if "capuchon" in recent.columns else ("sku_operativo", "size"),
        comida=("comida", lambda s: _top_join(s, 3)) if "comida" in recent.columns else ("sku_operativo", "size"),
        empaque=("empaque", lambda s: _top_join(s, 3)) if "empaque" in recent.columns else ("sku_operativo", "size"),
        receta=("receta", lambda s: _top_join(s, 3)) if "receta" in recent.columns else ("sku_operativo", "size"),
        caja_operativa=("caja_operativa", lambda s: _top_join(s, 5)) if "caja_operativa" in recent.columns else ("sku_operativo", "size"),
        codempaque=("codempaque", lambda s: _top_join(s, 5)) if "codempaque" in recent.columns else ("sku_operativo", "size"),
        bulkbouquet=("bulkbouquet", lambda s: _top_join(s, 5)) if "bulkbouquet" in recent.columns else ("sku_operativo", "size"),
        tallos_programa_caja=("tallos_programa_caja", "median") if "tallos_programa_caja" in recent.columns else ("sku_operativo", "size"),
        tallos_componentes_caja=("tallos_componentes_caja", "median") if "tallos_componentes_caja" in recent.columns else ("sku_operativo", "size"),
        ramos_programa_caja_inferidos=("ramos_programa_caja_inferidos", "median") if "ramos_programa_caja_inferidos" in recent.columns else ("sku_operativo", "size"),
        tallos_programa_ramo=("tallos_programa_ramo", "median") if "tallos_programa_ramo" in recent.columns else ("sku_operativo", "size"),
        ramos_x_caja=("ramos_x_caja", lambda s: _top_join(s, 5)) if "ramos_x_caja" in recent.columns else ("sku_operativo", "size"),
        fulles=("fulles", lambda s: _top_join(s, 5)) if "fulles" in recent.columns else ("sku_operativo", "size"),
        piezas=("piezas", lambda s: _top_join(s, 5)) if "piezas" in recent.columns else ("sku_operativo", "size"),
    )
    base = base.merge(active_weeks, on=CLIENT_KEYS, how="left")
    base["tallos_promedio_semana_normal"] = base["tallos_ventana"] / base["semanas_activas_cliente_ventana"].replace(0, np.nan)
    totals = base.groupby(CLIENT_KEYS, as_index=False)["tallos_promedio_semana_normal"].sum().rename(columns={"tallos_promedio_semana_normal": "tallos_promedio_cliente"})
    base = base.merge(totals, on=CLIENT_KEYS, how="left")
    base["porcentaje_semana_normal"] = (base["tallos_promedio_semana_normal"] / base["tallos_promedio_cliente"].replace(0, np.nan)).fillna(0)
    base["cumplimiento"] = (base["tallos_confirmados_ventana"] / base["tallos_ventana"].replace(0, np.nan)).fillna(0).clip(0, 1)
    tipo = base["tipo_pedido_operativo"].astype(str).str.upper()
    base["lectura_operativa"] = np.select(
        [
            tipo.eq("SOLIDO"),
            tipo.isin(["SURTIDO", "SURTIDO_M"]),
            tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]),
            tipo.eq("BULK"),
        ],
        ["SKU_TERMINADO_EXACTO", "SKU_MEZCLA_COLOR", "SKU_RECETA_COMPOSICION", "SKU_PRODUCTO_COLOR_BULK"],
        default="REVISION_MANUAL",
    )
    base["vigencia_sku"] = np.select(
        [
            base["frecuencia_en_ventana"].ge(3),
            base["frecuencia_en_ventana"].ge(2),
            base["frecuencia_en_ventana"].eq(1),
        ],
        ["VIGENTE_RECURRENTE", "VIGENTE_INTERMITENTE", "VIGENTE_OCASIONAL"],
        default="SIN_VIGENCIA",
    )
    base["recomendacion"] = np.select(
        [
            tipo.eq("SOLIDO") & base["frecuencia_en_ventana"].ge(3) & base["cumplimiento"].ge(0.9),
            tipo.eq("SOLIDO") & base["frecuencia_en_ventana"].ge(2),
            tipo.isin(["SURTIDO", "SURTIDO_M"]) & base["frecuencia_en_ventana"].ge(2),
            tipo.isin(["RAINBOW", "COMBO", "BOUQUET", "BQT"]) & base["frecuencia_en_ventana"].ge(2),
            tipo.eq("BULK") & base["frecuencia_en_ventana"].ge(2),
        ],
        ["COMPRAR_TERMINADO", "PILOTO", "COMPRAR_COLOR_BASE", "REVISAR_COMPOSICION", "COMPRAR_COLOR_BASE"],
        default="NO_ANTICIPAR",
    )
    base = base.rename(columns={"tallos_x_ramo": "tallos_por_ramo"})
    preferred = [
        "cod_cliente", "cliente", "sku_operativo", "lectura_operativa", "tipo_pedido_operativo", "subtipo_pedido_operativo",
        "producto", "empaque", "tipo_caja", "tallos_por_ramo", "tallos_programa_caja", "tallos_componentes_caja",
        "ramos_programa_caja_inferidos", "tallos_programa_ramo", "ramos_x_caja", "fulles", "piezas", "capuchon", "comida", "receta", "caja_operativa", "codempaque", "bulkbouquet",
        "tallos_promedio_semana_normal", "porcentaje_semana_normal", "frecuencia_en_ventana", "pedidos_en_ventana", "instancias_en_ventana",
        "cumplimiento", "vigencia_sku", "recomendacion", "tallos_ventana", "ventas_usd_ventana",
    ]
    cols = [col for col in preferred if col in base.columns]
    return base[cols].sort_values(["cod_cliente", "tallos_promedio_semana_normal", "frecuencia_en_ventana"], ascending=[True, False, False]).reset_index(drop=True)


def build_operational_sku_composition(df: pd.DataFrame, recent_weeks: int = 12) -> pd.DataFrame:
    """Describe the internal composition of each operational SKU."""
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["sku_operativo"] = _analysis_key_series(work)
    max_date = work["fecha"].max()
    recent = work[work["fecha"] >= max_date - pd.Timedelta(weeks=recent_weeks)].copy()
    if recent.empty:
        recent = work.copy()
    keys = CLIENT_KEYS + ["sku_operativo", "tipo_pedido_operativo", "producto", "color", "variedad", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque"]
    keys = [col for col in keys if col in recent.columns]
    active = recent.groupby(CLIENT_KEYS + ["sku_operativo"], as_index=False)["anio_semana"].nunique().rename(columns={"anio_semana": "semanas_sku"})
    out = recent.groupby(keys, dropna=False, as_index=False).agg(
        tallos=("tallos_analisis", "sum"),
        ramos=("ramos_pedidos", "sum") if "ramos_pedidos" in recent.columns else ("tallos_analisis", "size"),
        semanas=("anio_semana", "nunique"),
    )
    out = out.merge(active, on=CLIENT_KEYS + ["sku_operativo"], how="left")
    totals = out.groupby(CLIENT_KEYS + ["sku_operativo"], as_index=False)["tallos"].sum().rename(columns={"tallos": "tallos_sku"})
    out = out.merge(totals, on=CLIENT_KEYS + ["sku_operativo"], how="left")
    out["porcentaje_composicion"] = (out["tallos"] / out["tallos_sku"].replace(0, np.nan)).fillna(0)
    out["tallos_promedio_semana_normal"] = out["tallos"] / out["semanas_sku"].replace(0, np.nan)
    out["ramos_promedio_semana_normal"] = out["ramos"] / out["semanas_sku"].replace(0, np.nan)

    weekly_color = recent.groupby(CLIENT_KEYS + ["sku_operativo", "anio_semana", "color"], dropna=False, as_index=False)["tallos_analisis"].sum()
    weekly_total = weekly_color.groupby(CLIENT_KEYS + ["sku_operativo", "anio_semana"], as_index=False)["tallos_analisis"].sum().rename(columns={"tallos_analisis": "total_semana_sku"})
    weekly_color = weekly_color.merge(weekly_total, on=CLIENT_KEYS + ["sku_operativo", "anio_semana"], how="left")
    weekly_color["share_color_semana"] = weekly_color["tallos_analisis"] / weekly_color["total_semana_sku"].replace(0, np.nan)
    stability = weekly_color.groupby(CLIENT_KEYS + ["sku_operativo", "color"], dropna=False, as_index=False)["share_color_semana"].std().rename(columns={"share_color_semana": "std_share_color"})
    out = out.merge(stability, on=CLIENT_KEYS + ["sku_operativo", "color"], how="left")
    out["estabilidad_composicion"] = np.select(
        [
            out["std_share_color"].fillna(0).le(0.08),
            out["std_share_color"].fillna(0).le(0.18),
        ],
        ["ESTABLE", "MEDIA"],
        default="VARIABLE",
    )
    out = out.rename(columns={"tallos_x_ramo": "tallos_por_ramo"})
    preferred = [
        "cod_cliente", "cliente", "sku_operativo", "tipo_pedido_operativo", "producto", "color", "variedad",
        "porcentaje_composicion", "tallos_promedio_semana_normal", "ramos_promedio_semana_normal",
        "tipo_caja", "tallos_por_ramo", "capuchon", "comida", "empaque", "semanas", "estabilidad_composicion", "std_share_color",
    ]
    cols = [col for col in preferred if col in out.columns]
    return out[cols].sort_values(["cod_cliente", "sku_operativo", "tallos_promedio_semana_normal"], ascending=[True, True, False]).reset_index(drop=True)


MIXED_STRUCTURE_TYPES = ["SURTIDO", "SURTIDO_M", "RAINBOW", "BQT", "COMBO", "BOUQUET"]


def _top_join(series: pd.Series, n: int = 8) -> str:
    values = pd.Series(series).dropna().astype(str)
    values = values[~values.isin(["sin_info", "nan", "none", ""])]
    return ", ".join(values.value_counts().head(n).index)


def _unique_join(series: pd.Series, n: int = 8) -> str:
    """Formats distinct component labels without ranking repeated history."""
    values = pd.Series(series).dropna().astype(str)
    values = values[~values.isin(["sin_info", "nan", "none", ""])]
    return ", ".join(values.drop_duplicates().head(n).tolist())


def _grouped_unique_labels(frame: pd.DataFrame, keys: list[str], col: str, output_col: str, n: int) -> pd.DataFrame:
    """Build compact display labels after vectorized deduplication."""
    if col not in frame.columns:
        return frame[keys].drop_duplicates().assign(**{output_col: ""})
    values = frame[keys + [col]].dropna(subset=[col]).copy()
    values[col] = values[col].astype(str)
    values = values[~values[col].isin(["sin_info", "nan", "none", ""])].drop_duplicates(keys + [col])
    if values.empty:
        return frame[keys].drop_duplicates().assign(**{output_col: ""})
    values = values[values.groupby(keys, dropna=False).cumcount().lt(n)]
    return (
        values.groupby(keys, dropna=False, as_index=False)[col]
        .agg(", ".join)
        .rename(columns={col: output_col})
    )


def _component_signature(group: pd.DataFrame) -> str:
    total = group["tallos_analisis"].sum()
    tmp = group.groupby(["producto", "variedad", "color", "grado"], dropna=False, as_index=False)["tallos_analisis"].sum()
    tmp["share"] = np.where(total > 0, tmp["tallos_analisis"] / total, 0)
    pieces = []
    for row in tmp.sort_values(["producto", "variedad", "color", "grado"]).itertuples(index=False):
        pieces.append(f"{row.producto}|{row.variedad}|{row.color}|{row.grado}|{row.share:.3f}")
    return " / ".join(pieces)


def _component_signatures_fast(mixed: pd.DataFrame) -> pd.DataFrame:
    if mixed.empty:
        return pd.DataFrame(columns=["estructura_caja_id", "composicion_firma", "composicion_version_id"])
    component_keys = ["estructura_caja_id", "producto", "variedad", "color", "grado"]
    tmp = (
        mixed.groupby(component_keys, dropna=False, as_index=False)["tallos_analisis"]
        .sum()
        .rename(columns={"tallos_analisis": "tallos_componente"})
    )
    totals = (
        tmp.groupby("estructura_caja_id", as_index=False)["tallos_componente"]
        .sum()
        .rename(columns={"tallos_componente": "tallos_estructura"})
    )
    tmp = tmp.merge(totals, on="estructura_caja_id", how="left")
    tmp["share"] = (tmp["tallos_componente"] / tmp["tallos_estructura"].replace(0, np.nan)).fillna(0).round(3)
    tmp = tmp.sort_values(component_keys)
    tmp["firma_parte"] = (
        tmp["producto"].astype(str) + "|" +
        tmp["variedad"].astype(str) + "|" +
        tmp["color"].astype(str) + "|" +
        tmp["grado"].astype(str) + "|" +
        tmp["share"].map(lambda value: f"{value:.3f}")
    )
    firmas = tmp.groupby("estructura_caja_id", as_index=False)["firma_parte"].agg(" / ".join)
    firmas = firmas.rename(columns={"firma_parte": "composicion_firma"})
    firmas["composicion_version_id"] = firmas["composicion_firma"].map(
        lambda value: hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:12]
    )
    return firmas


def build_operational_structure_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Resume recurring order structures for the dashboard.

    The dashboard needs the regular structure ordered by a client, not every
    historical line that produced it.  Each output row therefore represents a
    client/week/structure version and carries the number of original observed
    structures.  This retains weekly filters, volume and recurrence while
    avoiding line-level files that become impractical on a full history.

    SOLIDO lines behave as finished SKUs. Mixed formats such as SURTIDO,
    RAINBOW, BQT and COMBO retain their own visible type but share the
    composition/recipe treatment.
    """
    if df.empty:
        empty = pd.DataFrame()
        return {
            "estructura_caja": empty,
            "estructura_componentes": empty,
            "catalogo_estructura_version": empty,
        }

    work = df.copy()
    work["sku_operativo"] = _analysis_key_series(work)
    work["tipo_pedido_operativo"] = work["tipo_pedido_operativo"].astype(str).str.upper()
    work["es_estructura_mixta"] = work["tipo_pedido_operativo"].isin(MIXED_STRUCTURE_TYPES)
    for col in ["caja_operativa", "pedido", "sku_composicion", "sku_terminado", "producto_color"]:
        if col not in work.columns:
            work[col] = "sin_info"

    work["fecha"] = pd.to_datetime(work["fecha"], errors="coerce")
    date_key = work["fecha"].dt.strftime("%Y-%m-%d").fillna("sin_fecha")
    if "anio_semana" not in work.columns:
        iso = work["fecha"].dt.isocalendar()
        work["anio_semana"] = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    mixed_id = (
        work["cod_cliente"].astype(str) + "|" + date_key + "|" + work["pedido"].astype(str)
        + "|" + work["caja_operativa"].astype(str) + "|" + work["sku_composicion"].astype(str)
    )
    solid_id = (
        work["cod_cliente"].astype(str) + "|" + date_key + "|" + work["pedido"].astype(str)
        + "|" + work["sku_terminado"].astype(str)
    )
    work["estructura_caja_id"] = np.where(work["es_estructura_mixta"], mixed_id, solid_id)

    signature_cols = [
        col for col in ["estructura_caja_id", "producto", "variedad", "color", "grado", "tallos_analisis"]
        if col in work.columns
    ]
    mixed = work.loc[work["es_estructura_mixta"], signature_cols].copy()
    firmas = _component_signatures_fast(mixed)

    # Only carry the compact version key over line-level history. The full
    # signature can be long and belongs in summarized catalog outputs.
    work = work.merge(firmas[["estructura_caja_id", "composicion_version_id"]], on="estructura_caja_id", how="left")
    work["composicion_version_id"] = work["composicion_version_id"].fillna(work["sku_terminado"])

    work["tallos_analisis"] = pd.to_numeric(work["tallos_analisis"], errors="coerce").fillna(0)
    work["tallos_x_ramo_num"] = pd.to_numeric(work["tallos_x_ramo"], errors="coerce").replace(0, np.nan)
    work["ramos_estimados_linea"] = (work["tallos_analisis"] / work["tallos_x_ramo_num"]).fillna(0)
    if "ramos_pedidos" not in work.columns:
        work["ramos_pedidos"] = 0
    work["ramos_pedidos"] = pd.to_numeric(work["ramos_pedidos"], errors="coerce").fillna(0)

    # Aggregate first at observed structure/component level. Repeated raw
    # lines no longer become repeated rows in the dashboard output.
    component_dimensions = [
        "estructura_caja_id", "composicion_version_id",
        "fecha", "anio_semana", "cod_cliente", "cliente", "pedido",
        "tipo_pedido_operativo", "sku_operativo", "sku_composicion",
        "caja_operativa", "tipo_caja", "producto", "variedad", "color",
        "grado", "tallos_x_ramo",
    ]
    component_dimensions = [col for col in component_dimensions if col in work.columns]
    event_components = (
        work.groupby(component_dimensions, dropna=False, as_index=False)
        .agg(
            tallos_analisis=("tallos_analisis", "sum"),
            ramos_pedidos=("ramos_pedidos", "sum"),
            ramos_estimados_linea=("ramos_estimados_linea", "sum"),
        )
    )
    event_totals = (
        event_components.groupby("estructura_caja_id", as_index=False)["tallos_analisis"]
        .sum()
        .rename(columns={"tallos_analisis": "tallos_evento"})
    )
    event_components = event_components.merge(event_totals, on="estructura_caja_id", how="left")
    event_components["participacion_tallos_estructura"] = (
        event_components["tallos_analisis"] / event_components["tallos_evento"].replace(0, np.nan)
    ).fillna(0)

    version_keys = ["cod_cliente", "cliente", "anio_semana", "tipo_pedido_operativo", "sku_operativo", "composicion_version_id"]
    component_keys = version_keys + [
        col for col in ["producto", "variedad", "color", "grado", "tallos_x_ramo"] if col in event_components.columns
    ]
    estructura_componentes = (
        event_components.groupby(component_keys, dropna=False, as_index=False)
        .agg(
            fecha=("fecha", "min"),
            tallos_analisis=("tallos_analisis", "sum"),
            ramos_pedidos=("ramos_pedidos", "sum"),
            ramos_estimados_linea=("ramos_estimados_linea", "sum"),
            estructuras_componente=("estructura_caja_id", "nunique"),
        )
    )
    estructura_componentes["estructura_caja_id"] = (
        estructura_componentes["cod_cliente"].astype(str) + "|"
        + estructura_componentes["anio_semana"].astype(str) + "|"
        + estructura_componentes["sku_operativo"].astype(str) + "|"
        + estructura_componentes["composicion_version_id"].astype(str)
    )
    component_total = (
        estructura_componentes.groupby("estructura_caja_id", as_index=False)["tallos_analisis"]
        .sum()
        .rename(columns={"tallos_analisis": "tallos_estructura"})
    )
    estructura_componentes = estructura_componentes.merge(component_total, on="estructura_caja_id", how="left")
    estructura_componentes["participacion_tallos_estructura"] = (
        estructura_componentes["tallos_analisis"] / estructura_componentes["tallos_estructura"].replace(0, np.nan)
    ).fillna(0)
    estructura_componentes = estructura_componentes.sort_values(
        ["cod_cliente", "fecha", "estructura_caja_id", "participacion_tallos_estructura"],
        ascending=[True, True, True, False],
    ).reset_index(drop=True)

    event_header_cols = [
        "estructura_caja_id", "composicion_version_id",
        "fecha", "anio_semana", "cod_cliente", "cliente", "pedido",
        "tipo_pedido_operativo", "sku_operativo", "sku_composicion",
        "caja_operativa", "tipo_caja", "capuchon", "comida", "empaque", "receta",
    ]
    event_header_cols = [col for col in event_header_cols if col in work.columns]
    event_meta = work[event_header_cols].drop_duplicates("estructura_caja_id")
    event_amounts = (
        work.groupby("estructura_caja_id", as_index=False)
        .agg(
            tallos_estructura=("tallos_analisis", "sum"),
            ramos_componentes=("ramos_pedidos", "sum"),
            ramos_estimados=("ramos_estimados_linea", "sum"),
        )
    )
    event_headers = event_meta.merge(event_amounts, on="estructura_caja_id", how="left")
    header_group_keys = [
        col for col in [
            "cod_cliente", "cliente", "anio_semana", "tipo_pedido_operativo",
            "sku_operativo", "composicion_version_id",
            "sku_composicion", "caja_operativa", "tipo_caja", "capuchon",
            "comida", "empaque", "receta",
        ] if col in event_headers.columns
    ]
    estructura_caja = (
        event_headers.groupby(header_group_keys, dropna=False, as_index=False)
        .agg(
            fecha=("fecha", "min"),
            repeticiones_estructura=("estructura_caja_id", "nunique"),
            tallos_estructura=("tallos_estructura", "sum"),
            ramos_componentes=("ramos_componentes", "sum"),
            ramos_estimados=("ramos_estimados", "sum"),
        )
    )
    estructura_caja["estructura_caja_id"] = (
        estructura_caja["cod_cliente"].astype(str) + "|"
        + estructura_caja["anio_semana"].astype(str) + "|"
        + estructura_caja["sku_operativo"].astype(str) + "|"
        + estructura_caja["composicion_version_id"].astype(str)
    )

    # Component labels are calculated once per visible structure version, not
    # once for every historical order occurrence.
    label_keys = ["tipo_pedido_operativo", "sku_operativo", "composicion_version_id"]
    labels = (
        estructura_componentes.groupby(label_keys, dropna=False, as_index=False)["color"]
        .nunique()
        .rename(columns={"color": "lineas_componentes"})
    )
    for source_col, output_col, limit in [
        ("producto", "productos", 6),
        ("color", "colores", 10),
        ("variedad", "variedades", 10),
        ("tallos_x_ramo", "tallos_x_ramo_lista", 6),
    ]:
        labels = labels.merge(
            _grouped_unique_labels(estructura_componentes, label_keys, source_col, output_col, limit),
            on=label_keys,
            how="left",
        )
    estructura_caja = (
        estructura_caja.merge(labels, on=label_keys, how="left")
        .sort_values(["cod_cliente", "fecha", "tallos_estructura"], ascending=[True, True, False])
        .reset_index(drop=True)
    )
    firma_lookup = firmas[["composicion_version_id", "composicion_firma"]].drop_duplicates()
    estructura_caja = estructura_caja.merge(firma_lookup, on="composicion_version_id", how="left")
    estructura_caja["composicion_firma"] = estructura_caja["composicion_firma"].fillna(estructura_caja["sku_operativo"])

    catalog_keys = ["cod_cliente", "cliente", "tipo_pedido_operativo", "sku_operativo", "composicion_version_id", "composicion_firma"]
    catalogo_estructura_version = (
        estructura_caja.groupby(catalog_keys, dropna=False, as_index=False)
        .agg(
            veces_observada=("repeticiones_estructura", "sum"),
            semanas_observada=("anio_semana", "nunique"),
            primera_fecha=("fecha", "min"),
            ultima_fecha=("fecha", "max"),
            tallos_totales=("tallos_estructura", "sum"),
            ramos_totales=("ramos_estimados", "sum"),
        )
    )
    catalogo_estructura_version["tallos_promedio_estructura"] = (
        catalogo_estructura_version["tallos_totales"]
        / catalogo_estructura_version["veces_observada"].replace(0, np.nan)
    ).fillna(0)
    catalogo_estructura_version["ramos_promedio_estimados"] = (
        catalogo_estructura_version["ramos_totales"]
        / catalogo_estructura_version["veces_observada"].replace(0, np.nan)
    ).fillna(0)
    catalogo_estructura_version = (
        catalogo_estructura_version.drop(columns=["tallos_totales", "ramos_totales"])
        .sort_values(["cod_cliente", "veces_observada", "tallos_promedio_estructura"], ascending=[True, False, False])
        .reset_index(drop=True)
    )

    return {
        "estructura_caja": estructura_caja,
        "estructura_componentes": estructura_componentes,
        "catalogo_estructura_version": catalogo_estructura_version,
    }


def build_client_week_operational_sku(df: pd.DataFrame) -> pd.DataFrame:
    """Week-by-week operational SKU table for Cliente 360."""
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["sku_operativo"] = _analysis_key_series(work)
    keys = CLIENT_KEYS + ["anio", "semana_iso", "anio_semana", "sku_operativo", "tipo_pedido_operativo"]
    keys = [col for col in keys if col in work.columns]
    out = work.groupby(keys, dropna=False, as_index=False).agg(
        tallos_pedidos=("tallos_analisis", "sum"),
        tallos_confirmados=("tallos_confirmados", "sum"),
        ventas_usd=("ventas_usd", "sum") if "ventas_usd" in work.columns else ("tallos_analisis", "size"),
        productos=("producto", lambda s: ", ".join(pd.Series(s).dropna().astype(str).value_counts().head(4).index)),
        colores=("color", lambda s: ", ".join(pd.Series(s).dropna().astype(str).value_counts().head(6).index)),
        variedades=("variedad", lambda s: ", ".join(pd.Series(s).dropna().astype(str).value_counts().head(6).index)),
        lineas=("sku_operativo", "size"),
        pedidos=("pedido", "nunique") if "pedido" in work.columns else ("sku_operativo", "size"),
    )
    out["cumplimiento"] = (out["tallos_confirmados"] / out["tallos_pedidos"].replace(0, np.nan)).fillna(0).clip(0, 1)
    week_totals = out.groupby(CLIENT_KEYS + ["anio_semana"], as_index=False)["tallos_pedidos"].sum().rename(columns={"tallos_pedidos": "tallos_cliente_semana"})
    out = out.merge(week_totals, on=CLIENT_KEYS + ["anio_semana"], how="left")
    out["participacion_semana_cliente"] = (out["tallos_pedidos"] / out["tallos_cliente_semana"].replace(0, np.nan)).fillna(0)
    return out.sort_values(["cod_cliente", "anio", "semana_iso", "tallos_pedidos"], ascending=[True, True, True, False]).reset_index(drop=True)


def summarize_operational_demand(df: pd.DataFrame, fuente_demanda: str) -> pd.DataFrame:
    """Summarize pending/estimated/future demand by operational SKU."""
    if df.empty:
        return pd.DataFrame()
    keys = CLIENT_KEYS + [
        "fecha", "anio", "semana_iso", "anio_semana", "dia_semana_num",
        "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "receta",
        "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo",
        "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque", "estructura_pedido", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key",
    ]
    out = df.groupby(keys, as_index=False).agg(
        tallos=("tallos_analisis", "sum"),
        tallos_confirmados=("tallos_confirmados", "sum"),
        faltante_tallos=("faltante_tallos", "sum"),
        lineas=("sku_terminado", "size"),
        pedidos=("pedido", "nunique") if "pedido" in df.columns else ("sku_terminado", "size"),
    )
    out["fuente_demanda"] = fuente_demanda
    return out.sort_values(["fecha", "cod_cliente", "tallos"], ascending=[True, True, False]).reset_index(drop=True)
