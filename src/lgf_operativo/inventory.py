from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_inventory(inv: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if inv is None or inv.empty:
        return {}

    inv_fecha_item = inv.groupby(["fecha", "anio_semana", "producto", "variedad", "color", "grado"], as_index=False).agg(
        inventario_total=("inventario", "sum"),
        fincas=("cod_finca", "nunique"),
    )
    inv_fecha_item["faltante_proyectado"] = inv_fecha_item["inventario_total"].clip(upper=0).abs()
    inv_fecha_item["sobrante_proyectado"] = inv_fecha_item["inventario_total"].clip(lower=0)
    inv_fecha_item["estado_disponibilidad"] = np.select(
        [inv_fecha_item["inventario_total"] < 0, inv_fecha_item["inventario_total"] > 0],
        ["FALTANTE", "SOBRANTE"],
        default="NEUTRO",
    )

    inv_finca = inv.groupby(["fecha", "producto", "variedad", "color", "grado", "cod_finca"], as_index=False).agg(inventario=("inventario", "sum"))
    inv_finca["estado_disponibilidad"] = np.select([inv_finca["inventario"] < 0, inv_finca["inventario"] > 0], ["FALTANTE", "SOBRANTE"], default="NEUTRO")

    inv_semana = inv.groupby(["anio_semana", "producto", "variedad", "color", "grado"], as_index=False).agg(inventario_total_semana=("inventario", "sum"))
    inv_semana["faltante_proyectado_semana"] = inv_semana["inventario_total_semana"].clip(upper=0).abs()
    inv_semana["sobrante_proyectado_semana"] = inv_semana["inventario_total_semana"].clip(lower=0)

    inv_fecha_color = inv.groupby(["fecha", "anio_semana", "producto", "color", "grado"], as_index=False).agg(
        inventario_color_total=("inventario", "sum"),
        variedades=("variedad", "nunique"),
        fincas=("cod_finca", "nunique"),
    )
    inv_fecha_color["faltante_color_proyectado"] = inv_fecha_color["inventario_color_total"].clip(upper=0).abs()
    inv_fecha_color["sobrante_color_proyectado"] = inv_fecha_color["inventario_color_total"].clip(lower=0)
    inv_fecha_color["estado_disponibilidad_color"] = np.select(
        [inv_fecha_color["inventario_color_total"] < 0, inv_fecha_color["inventario_color_total"] > 0],
        ["FALTANTE_COLOR", "SOBRANTE_COLOR"],
        default="NEUTRO_COLOR",
    )

    return {
        "inventario_fecha_item": inv_fecha_item.sort_values(["fecha", "producto", "color", "variedad"]),
        "inventario_fecha_color": inv_fecha_color.sort_values(["fecha", "producto", "color", "grado"]),
        "inventario_fecha_finca": inv_finca.sort_values(["fecha", "producto", "color", "variedad", "cod_finca"]),
        "inventario_semana_item": inv_semana.sort_values(["anio_semana", "producto", "color", "variedad"]),
    }


def cross_forecast_inventory(forecast: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    """Cross future operational demand with projected availability.

    inventory_final is already a projected balance after internal farm crosses.
    Availability is read mainly by product/color/grade. Variety remains useful
    to decide what to buy when the color balance is short, especially for
    non-USA clients.
    """
    if forecast is None or forecast.empty or inv is None or inv.empty:
        return pd.DataFrame()

    inv_agg = inv.groupby(["fecha", "producto", "variedad", "color", "grado"], as_index=False).agg(
        inventario_variedad_total=("inventario", "sum"),
        fincas_disponibles=("cod_finca", "nunique"),
    ).rename(columns={"fecha": "fecha_forecast"})
    inv_color = inv.groupby(["fecha", "producto", "color", "grado"], as_index=False).agg(
        inventario_color_total=("inventario", "sum"),
        variedades_en_balance=("variedad", "nunique"),
    ).rename(columns={"fecha": "fecha_forecast"})

    out = forecast.merge(inv_agg, on=["fecha_forecast", "producto", "variedad", "color", "grado"], how="left")
    out = out.merge(inv_color, on=["fecha_forecast", "producto", "color", "grado"], how="left")
    out["inventario_variedad_total"] = out["inventario_variedad_total"].fillna(0)
    out["inventario_color_total"] = out["inventario_color_total"].fillna(0)
    out["inventario_total"] = out["inventario_color_total"]
    out["fincas_disponibles"] = out["fincas_disponibles"].fillna(0).astype(int)
    out["variedades_en_balance"] = out["variedades_en_balance"].fillna(0).astype(int)
    out["faltante_proyectado_item"] = out["inventario_color_total"].clip(upper=0).abs()
    out["sobrante_proyectado_item"] = out["inventario_color_total"].clip(lower=0)
    out["faltante_variedad_proyectado"] = out["inventario_variedad_total"].clip(upper=0).abs()
    out["sobrante_variedad_proyectado"] = out["inventario_variedad_total"].clip(lower=0)
    out["riesgo_disponibilidad"] = np.select(
        [out["inventario_color_total"] < 0, out["inventario_color_total"] == 0, out["inventario_color_total"] > 0],
        ["ALTO_FALTANTE_COLOR", "SIN_SOBRANTE_COLOR", "CON_SOBRANTE_COLOR"],
        default="SIN_DATO",
    )
    out["riesgo_variedad"] = np.select(
        [out["inventario_variedad_total"] < 0, out["inventario_variedad_total"] == 0, out["inventario_variedad_total"] > 0],
        ["FALTANTE_VARIEDAD", "SIN_SOBRANTE_VARIEDAD", "CON_SOBRANTE_VARIEDAD"],
        default="SIN_DATO_VARIEDAD",
    )

    # If the row comes from a real pending order, priority is naturally higher than a pure forecast.
    is_pending = (
        out["fuente_demanda"].eq("PENDIENTE_REAL_CLIENTE")
        if "fuente_demanda" in out.columns
        else pd.Series(False, index=out.index)
    )
    pais = out["pais"].fillna("").astype(str).str.upper() if "pais" in out.columns else pd.Series("", index=out.index)
    is_usa = pais.str.contains(r"\bUSA\b|UNITED STATES|ESTADOS UNIDOS|EEUU", regex=True, na=False)
    tipo = out["tipo_pedido_operativo"].fillna("").astype(str).str.upper() if "tipo_pedido_operativo" in out.columns else pd.Series("", index=out.index)
    is_easy_buy = tipo.isin(["SOLIDO", "SURTIDO", "SURTIDO_M"])
    is_rainbow = tipo.eq("RAINBOW")
    score = out["score_compra_terminada"].fillna(0)

    non_usa = out[~is_usa].copy()
    if non_usa.empty:
        out["share_variedad_demanda_no_usa"] = 0.0
        out["ranking_variedad_no_usa"] = np.nan
    else:
        demand_keys = ["producto", "color", "grado", "variedad"]
        variety_demand = non_usa.groupby(demand_keys, as_index=False)["tallos_estimados"].sum()
        totals = variety_demand.groupby(["producto", "color", "grado"], as_index=False)["tallos_estimados"].sum().rename(
            columns={"tallos_estimados": "tallos_color_no_usa"}
        )
        variety_demand = variety_demand.merge(totals, on=["producto", "color", "grado"], how="left")
        variety_demand["share_variedad_demanda_no_usa"] = (
            variety_demand["tallos_estimados"] / variety_demand["tallos_color_no_usa"].replace(0, np.nan)
        ).fillna(0)
        variety_demand["ranking_variedad_no_usa"] = variety_demand.groupby(["producto", "color", "grado"])["tallos_estimados"].rank(
            method="dense", ascending=False
        )
        out = out.merge(
            variety_demand[demand_keys + ["share_variedad_demanda_no_usa", "ranking_variedad_no_usa"]],
            on=demand_keys,
            how="left",
        )
        out["share_variedad_demanda_no_usa"] = out["share_variedad_demanda_no_usa"].fillna(0)

    out["tallos_prioridad_compra_cliente"] = np.where(
        (out["inventario_color_total"] < 0) & (~is_usa) & is_easy_buy,
        np.minimum(out["tallos_estimados"], out["faltante_proyectado_item"]),
        0,
    )
    out["prioridad_compra"] = np.select(
        [
            is_rainbow & (out["riesgo_disponibilidad"] == "ALTO_FALTANTE_COLOR"),
            is_usa & (out["riesgo_disponibilidad"] == "ALTO_FALTANTE_COLOR"),
            is_pending & (~is_usa) & is_easy_buy & (out["riesgo_disponibilidad"] == "ALTO_FALTANTE_COLOR"),
            (~is_usa) & is_easy_buy & (out["riesgo_disponibilidad"] == "ALTO_FALTANTE_COLOR") & (score >= 80),
            (~is_usa) & is_easy_buy & (out["riesgo_disponibilidad"] == "ALTO_FALTANTE_COLOR") & (score >= 65),
            (~is_usa) & is_easy_buy & (out["riesgo_disponibilidad"] == "ALTO_FALTANTE_COLOR"),
            (out["riesgo_disponibilidad"] == "SIN_SOBRANTE_COLOR") & is_pending,
            (out["riesgo_disponibilidad"] == "SIN_SOBRANTE_COLOR") & (score >= 65),
        ],
        [
            "RAINBOW_NO_COMPRAR_ARMAR_CON_REGLA_GENERAL",
            "USA_VALIDAR_ANTES_DE_COMPRAR",
            "ORDEN_REAL_NO_USA_COMPRAR_SOLIDO_SURTIDO_PRIORIDAD_ALTA",
            "NO_USA_COMPRAR_VARIEDAD_TOP_PRIORIDAD_ALTA",
            "NO_USA_PILOTO_COMPRA_VARIEDAD_TOP",
            "NO_USA_COMPRAR_COLOR_BASE_VALIDAR_VARIEDAD",
            "ORDEN_REAL_PENDIENTE_VIGILAR",
            "VIGILAR_DISPONIBILIDAD",
        ],
        default="SIN_PRIORIDAD_COMPRA",
    )
    out["lectura_inventario"] = "INVENTORY_FINAL_BALANCE_PROYECTADO_COLOR"
    out["criterio_compra_variedad"] = np.select(
        [
            is_rainbow,
            is_usa,
            out["ranking_variedad_no_usa"].eq(1),
            out["share_variedad_demanda_no_usa"].ge(0.25),
        ],
        [
            "no_comprar_rainbow_como_terminado",
            "usa_no_define_compra_variedad",
            "variedad_top_no_usa",
            "variedad_relevante_no_usa",
        ],
        default="variedad_secundaria_o_sin_demanda_no_usa",
    )
    return out.sort_values(["fecha_forecast", "prioridad_compra", "cod_cliente", "score_compra_terminada"], ascending=[True, True, True, False]).reset_index(drop=True)
