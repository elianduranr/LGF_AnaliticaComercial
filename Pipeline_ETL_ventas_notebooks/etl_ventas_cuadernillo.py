from datetime import date, datetime, timedelta
from pathlib import Path
import os
import numpy as np
import pandas as pd
import pyodbc

from src.lgf_operativo.local_env import load_local_credentials


load_local_credentials()

ANIOS = list(range(2025, date.today().year + 1))
CARPETA_SALIDA = Path.cwd()
SOBRESCRIBIR = True

def ultimo_domingo_completo(hoy=None):
    hoy = hoy or date.today()
    base = hoy - timedelta(weeks=1)
    return base - timedelta(days=(base.weekday() + 1) % 7)


def rango_anio_iso(anio):
    inicio = date.fromisocalendar(anio, 1, 1)
    ultima_semana = date(anio, 12, 28).isocalendar().week
    fin = date.fromisocalendar(anio, ultima_semana, 7)

    if anio == date.today().isocalendar().year:
        fin = min(fin, ultimo_domingo_completo())

    return datetime.combine(inicio, datetime.min.time()), datetime.combine(fin, datetime.min.time())


def _conn_str_from_env(prefix, default_database, default_server=None, allow_trusted=False):
    load_local_credentials()
    explicit = os.getenv(f"{prefix}_CONN_STR")
    if explicit:
        return explicit
    driver = os.getenv(f"{prefix}_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    server = os.getenv(f"{prefix}_SQL_SERVER", default_server or "")
    database = os.getenv(f"{prefix}_SQL_DATABASE", default_database)
    user = os.getenv(f"{prefix}_SQL_USER")
    password = os.getenv(f"{prefix}_SQL_PASSWORD")
    if not server:
        raise RuntimeError(
            f"Falta {prefix}_SQL_SERVER o {prefix}_CONN_STR."
        )
    if not user or not password:
        raise RuntimeError(
            f"Faltan variables {prefix}_SQL_USER y {prefix}_SQL_PASSWORD o {prefix}_CONN_STR. "
            "No se intentara autenticacion Windows."
        )
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )


def conn_str_webflor():
    return _conn_str_from_env("ETL_WEBFLOR", "WF_Gaitana")


def conn_str_gaitana():
    return (
        os.getenv("ETL_GAITANA_CONN_STR")
        or os.getenv("OP_SALES_CONN_STR")
        or _conn_str_from_env("OP_SALES", "gaitana", default_server="192.168.1.22", allow_trusted=True)
    )


def cargar_master_variedades(path=None):
    project_root = Path(__file__).resolve().parents[1]
    default_path = project_root / "referencias" / "Master_table_varieties.xlsx"
    source = Path(path or os.getenv("ETL_MASTER_VARIETIES_PATH", str(default_path)))
    if not source.exists():
        raise FileNotFoundError(
            f"Archivo de variedades no encontrado: {source}. "
            "Define ETL_MASTER_VARIETIES_PATH o copia el archivo a "
            f"{default_path}."
        )
    master = pd.read_excel(source)
    return master.drop_duplicates(subset="VARIEDAD")


def ejecutar_reporte_ventas(fecha1, fecha2):
    df_list = []
    with pyodbc.connect(conn_str_webflor()) as conn:
        cursor = conn.cursor()
        cursor.execute("EXEC Reporte.InformeDeVentasFacturadas @FechaInicial=?, @FechaFinal=?", (fecha1, fecha2))
        while True:
            if cursor.description:
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                if rows:
                    df_list.append(pd.DataFrame.from_records(rows, columns=columns))
            if not cursor.nextset():
                break
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()


def cargar_divisas(primer_dia, ultimo_dia, anio):
    # Un anio ISO puede comenzar o terminar en el anio calendario vecino.
    tipos_dato = [f"Real_{year}" for year in range(primer_dia.year, ultimo_dia.year + 1)]
    placeholders = ", ".join(["?"] * len(tipos_dato))
    query = f"""
    SELECT Fecha_dt, EUR_USD, GBP_USD
    FROM (
        SELECT COALESCE(TRY_CONVERT(date, Fecha, 103), TRY_CONVERT(date, Fecha, 23), TRY_CONVERT(date, Fecha)) AS Fecha_dt,
               EUR_USD,
               GBP_USD
        FROM dbo.LGF_Divisas
        WHERE Tipo_Dato IN ({placeholders})
    ) D
    WHERE Fecha_dt BETWEEN ? AND ?
    ORDER BY Fecha_dt;
    """
    with pyodbc.connect(conn_str_gaitana()) as conn:
        df_divisas = pd.read_sql(query, conn, params=tipos_dato + [primer_dia, ultimo_dia])
    if df_divisas.empty:
        raise ValueError(f"No se encontraron divisas para {tipos_dato} entre {primer_dia} y {ultimo_dia}.")
    df_divisas["Fecha_dt"] = pd.to_datetime(df_divisas["Fecha_dt"])
    df_divisas[["EUR_USD", "GBP_USD"]] = df_divisas[["EUR_USD", "GBP_USD"]].astype(float)
    tasas_distintas = df_divisas.groupby("Fecha_dt")[["EUR_USD", "GBP_USD"]].nunique(dropna=False)
    fechas_conflictivas = tasas_distintas[(tasas_distintas > 1).any(axis=1)].index.tolist()
    if fechas_conflictivas:
        raise ValueError(f"Divisas contradictorias para {tipos_dato} en fechas: {fechas_conflictivas[:5]}")
    duplicados = int(df_divisas.duplicated(subset=["Fecha_dt"]).sum())
    if duplicados:
        print(f"Divisas duplicadas identicas eliminadas para {tipos_dato}: {duplicados:,}")
    df_divisas = df_divisas.drop_duplicates(subset=["Fecha_dt"]).set_index("Fecha_dt").sort_index()
    df_divisas["USD/EUR"] = 1 / df_divisas["EUR_USD"]
    df_divisas["USD/GBP"] = 1 / df_divisas["GBP_USD"]
    tasas = df_divisas[["USD/EUR", "USD/GBP"]].reset_index().rename(columns={"Fecha_dt": "FECHA"})
    tasas["FECHA"] = pd.to_datetime(tasas["FECHA"])
    return tasas


def cargar_clientes_tipo_flete():
    with pyodbc.connect(conn_str_gaitana()) as conn:
        df = pd.read_sql("SELECT * FROM LGF_Clientes", conn)
    return df.rename(columns={"ID_Cliente": "CODCUSTOM"})


def cargar_clientes_webflor():
    with pyodbc.connect(conn_str_webflor()) as conn:
        detalle = pd.read_sql("SELECT * FROM Venta.ClienteSucursal;", conn)
        master = pd.read_sql("SELECT * FROM Venta.Cliente;", conn)
    detalle = detalle[["Codigo", "NomSucursal", "IdCliente"]].copy().rename(columns={"Codigo": "Codigo_sucursal"})
    master = master[["IdCliente", "NomCliente", "Codigo"]].copy().rename(columns={"Codigo": "Codigo_master"})
    final = pd.merge(master, detalle, on="IdCliente", how="left")
    final.drop(final[final["Codigo_master"].astype(str).str.strip() == "5104"].index, inplace=True)
    return final.drop_duplicates(subset=["Codigo_sucursal"], keep="first").reset_index(drop=True)


def formatear_guia(guia):
    guia = str(guia).strip()
    if guia.isdigit() and len(guia) > 3:
        return guia[:3] + "-" + guia[3:]
    return guia


COLUMNAS_CONTROL = ["TallosConfirmados", "TallosPedidos", "TOTALTALLOS", "VALORTOTAL"]


def asegurar_numericos(df, etapa):
    for col in COLUMNAS_CONTROL:
        if col not in df.columns:
            raise KeyError(f"Falta columna numerica requerida en {etapa}: {col}")
        original = df[col]
        convertido = pd.to_numeric(original, errors="coerce")
        invalidos = original.notna() & convertido.isna()
        if invalidos.any():
            muestra = original.loc[invalidos].head(5).tolist()
            raise ValueError(f"Valores no numericos en {etapa}.{col}: {muestra}")
        df[col] = convertido
    return df


def resumen_control(df):
    return {col: float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum()) for col in COLUMNAS_CONTROL}


def registrar_control(control, etapa, df, tipo="estado"):
    fila = {"ETAPA": etapa, "TIPO": tipo, "FILAS": len(df)}
    fila.update(resumen_control(df))
    control.append(fila)


def validar_coherencia_origen_tallos(control, df, anio):
    pedidos = pd.to_numeric(df["TallosPedidos"], errors="coerce").fillna(0)
    confirmados = pd.to_numeric(df["TallosConfirmados"], errors="coerce").fillna(0)
    con_pedido = pedidos.ne(0)
    filas_2x = int((con_pedido & confirmados.eq(2 * pedidos)).sum())
    filas_iguales = int((con_pedido & confirmados.eq(pedidos)).sum())
    ratio = float(confirmados.sum() / pedidos.sum()) if pedidos.sum() else np.nan
    control.append({
        "ETAPA": "diagnostico_origen_tallos", "TIPO": "validacion_origen", "FILAS": len(df),
        "TallosConfirmados": float(confirmados.sum()), "TallosPedidos": float(pedidos.sum()),
        "TOTALTALLOS": float(pd.to_numeric(df["TOTALTALLOS"], errors="coerce").fillna(0).sum()),
        "VALORTOTAL": float(pd.to_numeric(df["VALORTOTAL"], errors="coerce").fillna(0).sum()),
        "RATIO_CONFIRMADOS_PEDIDOS": ratio, "FILAS_CONFIRMADOS_2X_PEDIDOS": filas_2x,
        "FILAS_CONFIRMADOS_IGUAL_PEDIDOS": filas_iguales,
    })
    proporcion_2x = filas_2x / int(con_pedido.sum()) if con_pedido.any() else 0
    if ratio > 1.25 or proporcion_2x > 0.10:
        raise ValueError(
            f"Origen anomalo para {anio}: TallosConfirmados/TallosPedidos={ratio:.4f}, "
            f"filas exactamente 2x={filas_2x:,} ({proporcion_2x:.2%}). "
            "Revisar Venta.PedidoItemFlor.TotalTallosConfirmados antes de exportar."
        )


def validar_totales(etapa, df, esperado, columnas=COLUMNAS_CONTROL, tolerancia=0.01):
    actual = resumen_control(df)
    diferencias = {col: actual[col] - esperado[col] for col in columnas if abs(actual[col] - esperado[col]) > tolerancia}
    if diferencias:
        raise ValueError(f"Control numerico fallo en {etapa}. Diferencias frente al esperado: {diferencias}")


def restar_resumen(base, removido):
    return {col: base[col] - removido[col] for col in COLUMNAS_CONTROL}


def sumar_delta(base, antes, despues):
    return {col: base[col] - antes[col] + despues[col] for col in COLUMNAS_CONTROL}


def preparar_ventas_periodo(fecha1, fecha2, master_table_var, df_clientes_original, df_clientes_final, etiqueta=None):
    fecha1 = pd.to_datetime(fecha1).to_pydatetime()
    fecha2 = pd.to_datetime(fecha2).to_pydatetime()
    anio = int(pd.Timestamp(fecha1).isocalendar().year)
    etiqueta = etiqueta or f"{fecha1.date()} a {fecha2.date()}"
    print(f"Procesando periodo {etiqueta}: {fecha1.date()} a {fecha2.date()}")

    historic_datita = ejecutar_reporte_ventas(fecha1, fecha2)
    if historic_datita.empty:
        print(f"No se encontraron datos de ventas para {etiqueta}.")
        return pd.DataFrame(), pd.DataFrame()

    control = []
    historic_datita = asegurar_numericos(historic_datita.copy(), "extraccion_original")
    registrar_control(control, "extraccion_original", historic_datita)
    validar_coherencia_origen_tallos(control, historic_datita, anio)
    esperado = resumen_control(historic_datita)

    historic_datita.rename(columns={"NomVariedad": "VARIEDAD", "NomColor": "COLOR", "TAMANO": "GRADO"}, inplace=True)
    historic_datita["VARIEDAD"] = historic_datita["VARIEDAD"].str.lower()
    historic_datita["PRODUCTO"] = historic_datita["PRODUCTO"].str.lower()
    historic_datita["COLOR"] = historic_datita["COLOR"].str.lower()

    cajas_a_corregir = ["Blooms Carnations Asstd - Cliente 1001", "Carnations Asstd - Cliente 1001"]
    mask = (historic_datita["CODCUSTOM"].astype(str) == "1142") & (historic_datita["CajaId"].isin(cajas_a_corregir))
    ajuste_1142_antes = historic_datita.loc[mask].copy()
    historic_datita.loc[mask, "CajaId"] = "Blooms Carnations Asstd - Cliente 1142"
    if mask.any():
        historic_datita.loc[mask, "VALORTOTAL"] = historic_datita.loc[mask, "TallosConfirmados"] * historic_datita.loc[mask, "VALORUNITARIO"]
    ajuste_1142_despues = historic_datita.loc[mask].copy()
    registrar_control(control, "ajuste_1142_antes", ajuste_1142_antes, "ajuste_permitido")
    registrar_control(control, "ajuste_1142_despues", ajuste_1142_despues, "ajuste_permitido")
    esperado = sumar_delta(esperado, resumen_control(ajuste_1142_antes), resumen_control(ajuste_1142_despues))
    validar_totales("correccion caja cliente 1142", historic_datita, esperado)
    registrar_control(control, "post_ajuste_1142", historic_datita)

    historic_datita_normalized = pd.merge(historic_datita, master_table_var, on="VARIEDAD", how="left")
    historic_datita_normalized["PRODUCTO"] = historic_datita_normalized["Product Code"].combine_first(historic_datita_normalized["PRODUCTO"])
    historic_datita_normalized["COLOR"] = historic_datita_normalized["Color Code"].combine_first(historic_datita_normalized["COLOR"])
    historic_datita_normalized["VARIEDAD"] = historic_datita_normalized["Var Code"].combine_first(historic_datita_normalized["VARIEDAD"])
    historic_datita_normalized.drop(["Family Code", "Product Code", "Tone Code", "Color Code"], axis=1, inplace=True)
    historic_datita_normalized["VARIEDAD"] = historic_datita_normalized["VARIEDAD"].str.lower()
    historic_datita_normalized["PRODUCTO"] = historic_datita_normalized["PRODUCTO"].str.lower()
    historic_datita_normalized["COLOR"] = historic_datita_normalized["COLOR"].str.lower()
    historic_datita_normalized["VARIEDAD"] = historic_datita_normalized["VARIEDAD"].str.replace(r"[.,!?]", "", regex=True)

    dict_pompon = {"pompon": "pompon", "pompón button": "pompon", "pompón cushion": "pompon", "pompón daisy": "pompon", "pompón novelty": "pompon", "pompón cdn": "pompon", "disbus cushion": "disbud", "disbud": "disbud", "disbud cremon": "disbud", "disbud linette": "disbud", "disbud cushion": "disbud", "disbud spider": "disbud", "girasol": "girasol", "sunflower": "girasol", "pick": "bouquet"}
    historic_datita_normalized["PRODUCTO"] = historic_datita_normalized["PRODUCTO"].apply(lambda x: dict_pompon.get(x, x))

    lista_concatenacion = ["alstroemeria", "aster", "calla", "craspedia", "disbud", "gerbera", "gypsophila", "hydrangea", "hypericum", "lepidium", "leucadendro", "lilies", "liliput", "limonium", "matsumoto", "mini hydrangea", "pompon", "rose", "ruscus", "snapdragon", "solidago", "spray rose", "statice", "girasol", "trachelium", "veronica", "cocculus"]
    historic_datita_normalized["VARIEDAD"] = historic_datita_normalized.apply(lambda row: f"{row['PRODUCTO']} {row['COLOR']}" if row["PRODUCTO"] in lista_concatenacion else row["VARIEDAD"], axis=1)
    historic_datita_normalized["VARIEDAD"] = historic_datita_normalized.apply(lambda row: f"{row['PRODUCTO']} {row['COLOR']}" if pd.isnull(row["VARIEDAD"]) else row["VARIEDAD"], axis=1)
    validar_totales("normalizacion variedades", historic_datita_normalized, esperado)
    registrar_control(control, "post_normalizacion_variedades", historic_datita_normalized)

    historic_data_piece = historic_datita_normalized.copy()
    Elimination_codes = ["5006", "5005", "5020", "5412", "5025", "5855", "5034", "5129", "3", "5513"]
    eliminados_codigos = historic_data_piece[historic_data_piece["CODCUSTOM"].isin(Elimination_codes)].copy()
    registrar_control(control, "excluidos_codigos_operacion", eliminados_codigos, "exclusion_permitida")
    historic_data_piece = historic_data_piece[~historic_data_piece["CODCUSTOM"].isin(Elimination_codes)]
    esperado = restar_resumen(esperado, resumen_control(eliminados_codigos))
    validar_totales("exclusion codigos operacion", historic_data_piece, esperado)
    historic_data_piece["FECHA"] = pd.to_datetime(historic_data_piece["FECHA"], errors="coerce")
    historic_data_piece["AÑO"] = historic_data_piece["FECHA"].dt.isocalendar().year
    historic_data_piece["SEMANA"] = historic_data_piece["FECHA"].dt.isocalendar().week
    historic_data_piece["MES"] = historic_data_piece["FECHA"].dt.month
    historic_data_piece["AÑO_SEMANA"] = historic_data_piece["AÑO"].astype(str) + "-W" + historic_data_piece["SEMANA"].astype(str).str.zfill(2)
    historic_data_piece["CODCUSTOM"] = historic_data_piece["CODCUSTOM"].astype(str)

    condicion_base = (historic_data_piece["NomCompania"] == "La Gaitana Farms SAS") & (historic_data_piece["CODCONSOL"].isin(["794", "1999", "30542", "19991"]))
    excepcion = historic_data_piece["CODCUSTOM"] == "1070"
    excluidos_consolidado = historic_data_piece[condicion_base & ~excepcion].copy()
    registrar_control(control, "excluidos_consolidado_interno", excluidos_consolidado, "exclusion_permitida")
    data_final_billing = historic_data_piece[~(condicion_base & ~excepcion)].copy().reset_index(drop=True)
    esperado = restar_resumen(esperado, resumen_control(excluidos_consolidado))
    validar_totales("exclusion consolidado interno", data_final_billing, esperado)
    mask_1070_gaitana = (data_final_billing["CODCUSTOM"] == "1070") & (data_final_billing["NomCompania"] == "La Gaitana Farms SAS")
    ajuste_1070_gaitana_antes = data_final_billing.loc[mask_1070_gaitana].copy()
    data_final_billing.loc[mask_1070_gaitana, "VALORTOTAL"] = 0
    ajuste_1070_gaitana_despues = data_final_billing.loc[mask_1070_gaitana].copy()
    registrar_control(control, "ajuste_1070_gaitana_antes", ajuste_1070_gaitana_antes, "ajuste_permitido_facturacion_en_charme")
    registrar_control(control, "ajuste_1070_gaitana_despues", ajuste_1070_gaitana_despues, "ajuste_permitido_facturacion_en_charme")
    esperado = sumar_delta(esperado, resumen_control(ajuste_1070_gaitana_antes), resumen_control(ajuste_1070_gaitana_despues))
    mask_1070_charme = (data_final_billing["CODCUSTOM"] == "1070") & (data_final_billing["NomCompania"] == "Charme Flowers Inc c/o Kaufman Rossin")
    ajuste_1070_charme_antes = data_final_billing.loc[mask_1070_charme].copy()
    cols_tallos_charme = [c for c in ["TallosConfirmados", "TallosPedidos", "TOTALTALLOS"] if c in data_final_billing.columns]
    data_final_billing.loc[mask_1070_charme, cols_tallos_charme] = 0
    ajuste_1070_charme_despues = data_final_billing.loc[mask_1070_charme].copy()
    registrar_control(control, "ajuste_1070_charme_antes", ajuste_1070_charme_antes, "ajuste_permitido_tallos_en_gaitana")
    registrar_control(control, "ajuste_1070_charme_despues", ajuste_1070_charme_despues, "ajuste_permitido_tallos_en_gaitana")
    esperado = sumar_delta(esperado, resumen_control(ajuste_1070_charme_antes), resumen_control(ajuste_1070_charme_despues))
    validar_totales("ajustes comerciales 1070", data_final_billing, esperado)
    registrar_control(control, "post_filtros_y_ajustes", data_final_billing)

    data_final_billing.rename(columns={"NomVariedad": "VARIEDAD", "NomColor": "COLOR", "TAMANO": "GRADO"}, inplace=True)
    for col in ["PRODUCTO", "COLOR", "VARIEDAD", "GRADO"]:
        if col in data_final_billing.columns:
            data_final_billing[col] = data_final_billing[col].astype(str).str.lower()
    diccionario_grados = {"40 cm": "40 cm", "44 cms": "40 cm", "50 cm": "50 cm", "55 Cms": "55 cm", "55 cm": "55 cm", "60 cm": "60 cm", "65 cm": "65 cm", "6O cm": "60 cm", "70 cm": "70 cm", "Fcy": "fcy", "Granel": "granel", "Mediano": "mediano", "Nacional": "nacional", "Perfection": "perfection", "Petit": "petit", "Sel": "sel", "Select": "sel", "Short": "short", "Super select": "super select", "Unico": "unico", "fcy": "fcy", "nac": "nacional", "sel": "sel", "std": "std", np.nan: "non-grade"}
    data_final_billing["GRADO"] = data_final_billing["GRADO"].map(diccionario_grados).fillna("non-grade")

    tasas = cargar_divisas(pd.to_datetime(data_final_billing["FECHA"].min()).date(), pd.to_datetime(data_final_billing["FECHA"].max()).date(), anio)
    data_billing_dollars = pd.merge(data_final_billing, tasas, on=["FECHA"], how="left", validate="many_to_one").sort_values(by="FECHA", ascending=True)
    validar_totales("union tasas divisas", data_billing_dollars, esperado)
    monedas_conversion = data_billing_dollars["NomMoneda"].isin(["EUROS", "GBP"])
    if data_billing_dollars.loc[monedas_conversion, ["USD/EUR", "USD/GBP"]].isna().any().any():
        raise ValueError(f"Faltan tasas de divisas para ventas en EUR/GBP del anio ISO {anio}.")
    data_billing_dollars["USD/EUR"] = data_billing_dollars["USD/EUR"].ffill().astype(float)
    data_billing_dollars["USD/GBP"] = data_billing_dollars["USD/GBP"].ffill().astype(float)
    data_billing_dollars["VALORTOTAL"] = data_billing_dollars["VALORTOTAL"].astype(float)
    data_billing_dollars["VENTAS_USD"] = np.where(data_billing_dollars["NomMoneda"] == "EUROS", data_billing_dollars["VALORTOTAL"] / data_billing_dollars["USD/EUR"], np.where(data_billing_dollars["NomMoneda"] == "GBP", data_billing_dollars["VALORTOTAL"] / data_billing_dollars["USD/GBP"], data_billing_dollars["VALORTOTAL"]))

    data_billing_dollars["GuiaMaster"] = data_billing_dollars["GuiaMaster"].apply(formatear_guia)
    data_billing_dollars["GuiaMaster"] = data_billing_dollars["GuiaMaster"].astype(str).str.replace(" ", "", regex=False).str.strip().apply(formatear_guia)
    data_billing_dollars = pd.merge(data_billing_dollars, df_clientes_original[["CODCUSTOM", "Tipo_Flete"]], on="CODCUSTOM", how="left")
    validar_totales("union tipo flete", data_billing_dollars, esperado)
    for col in data_billing_dollars.columns:
        if data_billing_dollars[col].dtype == object:
            data_billing_dollars[col] = data_billing_dollars[col].astype(str).str.strip()
    data_billing_dollars = data_billing_dollars.where(pd.notnull(data_billing_dollars), None)

    data_billing_dollars.drop(columns=["COMENTARIOSPEDIDO"], inplace=True, errors="ignore")
    data_billing_dollars["VALORUNITARIO"] = pd.to_numeric(data_billing_dollars["VALORUNITARIO"], errors="coerce", downcast="float")
    data_billing_dollars.rename(columns={"VERSION": "Version_1"}, inplace=True)
    data_billing_dollars["ABREVIADOFINCA"] = data_billing_dollars["ABREVIADOFINCA"].apply(lambda x: "AR" if x in ["ARB", "TEUC-ARB", "DANNAF", "TEO - ARB"] else "GF")

    df = pd.merge(data_billing_dollars, df_clientes_final, left_on="CODCUSTOM", right_on="Codigo_sucursal", how="left")
    validar_totales("union maestro clientes", df, esperado)
    df["CODCUSTOM"] = df["Codigo_master"].combine_first(df["CODCUSTOM"])
    df["CLIENTE"] = df["NomCliente"].combine_first(df["CLIENTE"])
    data_billing_dollars = df.drop(columns=["IdCliente", "NomCliente", "Codigo_master", "Codigo_sucursal", "NomSucursal"], errors="ignore").copy()
    mask_1070 = data_billing_dollars["CODCUSTOM"].astype(str).str.strip() == "1070"
    data_billing_dollars["NomCompania"] = np.where(mask_1070, "Charme Flowers Inc c/o Kaufman Rossin", data_billing_dollars["NomCompania"])
    validar_totales("preparacion final", data_billing_dollars, esperado)
    registrar_control(control, "pre_exportacion", data_billing_dollars)

    columnas_salida = [
        "NomCompania", "semana", "DIA", "fecha", "cod_cliente", "cliente", "grupo", "subcliente",
        "tipo_venta", "tipo_orden_empaque", "pedido", "invoice", "tipo_empaque", "empaque", "grado",
        "caja_id", "color", "variedad", "PIEZASEQUVALENTES", "FULLESEQUIVALENTES", "TYPEOFPACKAGE",
        "tipo_caja", "tallos_total", "tallos_pedidos", "TIPOCORTE", "VALORUNITARIO", "MARCACAJA",
        "producto", "AGENCIACARGA", "pais", "ciudad", "RXCAJA", "fulles", "equivalencia", "flor_emp",
        "tallos_x_ramo", "ramos_pedidos", "RXCAJADETALLE", "ramos_confirmados", "po", "id_caja",
        "Version_1", "OBSERVACIONESEMPAQUE", "tipo_precio", "TXRAMO", "comida", "capuchon", "mes",
        "tipo_orden", "estado", "vendedor", "receta", "bulkbouquet", "codempaque", "pull_date",
        "GuiaMaster", "serial", "abrev_finca", "finca", "NomMoneda", "cod_cliente_consolidado",
        "cliente_consolidado", "Var Code", "AÑO", "AÑO_SEMANA", "USD/EUR", "USD/GBP", "Tipo_Flete",
        "piezas", "tallos_confirmados", "VALORTOTAL", "ventas_usd"
    ]
    renombrar_salida = {
        "SEMANA": "semana", "FECHA": "fecha", "CODCUSTOM": "cod_cliente", "CLIENTE": "cliente",
        "GRUPO": "grupo", "SUBCLIENTE": "subcliente", "TIPOVENTA": "tipo_venta",
        "TIPORDENEMPAQUE": "tipo_orden_empaque", "PEDIDO": "pedido", "INVOICE": "invoice",
        "TIPEMPAQUE": "tipo_empaque", "EMPAQUE": "empaque", "GRADO": "grado", "CajaId": "caja_id",
        "COLOR": "color", "VARIEDAD": "variedad", "TIPCAJA": "tipo_caja", "TOTALTALLOS": "tallos_total",
        "TallosPedidos": "tallos_pedidos", "PRODUCTO": "producto", "PAIS": "pais", "CIUDAD": "ciudad",
        "FULLES": "fulles", "EQUIVALENCIA": "equivalencia", "FLOREMP": "flor_emp",
        "TALLXRAM": "tallos_x_ramo", "TOTRAMPED": "ramos_pedidos", "TOTRAMCONF": "ramos_confirmados",
        "PO": "po", "IDCAJA": "id_caja", "TipoPrecio": "tipo_precio", "Comida": "comida",
        "Capuchon": "capuchon", "MES": "mes", "TipoOrden": "tipo_orden", "ESTADO": "estado",
        "VENDEDOR": "vendedor", "RECETA": "receta", "BULKBOUQUET": "bulkbouquet",
        "CODEMPAQUE": "codempaque", "PullDate": "pull_date", "SERIAL": "serial",
        "ABREVIADOFINCA": "abrev_finca", "FINCA": "finca", "CODCONSOL": "cod_cliente_consolidado",
        "CLIENTECONSOL": "cliente_consolidado", "PIEZAS": "piezas",
        "TallosConfirmados": "tallos_confirmados", "VENTAS_USD": "ventas_usd"
    }
    data_billing_dollars["NomMoneda"] = "DOLARES"
    df_export = data_billing_dollars.rename(columns=renombrar_salida).copy()
    for col in columnas_salida:
        if col not in df_export.columns:
            df_export[col] = pd.NA
    df_export = df_export[columnas_salida]

    sum_cols = ["piezas", "tallos_total", "tallos_pedidos", "tallos_confirmados", "VALORTOTAL", "ventas_usd"]
    faltantes = [c for c in sum_cols if c not in df_export.columns]
    if faltantes:
        raise KeyError(f"Faltan columnas esperadas para {anio}: {faltantes}")

    keys = [c for c in df_export.columns if c not in sum_cols]
    for c in sum_cols:
        df_export[c] = pd.to_numeric(df_export[c], errors="coerce").fillna(0)
    df_export = df_export.groupby(keys, dropna=False, as_index=False)[sum_cols].sum()
    df_control_export = df_export.rename(columns={"tallos_total": "TOTALTALLOS", "tallos_pedidos": "TallosPedidos", "tallos_confirmados": "TallosConfirmados"})
    validar_totales("agrupacion exportacion", df_control_export, esperado)
    registrar_control(control, "exportacion", df_control_export)
    return df_export, pd.DataFrame(control)


def preparar_ventas_anio(anio, master_table_var, df_clientes_original, df_clientes_final):
    fecha1, fecha2 = rango_anio_iso(anio)
    return preparar_ventas_periodo(
        fecha1,
        fecha2,
        master_table_var,
        df_clientes_original,
        df_clientes_final,
        etiqueta=f"anio ISO {anio}",
    )


def preparar_ventas_rango(start_date, end_date, master_path=None):
    master_table_var = cargar_master_variedades(master_path)
    df_clientes_original = cargar_clientes_tipo_flete()
    df_clientes_final = cargar_clientes_webflor()
    return preparar_ventas_periodo(
        start_date,
        end_date,
        master_table_var,
        df_clientes_original,
        df_clientes_final,
    )


def exportar_ventas_rango(start_date, end_date, output_dir=None, master_path=None, prefix="ventas_facturadas"):
    output = Path(output_dir or CARPETA_SALIDA)
    output.mkdir(parents=True, exist_ok=True)
    df_export, df_control = preparar_ventas_rango(start_date, end_date, master_path=master_path)
    safe_start = pd.Timestamp(start_date).strftime("%Y%m%d")
    safe_end = pd.Timestamp(end_date).strftime("%Y%m%d")
    ventas_path = output / f"{prefix}_{safe_start}_{safe_end}.csv"
    control_path = output / f"control_validacion_ventas_{safe_start}_{safe_end}.csv"
    df_export.to_csv(ventas_path, index=False, encoding="utf-8-sig")
    df_control.to_csv(control_path, index=False, encoding="utf-8-sig")
    return df_export, df_control, ventas_path, control_path
