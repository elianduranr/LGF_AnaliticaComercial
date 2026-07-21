"""Reglas de limpieza y normalizacion de pedidos historicos LGF.

Este modulo traduce columnas crudas a nombres canonicos y aplica reglas
operativas compartidas por descriptivos y forecast.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = {
    "fecha": ["FECHA", "Fecha", "fecha"],
    "cod_cliente": ["CODCUSTOM", "CodCustom", "COD_CLIENTE", "cod_cliente", "codigo_cliente"],
    "cliente": ["CLIENTE", "Cliente", "cliente"],
    "NomCompania": ["NomCompania", "NOMCOMPANIA", "Compania", "COMPAÑIA", "COMPANIA", "compania"],
    "grupo": ["GRUPO", "Grupo", "grupo"],
    "subcliente": ["SUBCLIENTE", "Subcliente", "subcliente"],
    "tipo_venta": ["TIPOVENTA", "TipoVenta", "tipo_venta"],
    "tipo_orden_empaque": ["TIPORDENEMPAQUE", "TipoOrdenEmpaque", "tipo_orden_empaque"],
    "pedido": ["PEDIDO", "Pedido", "pedido"],
    "invoice": ["INVOICE", "Invoice", "invoice"],
    "tipo_empaque": ["TIPEMPAQUE", "TipoEmpaque", "tipo_empaque"],
    "empaque": ["EMPAQUE", "Empaque", "empaque"],
    "grado": ["GRADO", "TAMANO", "TAMAÑO", "Tamano", "Tamaño", "grado"],
    "caja_id": ["CajaId", "CAJAID", "IDCAJA", "caja_id"],
    "id_caja": ["IDCAJA", "IdCaja", "id_caja"],
    "codempaque": ["CODEMPAQUE", "CodEmpaque", "codempaque"],
    "bulkbouquet": ["BULKBOUQUET", "BulkBouquet", "bulkbouquet"],
    "color": ["NomColor", "COLOR", "Color", "color"],
    "variedad": ["NomVariedad", "VARIEDAD", "Variedad", "variedad"],
    "tipo_caja": ["TIPCAJA", "TIPOCAJA", "TipoCaja", "tipo_caja"],
    "tallos_total": ["TOTALTALLOS", "TotalTallos", "tallos_total"],
    "tallos_pedidos": ["TallosPedidos", "TALLOSPEDIDOS", "tallos_pedidos"],
    "tallos_confirmados": ["TallosConfirmados", "TALLOSCONFIRMADOS", "tallos_confirmados"],
    "producto": ["PRODUCTO", "Producto", "producto"],
    "pais": ["PAIS", "Pais", "país", "pais"],
    "ciudad": ["CIUDAD", "Ciudad", "ciudad"],
    "piezas": ["PIEZAS", "Piezas", "piezas"],
    "fulles": ["FULLES", "Fulles", "fulles"],
    "equivalencia": ["EQUIVALENCIA", "Equivalencia", "equivalencia"],
    "ramos_x_caja": ["RXCAJA", "RxCaja", "rxcaja", "ramos_x_caja"],
    "ramos_x_caja_detalle": ["RXCAJADETALLE", "RxCajaDetalle", "rxcajadetalle", "ramos_x_caja_detalle"],
    "flor_emp": ["FLOREMP", "FlorEmp", "flor_emp"],
    "tallos_x_ramo": ["TALLXRAM", "TXRAMO", "TallosXRamo", "tallos_x_ramo"],
    "ramos_pedidos": ["TOTRAMPED", "TotRamPed", "ramos_pedidos"],
    "ramos_confirmados": ["TOTRAMCONF", "TotRamConf", "ramos_confirmados"],
    "po": ["PO", "Po", "po"],
    "tipo_precio": ["TipoPrecio", "TIPOPRECIO", "tipo_precio"],
    "comida": ["Comida", "COMIDA", "comida"],
    "capuchon": ["Capuchon", "Capuchón", "CAPUCHON", "capuchon"],
    "mes": ["MES", "Mes", "mes"],
    "tipo_orden": ["TipoOrden", "TIPOORDEN", "tipo_orden"],
    "estado": ["ESTADO", "Estado", "estado"],
    "vendedor": ["VENDEDOR", "Vendedor", "vendedor"],
    "receta": ["RECETA", "Receta", "receta"],
    "pull_date": ["PullDate", "PULLDATE", "pull_date"],
    "serial": ["SERIAL", "Serial", "serial"],
    "finca": ["FINCA", "Finca", "finca"],
    "abrev_finca": ["ABREVIADOFINCA", "ABREVIADO_FINCA", "abrev_finca"],
    "semana": ["SEMANA", "Semana", "semana"],
    "ventas_usd": ["VENTAS_USD", "Ventas_USD", "ventas_usd"],
    "valor_unitario_original": ["VALORUNITARIO", "ValorUnitario", "valor_unitario_original"],
    "valor_total_original": ["VALORTOTAL", "ValorTotal", "valor_total_original"],
    "moneda_original": ["NomMoneda", "NOMMONEDA", "MONEDA", "moneda_original"],
    "cod_cliente_consolidado": ["CODCONSOL", "CodConsol", "cod_cliente_consolidado"],
    "cliente_consolidado": ["CLIENTECONSOL", "ClienteConsol", "cliente_consolidado"],
    "archivo_origen": ["ARCHIVO_ORIGEN", "ArchivoOrigen", "archivo_origen"],
}

INVENTORY_COLUMNS = {
    "producto": ["PRODUCTO", "Producto", "producto"],
    "color": ["COLOR", "Color", "color"],
    "variedad": ["VARIEDAD", "Variedad", "variedad"],
    "grado": ["GRADO", "Grado", "grado"],
    "inventario": ["INVENTARIO", "Inventario", "inventario"],
    "cod_finca": ["CODFINCA", "CodFinca", "cod_finca"],
    "fecha": ["FECHA", "Fecha", "fecha"],
    "semana": ["SEMANA", "Semana", "semana"],
}

ESTADO_CANONICO = {
    "confirmado": "confirmado",
    "pendiente": "pendiente",
    "en proceso": "en_proceso",
    "proceso": "en_proceso",
    "por verificar": "por_verificar",
    "reproceso": "reproceso",
}

ESTADO_CATEGORIA = {
    "confirmado": "historico_real_despachado",
    "pendiente": "orden_real_futura_cliente",
    "en_proceso": "estimado_comercial",
    "por_verificar": "cambio_sobre_confirmado",
    "reproceso": "cambio_sobre_confirmado",
    "otro": "otro_no_clasificado",
}

def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def fix_mojibake(value):
    """Fix common mojibake such as exportaciÃ³n -> exportación."""
    if not isinstance(value, str):
        return value
    if "Ã" in value or "Â" in value:
        try:
            return value.encode("latin1").decode("utf-8")
        except Exception:
            return value
    return value


def normalize_text(value) -> str:
    if pd.isna(value):
        return "sin_info"
    value = fix_mojibake(str(value))
    value = value.strip().lower()
    value = strip_accents(value)
    value = re.sub(r"\s+", " ", value)
    value = value.replace("nan", "sin_info") if value == "nan" else value
    return value or "sin_info"


def normalize_key(value) -> str:
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "sin_info"


def normalize_text_series(series: pd.Series) -> pd.Series:
    """Normalize repeated text values once, then map back to the full column."""
    unique = pd.Series(series.drop_duplicates())
    mapping = {value: normalize_text(value) for value in unique}
    return series.map(mapping).fillna("sin_info")


def normalize_key_series(series: pd.Series) -> pd.Series:
    unique = pd.Series(series.drop_duplicates())
    mapping = {value: normalize_key(value) for value in unique}
    return series.map(mapping).fillna("sin_info")


def combine_key_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series("sin_info", index=df.index)
    combined = df[columns[0]].astype(str)
    for col in columns[1:]:
        combined = combined.str.cat(df[col].astype(str), sep="|")
    return normalize_key_series(combined)


def rename_to_canonical(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    """Rename available source aliases without creating duplicate canonical columns.

    Complete historical extracts may retain both a canonical field and one of
    its legacy source aliases (for example ``tallos_x_ramo`` and ``TXRAMO``).
    In that case the canonical column is already the downstream contract and
    the legacy alias is preserved only as source detail.
    """
    rename = {}
    existing = set(df.columns)
    for canonical, options in mapping.items():
        if canonical in existing:
            continue
        for option in options:
            if option in existing:
                rename[option] = canonical
                break
    return df.rename(columns=rename).copy()


def ensure_columns(df: pd.DataFrame, columns: Iterable[str], default=np.nan) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = default
    return df


def to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False).str.replace(r"[^0-9\-.]", "", regex=True),
        errors="coerce",
    ).fillna(0)


def parse_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=False)
    if parsed.isna().mean() > 0.5:
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return parsed


def classify_estado(estado: pd.Series) -> pd.DataFrame:
    estado_norm = normalize_text_series(estado)
    estado_canonico = estado_norm.map(ESTADO_CANONICO).fillna("otro")
    estado_categoria = estado_canonico.map(ESTADO_CATEGORIA).fillna("otro_no_clasificado")
    return pd.DataFrame({
        "estado_original_norm": estado_norm,
        "estado_canonico": estado_canonico,
        "estado_categoria": estado_categoria,
        "es_historico_real": estado_canonico.eq("confirmado"),
        "es_orden_real_futura": estado_canonico.eq("pendiente"),
        "es_estimado_comercial": estado_canonico.eq("en_proceso"),
        "es_cambio_sobre_confirmado": estado_canonico.isin(["por_verificar", "reproceso"]),
    })



def classify_tipo_pedido_operativo(df: pd.DataFrame) -> pd.DataFrame:
    """Use source-system ``TIPEMPAQUE`` as the sole operational-type authority.

    The two solid variants are consolidated as ``SOLIDO``. Every other value
    is preserved as supplied by the system (apart from case/text cleanup).
    """
    if "tipo_empaque" in df.columns:
        raw = normalize_text_series(df["tipo_empaque"])
    else:
        raw = pd.Series("sin_info", index=df.index, dtype="object")

    tipo = raw.str.upper()
    tipo = tipo.where(~raw.isin(["solido por variedad", "solido por color"]), "SOLIDO")
    tipo = tipo.where(raw.ne("sin_info"), "TIPO_EMPAQUE_NO_INFORMADO")
    subtipo = normalize_key_series(raw)
    origen_tipologia = pd.Series("tipo_empaque_sistema", index=df.index, dtype="object")

    facilidad = pd.Series("REVISAR_OPERACION", index=df.index, dtype="object")
    facilidad[tipo.isin(["SOLIDO", 'SURTIDO "M"'])] = "FACIL_COMPRAR_TERMINADO"
    facilidad[tipo.eq("RAINBOW")] = "NO_COMPRAR_RAINBOW_ARMAR_INTERNO"
    facilidad[tipo.isin(["COMBO", "BULK", "BOUQUET", "BQT"])] = "VALIDAR_FORMATO_ANTES_COMPRAR"

    nivel_disponibilidad = pd.Series("COLOR", index=df.index, dtype="object")
    nivel_disponibilidad[tipo.eq("SOLIDO") & subtipo.eq("solido_por_variedad")] = "COLOR_VARIEDAD"
    nivel_disponibilidad[tipo.eq("RAINBOW")] = "REGLA_GENERAL_PEDIDO"

    enfoque_analisis = pd.Series("REVISION_OPERATIVA", index=df.index, dtype="object")
    enfoque_analisis[tipo.eq("SOLIDO")] = "SKU_SOLIDO_COLOR_CAJA"
    enfoque_analisis[tipo.eq('SURTIDO "M"')] = "ESTRUCTURA_MEZCLA_COLOR_COMPONENTE"
    enfoque_analisis[tipo.eq("RAINBOW")] = "RECETA_RAINBOW_COLOR_COMPONENTE"
    enfoque_analisis[tipo.eq("BQT")] = "RECETA_BQT_ESTRUCTURA"
    enfoque_analisis[tipo.eq("BOUQUET")] = "RECETA_BOUQUET_ESTRUCTURA"
    enfoque_analisis[tipo.eq("COMBO")] = "COMBO_ESTRUCTURA_CAJA"
    enfoque_analisis[tipo.eq("BULK")] = "BULK_ESTRUCTURA_PEDIDO"

    rol_color = pd.Series("COLOR_REFERENCIAL", index=df.index, dtype="object")
    rol_color[tipo.eq("SOLIDO")] = "COLOR_DEFINITORIO_SKU"
    rol_color[tipo.isin(['SURTIDO "M"', "RAINBOW", "BOUQUET", "BQT", "COMBO"])] = "COLOR_COMPONENTE_ESTRUCTURA"
    rol_color[tipo.eq("BULK")] = "COLOR_COMPONENTE_ESTRUCTURA"

    familia_analisis = pd.Series("OTROS_FORMATOS", index=df.index, dtype="object")
    familia_analisis[tipo.eq("SOLIDO")] = "SOLIDOS_COLOR_CAJA"
    familia_analisis[tipo.isin(['SURTIDO "M"', "RAINBOW", "BOUQUET", "BQT", "COMBO"])] = "ESTRUCTURAS_MIXTAS_RECETA"
    familia_analisis[tipo.eq("BULK")] = "ESTRUCTURAS_MIXTAS_RECETA"

    return pd.DataFrame({
        "tipo_pedido_operativo": tipo,
        "subtipo_pedido_operativo": subtipo,
        "origen_tipologia_operativa": origen_tipologia,
        "tipo_pedido_raw": raw,
        "facilidad_compra_terminado": facilidad,
        "nivel_disponibilidad_operativa": nivel_disponibilidad,
        "enfoque_analisis_operativo": enfoque_analisis,
        "rol_color_operativo": rol_color,
        "familia_analisis_operativa": familia_analisis,
        "es_pedido_solido": tipo.eq("SOLIDO"),
        "es_pedido_no_solido": ~tipo.eq("SOLIDO"),
        "es_rainbow": tipo.eq("RAINBOW"),
    })


def reconcile_tipo_pedido_operativo(df: pd.DataFrame) -> pd.DataFrame:
    """Correct stale labels exclusively from original ``tipo_empaque`` data.

    Result tables and dashboard caches can outlive a classifier change. This
    keeps their visible type aligned with the source-system field.
    """
    if df.empty or "tipo_pedido_operativo" not in df.columns:
        return df
    if "tipo_empaque" not in df.columns:
        return df

    classified = classify_tipo_pedido_operativo(df)
    blank = {"", "sin_info", "nan", "none", "0", "0.0"}
    values = df["tipo_empaque"].fillna("").astype(str).str.strip().str.lower()
    usable = ~values.isin(blank)
    if not usable.any():
        return df

    out = df.copy()
    for col in classified.columns:
        if col in out.columns:
            out.loc[usable, col] = classified.loc[usable, col]
    return out


def add_client_identifiers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cod_cliente"] = normalize_text_series(df["cod_cliente"])
    df["cliente"] = normalize_text_series(df["cliente"])
    # Si no hay código, usa nombre como fallback para no romper agrupaciones.
    df.loc[df["cod_cliente"].isin(["sin_info", "", "nan"]), "cod_cliente"] = df.loc[
        df["cod_cliente"].isin(["sin_info", "", "nan"]), "cliente"
    ]
    df["cliente_key"] = normalize_text_series(df["cod_cliente"].astype(str).str.cat(df["cliente"].astype(str), sep=" | "))
    return df


def clean_historical_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Clean orders extract from LGF.

    Business rules:
    - Official date = FECHA, dispatch date from Bogotá.
    - Official quantity = TallosPedidos; TallosConfirmados is used for fulfillment.
    - Analysis level = CLIENTE, but every output keeps CODCUSTOM/cod_cliente.
    - ESTADO is not mixed blindly:
        Confirmado = historical real dispatched order.
        Pendiente = real future order from client.
        En proceso = commercial estimate.
        Por verificar/Reproceso = changes over something already confirmed.
    """
    df = rename_to_canonical(df, CANONICAL_COLUMNS)
    required = [
        "fecha", "cod_cliente", "cliente", "NomCompania", "producto", "variedad", "color", "grado",
        "tipo_caja", "tallos_pedidos", "tallos_confirmados", "tallos_total", "tallos_x_ramo",
        "ramos_pedidos", "ramos_confirmados", "ramos_x_caja", "ramos_x_caja_detalle", "piezas", "fulles", "equivalencia",
        "tipo_empaque", "empaque", "capuchon", "comida", "pais", "ciudad",
        "tipo_orden", "tipo_orden_empaque", "receta", "estado", "finca", "semana", "vendedor", "subcliente",
        "caja_id", "id_caja", "codempaque", "bulkbouquet",
        "ventas_usd", "cod_cliente_consolidado", "cliente_consolidado", "archivo_origen",
        "valor_unitario_original", "valor_total_original", "moneda_original",
    ]
    df = ensure_columns(df, required)

    df["fecha"] = parse_date(df["fecha"])
    df = df[df["fecha"].notna()].copy()

    for col in ["tallos_pedidos", "tallos_confirmados", "tallos_total", "tallos_x_ramo", "ramos_pedidos", "ramos_confirmados", "ramos_x_caja", "ramos_x_caja_detalle", "piezas", "fulles", "equivalencia", "ventas_usd", "valor_unitario_original", "valor_total_original"]:
        if col in df.columns:
            df[col] = to_number(df[col])

    # Official quantity: TallosPedidos. Fallback only if missing/zero.
    df["tallos_analisis"] = df["tallos_pedidos"]
    mask_missing = df["tallos_analisis"].isna() | (df["tallos_analisis"] <= 0)
    df.loc[mask_missing, "tallos_analisis"] = df.loc[mask_missing, "tallos_total"]

    # Estado classification BEFORE normal text normalization overwrites semantic values.
    estado_info = classify_estado(df["estado"])
    for col in estado_info.columns:
        df[col] = estado_info[col].values

    text_cols = [
        "cliente", "NomCompania", "subcliente", "grupo", "producto", "variedad", "color", "grado",
        "tipo_caja", "tipo_empaque", "empaque", "capuchon", "comida", "pais", "ciudad", "tipo_orden",
        "tipo_orden_empaque", "receta", "estado", "finca", "abrev_finca", "vendedor", "tipo_venta",
        "caja_id", "id_caja", "codempaque", "bulkbouquet",
        "cod_cliente_consolidado", "cliente_consolidado", "archivo_origen",
        "moneda_original",
    ]
    df = add_client_identifiers(df)
    for col in text_cols:
        if col in df.columns:
            df[col] = normalize_text_series(df[col])
    if "NomCompania" in df.columns:
        missing_company = df["NomCompania"].isin(["sin_info", "", "nan", "none"])
        df.loc[missing_company, "NomCompania"] = df.loc[missing_company, "cliente"]

    # TIPEMPAQUE from the source system is the sole operational-type authority.
    tipo_pedido_info = classify_tipo_pedido_operativo(df)
    for col in tipo_pedido_info.columns:
        df[col] = tipo_pedido_info[col].values

    # Cumplimiento: solo tiene lectura fuerte en histórico confirmado/cambios ya confirmados.
    df["faltante_tallos"] = (df["tallos_analisis"] - df["tallos_confirmados"]).clip(lower=0)
    df["cumplimiento_linea"] = np.where(
        df["tallos_analisis"] > 0,
        df["tallos_confirmados"] / df["tallos_analisis"],
        np.nan,
    )

    iso = df["fecha"].dt.isocalendar()
    df["anio"] = iso.year.astype(int)
    df["semana_iso"] = iso.week.astype(int)
    df["anio_semana"] = df["anio"].astype(str) + "-W" + df["semana_iso"].astype(str).str.zfill(2)
    df["mes_num"] = df["fecha"].dt.month
    df["dia_semana_num"] = df["fecha"].dt.dayofweek + 1
    df["dia_semana"] = df["fecha"].dt.day_name(locale="C")

    df["tallos_componente_caja"] = (df["ramos_x_caja"] * df["tallos_x_ramo"]).replace([np.inf, -np.inf], np.nan)
    caja_factor = df["fulles"].where(df["fulles"].gt(0), df["piezas"])
    df["cajas_programa"] = caja_factor.where(caja_factor.gt(0), np.nan)

    # Operational SKUs.
    for col in ["tallos_x_ramo"]:
        df[col] = df[col].fillna(0).astype(float).round(6).astype(str).str.replace(r"\.0$", "", regex=True)

    components_full = ["tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque", "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "capuchon", "comida", "empaque"]
    components_flex = ["tipo_pedido_operativo", "producto", "color", "grado", "tipo_caja", "tallos_x_ramo"]
    df["sku_terminado"] = combine_key_columns(df, components_full)
    df["sku_flexible"] = combine_key_columns(df, components_flex)
    df["estructura_pedido"] = (
        df["tipo_pedido_operativo"].astype(str) + "|" +
        df["subtipo_pedido_operativo"].astype(str) + "|" +
        df["tipo_orden_empaque"].astype(str) + "|" +
        df["tipo_empaque"].astype(str)
    )
    df["estructura_pedido"] = normalize_key_series(df["estructura_pedido"])
    df["producto_color"] = combine_key_columns(df, ["producto", "color"])
    solid_tallos_ramo = df["tallos_x_ramo"].astype(str).str.strip()
    solid_sku_operativo = df["producto_color"].astype(str) + "|" + solid_tallos_ramo + "_tallos_ramo"
    solid_sku_operativo = solid_sku_operativo.where(~solid_tallos_ramo.isin(["", "0", "0.0", "nan", "None"]), df["producto_color"])
    solid_sku_operativo = normalize_key_series(solid_sku_operativo)
    df["producto_variedad_color"] = (
        df["producto"].astype(str) + "|" + df["variedad"].astype(str) + "|" + df["color"].astype(str)
    )
    df["producto_variedad_color"] = normalize_key_series(df["producto_variedad_color"])
    df["empaque_operativo"] = (
        df["tipo_pedido_operativo"].astype(str) + "|" +
        df["tipo_caja"].astype(str) + "|" + df["tallos_x_ramo"].astype(str) + "|" +
        df["capuchon"].astype(str) + "|" + df["comida"].astype(str) + "|" + df["empaque"].astype(str)
    )
    df["empaque_operativo"] = normalize_key_series(df["empaque_operativo"])
    caja_id_norm = normalize_key_series(df["caja_id"])
    id_caja_norm = normalize_key_series(df["id_caja"]) if "id_caja" in df.columns else pd.Series("sin_info", index=df.index)
    df["caja_operativa"] = caja_id_norm.where(~caja_id_norm.isin(["sin_info", "nan", "none", ""]), id_caja_norm)
    df["color_componente_key"] = (
        df["estructura_pedido"].astype(str) + "|" +
        df["producto"].astype(str) + "|" + df["color"].astype(str) + "|" +
        df["grado"].astype(str) + "|" + df["tipo_caja"].astype(str)
    )
    df["color_componente_key"] = normalize_key_series(df["color_componente_key"])
    df["receta_estructura_key"] = (
        df["tipo_pedido_operativo"].astype(str) + "|" +
        df["subtipo_pedido_operativo"].astype(str) + "|" +
        df["receta"].astype(str) + "|" +
        df["tipo_caja"].astype(str) + "|" +
        df["tallos_x_ramo"].astype(str) + "|" +
        df["capuchon"].astype(str) + "|" +
        df["comida"].astype(str) + "|" +
        df["empaque"].astype(str)
    )
    df["receta_estructura_key"] = normalize_key_series(df["receta_estructura_key"])
    df["receta_programa_key"] = (
        df["tipo_pedido_operativo"].astype(str) + "|" +
        df["subtipo_pedido_operativo"].astype(str) + "|" +
        df["receta"].astype(str) + "|" +
        df["tipo_caja"].astype(str) + "|" +
        df["capuchon"].astype(str) + "|" +
        df["comida"].astype(str) + "|" +
        df["empaque"].astype(str)
    )
    df["receta_programa_key"] = normalize_key_series(df["receta_programa_key"])
    recipe_group = [
        "cod_cliente", "fecha", "pedido", "tipo_pedido_operativo", "receta_programa_key", "caja_operativa",
    ]
    recipe_group = [col for col in recipe_group if col in df.columns]
    recipe_types = df["tipo_pedido_operativo"].isin(["RAINBOW", "BOUQUET", "BQT", "COMBO"])
    totals = df[recipe_types].groupby(recipe_group, dropna=False, as_index=False).agg(
        tallos_programa_total=("tallos_analisis", "sum"),
        cajas_programa_grupo=("cajas_programa", "max"),
        tallos_componentes_caja=("tallos_componente_caja", "sum"),
        ramos_programa_caja_detalle=("ramos_x_caja_detalle", "sum"),
        ramos_programa_caja=("ramos_x_caja", "sum"),
    )
    totals["tallos_programa_caja"] = (
        totals["tallos_programa_total"] / totals["cajas_programa_grupo"].replace(0, np.nan)
    )
    totals["tallos_programa_caja"] = totals["tallos_programa_caja"].fillna(totals["tallos_componentes_caja"])
    totals["ramos_programa_caja_inferidos"] = totals["ramos_programa_caja_detalle"].where(
        totals["ramos_programa_caja_detalle"].gt(0),
        totals["ramos_programa_caja"],
    )
    totals["tallos_programa_ramo"] = (
        totals["tallos_programa_caja"] / totals["ramos_programa_caja_inferidos"].replace(0, np.nan)
    )
    derived_program_cols = [
        "tallos_programa_caja",
        "tallos_componentes_caja",
        "ramos_programa_caja_inferidos",
        "tallos_programa_ramo",
    ]
    df = df.drop(columns=[col for col in derived_program_cols if col in df.columns])
    df = df.merge(
        totals[recipe_group + [
            "tallos_programa_caja",
            "tallos_componentes_caja",
            "ramos_programa_caja_inferidos",
            "tallos_programa_ramo",
        ]],
        on=recipe_group,
        how="left",
    )
    tamano_programa = df["tallos_programa_ramo"].round(6).astype("string").str.replace(r"\.0+$", "", regex=True)
    tamano_programa = tamano_programa.where(~tamano_programa.isin(["<NA>", "nan", "None"]), "sin_tamano")
    df["receta_programa_tamano_key"] = normalize_key_series(
        df["receta_programa_key"].astype(str) + "|tallos_ramo_programa_" + tamano_programa.astype(str)
    )
    # SKU operativo separates line-level detail from the real operational structure:
    # SOLIDO groups by producto+color and keeps variedad only as detail; mixed/recipe
    # formats group the lines of the same structure without treating every color as an
    # independent SKU.
    mixed_components = [
        "tipo_pedido_operativo", "subtipo_pedido_operativo", "tipo_orden_empaque", "tipo_empaque",
        "empaque", "producto", "tipo_caja", "tallos_x_ramo", "capuchon", "comida",
        "receta", "codempaque", "bulkbouquet", "caja_operativa",
    ]
    df["sku_composicion"] = combine_key_columns(df, mixed_components)
    df["instancia_pedido_operativo"] = (
        df["cod_cliente"].astype(str) + "|" +
        df["fecha"].dt.strftime("%Y-%m-%d") + "|" +
        df["pedido"].astype(str) + "|" +
        df["sku_composicion"].astype(str)
    )
    df["instancia_pedido_operativo"] = normalize_key_series(df["instancia_pedido_operativo"])
    df["llave_analisis_operativo"] = np.select(
        [
            df["tipo_pedido_operativo"].eq("SOLIDO"),
            df["tipo_pedido_operativo"].ne("SOLIDO"),
        ],
        [
            solid_sku_operativo,
            df["receta_programa_tamano_key"].where(df["tipo_pedido_operativo"].isin(["RAINBOW", "BOUQUET", "BQT", "COMBO"]), df["sku_composicion"]),
        ],
        default=df["estructura_pedido"],
    )
    df["sku_operativo"] = np.select(
        [
            df["tipo_pedido_operativo"].eq("SOLIDO"),
            df["tipo_pedido_operativo"].isin(["RAINBOW", "BOUQUET", "BQT", "COMBO"]),
            df["tipo_pedido_operativo"].ne("SOLIDO"),
        ],
        [
            solid_sku_operativo,
            df["receta_programa_tamano_key"],
            df["sku_composicion"],
        ],
        default=df["llave_analisis_operativo"],
    )

    # Keep monetary-only records for the commercial visualizer. Some accounts
    # invoice value on separate lines from the recipe components carrying
    # stems; downstream structural modules explicitly use positive-stem rows.
    has_stems = df["tallos_analisis"] > 0
    has_value = df["ventas_usd"].ne(0) | df["valor_total_original"].ne(0)
    df = df[has_stems | has_value].copy()
    return df.reset_index(drop=True)


def split_orders_by_estado(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split cleaned order extract by business meaning of ESTADO."""
    return {
        "pedidos_limpios_todos_estados": df.copy(),
        "historico_confirmado": df[df["estado_canonico"].eq("confirmado")].copy(),
        "ordenes_pendientes_reales": df[df["estado_canonico"].eq("pendiente")].copy(),
        "estimados_comerciales_en_proceso": df[df["estado_canonico"].eq("en_proceso")].copy(),
        "cambios_por_verificar_reproceso": df[df["estado_canonico"].isin(["por_verificar", "reproceso"])].copy(),
        "otros_estados": df[df["estado_canonico"].eq("otro")].copy(),
    }


def summarize_estado(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return df.groupby(["estado_canonico", "estado_categoria"], as_index=False).agg(
        filas=("estado_canonico", "size"),
        clientes=("cod_cliente", "nunique"),
        tallos=("tallos_analisis", "sum"),
        fecha_min=("fecha", "min"),
        fecha_max=("fecha", "max"),
    ).sort_values("tallos", ascending=False).reset_index(drop=True)


def clean_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Clean future inventory/projection base.

    Expected minimum columns: PRODUCTO, COLOR, VARIEDAD, GRADO, INVENTARIO, CODFINCA, FECHA, SEMANA.
    """
    df = rename_to_canonical(df, INVENTORY_COLUMNS)
    required = ["producto", "color", "variedad", "grado", "inventario", "cod_finca", "fecha", "semana"]
    df = ensure_columns(df, required)
    df["fecha"] = parse_date(df["fecha"])
    df = df[df["fecha"].notna()].copy()
    df["inventario"] = to_number(df["inventario"])

    for col in ["producto", "color", "variedad", "grado", "cod_finca"]:
        df[col] = df[col].map(normalize_text)

    iso = df["fecha"].dt.isocalendar()
    df["anio"] = iso.year.astype(int)
    df["semana_iso"] = iso.week.astype(int)
    df["anio_semana"] = df["anio"].astype(str) + "-W" + df["semana_iso"].astype(str).str.zfill(2)
    df["producto_color"] = (df["producto"].astype(str) + "|" + df["color"].astype(str)).map(normalize_key)
    df["producto_variedad_color"] = (
        df["producto"].astype(str) + "|" + df["variedad"].astype(str) + "|" + df["color"].astype(str)
    ).map(normalize_key)
    return df.reset_index(drop=True)
