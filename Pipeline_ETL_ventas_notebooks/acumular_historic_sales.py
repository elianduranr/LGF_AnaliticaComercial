from pathlib import Path
import re

import pandas as pd


CARPETA = Path(__file__).resolve().parent
PATRON_ARCHIVOS = "ventas_facturadas_*.csv"
ARCHIVO_SALIDA = "historic_sales_acum.csv"
ARCHIVO_TEMPORAL = "historic_sales_acum.tmp.csv"
CHUNK_SIZE = 100_000
COLUMNAS_NUMERICAS = [
    "piezas",
    "tallos_total",
    "tallos_pedidos",
    "tallos_confirmados",
    "VALORTOTAL",
    "ventas_usd",
]
COLUMNAS_ANUALES = [
    "NomCompania",
    "semana",
    "DIA",
    "fecha",
    "cod_cliente",
    "cliente",
    "grupo",
    "subcliente",
    "tipo_venta",
    "tipo_orden_empaque",
    "pedido",
    "invoice",
    "tipo_empaque",
    "empaque",
    "grado",
    "caja_id",
    "color",
    "variedad",
    "PIEZASEQUVALENTES",
    "FULLESEQUIVALENTES",
    "TYPEOFPACKAGE",
    "tipo_caja",
    "tallos_total",
    "tallos_pedidos",
    "TIPOCORTE",
    "VALORUNITARIO",
    "MARCACAJA",
    "producto",
    "AGENCIACARGA",
    "pais",
    "ciudad",
    "RXCAJA",
    "fulles",
    "equivalencia",
    "flor_emp",
    "tallos_x_ramo",
    "ramos_pedidos",
    "RXCAJADETALLE",
    "ramos_confirmados",
    "po",
    "id_caja",
    "Version_1",
    "OBSERVACIONESEMPAQUE",
    "tipo_precio",
    "TXRAMO",
    "comida",
    "capuchon",
    "mes",
    "tipo_orden",
    "estado",
    "vendedor",
    "receta",
    "bulkbouquet",
    "codempaque",
    "pull_date",
    "GuiaMaster",
    "serial",
    "abrev_finca",
    "finca",
    "NomMoneda",
    "cod_cliente_consolidado",
    "cliente_consolidado",
    "Var Code",
    "AÑO",
    "AÑO_SEMANA",
    "USD/EUR",
    "USD/GBP",
    "Tipo_Flete",
    "piezas",
    "tallos_confirmados",
    "VALORTOTAL",
    "ventas_usd",
]


def anio_archivo(archivo):
    match = re.fullmatch(r"ventas_facturadas_(\d{4})\.csv", archivo.name)
    if not match:
        raise ValueError(f"Nombre de archivo anual no valido: {archivo.name}")
    return int(match.group(1))


def validar_columnas(archivo, columnas):
    faltantes = [col for col in COLUMNAS_ANUALES if col not in columnas]
    if faltantes:
        raise ValueError(f"{archivo.name} no contiene columnas del contrato: {faltantes}")
    extras = [col for col in columnas if col not in COLUMNAS_ANUALES]
    if extras:
        raise ValueError(f"{archivo.name} contiene columnas fuera del contrato: {extras}")


def validar_chunk(df, archivo, anio):
    for col in COLUMNAS_NUMERICAS:
        convertido = pd.to_numeric(df[col], errors="coerce")
        invalidos = df[col].notna() & convertido.isna()
        if invalidos.any():
            muestra = df.loc[invalidos, col].head(5).tolist()
            raise ValueError(f"Valores no numericos en {archivo.name}.{col}: {muestra}")
        df[col] = convertido

    anios = pd.to_numeric(df["AÑO"], errors="coerce")
    if anios.isna().any() or not (anios.astype(int) == anio).all():
        encontrados = sorted(anios.dropna().astype(int).unique().tolist())
        raise ValueError(f"{archivo.name} contiene AÑO distintos de {anio}: {encontrados}")


def main():
    archivos = sorted(
        archivo
        for archivo in CARPETA.glob(PATRON_ARCHIVOS)
        if archivo.name != ARCHIVO_SALIDA
    )

    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron archivos con el patron {PATRON_ARCHIVOS} en {CARPETA}"
        )

    ruta_salida = CARPETA / ARCHIVO_SALIDA
    ruta_temporal = CARPETA / ARCHIVO_TEMPORAL
    filas_exportadas = 0
    totales = {col: 0.0 for col in COLUMNAS_NUMERICAS}
    escribir_encabezado = True

    for archivo in archivos:
        anio = anio_archivo(archivo)
        columnas = pd.read_csv(archivo, encoding="utf-8-sig", nrows=0).columns.tolist()
        validar_columnas(archivo, columnas)

        for df in pd.read_csv(
            archivo, encoding="utf-8-sig", low_memory=False, chunksize=CHUNK_SIZE
        ):
            df = df[COLUMNAS_ANUALES].copy()
            validar_chunk(df, archivo, anio)
            df["archivo_origen"] = archivo.name
            df.to_csv(
                ruta_temporal,
                mode="w" if escribir_encabezado else "a",
                header=escribir_encabezado,
                index=False,
                encoding="utf-8-sig" if escribir_encabezado else "utf-8",
            )
            escribir_encabezado = False
            filas_exportadas += len(df)
            for col in COLUMNAS_NUMERICAS:
                totales[col] += float(df[col].fillna(0).sum())

    ruta_temporal.replace(ruta_salida)

    print(f"Archivos unidos: {len(archivos)}")
    for archivo in archivos:
        print(f"- {archivo.name}")
    print(f"Filas exportadas: {filas_exportadas:,}")
    print(f"Columnas exportadas: {len(COLUMNAS_ANUALES) + 1:,}")
    for col, total in totales.items():
        print(f"Total {col}: {total:,.2f}")
    print(f"Archivo generado: {ruta_salida}")


if __name__ == "__main__":
    main()
