"""Carga controlada de ventas procesadas hacia SQL Server op_sales.

El modulo no guarda credenciales. Lee la conexion desde variables de entorno:

- OP_SALES_CONN_STR, o
- OP_SALES_SQL_SERVER, OP_SALES_SQL_DATABASE, OP_SALES_SQL_USER,
  OP_SALES_SQL_PASSWORD y opcionalmente OP_SALES_SQL_DRIVER.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .cleaning import clean_historical_orders
from .io_utils import read_table


SQL_TABLE = "op_sales.fact_sales_line"
LOAD_TABLE = "op_sales.etl_load_batch"
DEFAULT_SCHEMA_FILE = Path("sql") / "op_sales_schema.sql"

TARGET_COLUMNS = [
    "line_key",
    "load_id",
    "fecha",
    "anio",
    "semana_iso",
    "anio_semana",
    "cod_cliente",
    "cliente",
    "NomCompania",
    "pais",
    "ciudad",
    "cod_cliente_consolidado",
    "cliente_consolidado",
    "pedido",
    "invoice",
    "po",
    "estado",
    "estado_canonico",
    "estado_categoria",
    "tipo_pedido_operativo",
    "origen_tipologia_operativa",
    "subtipo_pedido_operativo",
    "familia_analisis_operativa",
    "enfoque_analisis_operativo",
    "rol_color_operativo",
    "producto",
    "variedad",
    "color",
    "grado",
    "tipo_caja",
    "caja_id",
    "id_caja",
    "caja_operativa",
    "tipo_orden_empaque",
    "tipo_empaque",
    "empaque",
    "capuchon",
    "comida",
    "receta",
    "bulkbouquet",
    "codempaque",
    "tallos_x_ramo",
    "ramos_pedidos",
    "ramos_confirmados",
    "ramos_x_caja",
    "ramos_x_caja_detalle",
    "fulles",
    "piezas",
    "equivalencia",
    "tallos_total",
    "tallos_pedidos",
    "tallos_analisis",
    "tallos_confirmados",
    "faltante_tallos",
    "valor_unitario_original",
    "valor_total_original",
    "ventas_usd",
    "moneda_original",
    "usd_eur",
    "usd_gbp",
    "sku_terminado",
    "sku_flexible",
    "producto_color",
    "producto_variedad_color",
    "estructura_pedido",
    "empaque_operativo",
    "llave_analisis_operativo",
    "color_componente_key",
    "receta_estructura_key",
    "receta_programa_key",
    "receta_programa_tamano_key",
    "sku_operativo",
    "sku_composicion",
    "instancia_pedido_operativo",
    "tallos_componente_caja",
    "tallos_programa_caja",
    "tallos_componentes_caja",
    "ramos_programa_caja_inferidos",
    "tallos_programa_ramo",
    "vendedor",
    "finca",
    "abrev_finca",
    "agencia_carga",
    "guia_master",
    "serial",
    "archivo_origen",
    "source_pull_date",
]

MAX_STRING_LENGTHS = {
    "line_key": 64,
    "anio_semana": 8,
    "cod_cliente": 32,
    "cliente": 500,
    "NomCompania": 500,
    "pais": 250,
    "ciudad": 250,
    "cod_cliente_consolidado": 32,
    "cliente_consolidado": 500,
    "pedido": 80,
    "invoice": 80,
    "po": 250,
    "estado": 250,
    "estado_canonico": 40,
    "estado_categoria": 40,
    "tipo_pedido_operativo": 40,
    "origen_tipologia_operativa": 80,
    "subtipo_pedido_operativo": 160,
    "familia_analisis_operativa": 80,
    "enfoque_analisis_operativo": 100,
    "rol_color_operativo": 80,
    "producto": 250,
    "variedad": 500,
    "color": 250,
    "grado": 40,
    "tipo_caja": 250,
    "caja_id": 250,
    "id_caja": 250,
    "caja_operativa": 250,
    "tipo_orden_empaque": 250,
    "tipo_empaque": 250,
    "empaque": 700,
    "capuchon": 500,
    "comida": 500,
    "receta": 700,
    "bulkbouquet": 250,
    "codempaque": 250,
    "moneda_original": 20,
    "sku_terminado": 500,
    "sku_flexible": 500,
    "producto_color": 300,
    "producto_variedad_color": 500,
    "estructura_pedido": 500,
    "empaque_operativo": 600,
    "llave_analisis_operativo": 700,
    "color_componente_key": 700,
    "receta_estructura_key": 700,
    "receta_programa_key": 700,
    "receta_programa_tamano_key": 760,
    "sku_operativo": 760,
    "sku_composicion": 900,
    "instancia_pedido_operativo": 900,
    "vendedor": 500,
    "finca": 500,
    "abrev_finca": 250,
    "agencia_carga": 500,
    "guia_master": 250,
    "serial": 250,
    "archivo_origen": 500,
}

COLUMN_ALIASES = {
    "AGENCIACARGA": "agencia_carga",
    "GuiaMaster": "guia_master",
    "pull_date": "source_pull_date",
    "USD/EUR": "usd_eur",
    "USD/GBP": "usd_gbp",
}

LINE_KEY_COLUMNS = [
    "fecha",
    "cod_cliente",
    "pedido",
    "invoice",
    "caja_operativa",
    "producto",
    "variedad",
    "color",
    "grado",
    "tipo_pedido_operativo",
    "sku_operativo",
    "tallos_analisis",
    "tallos_confirmados",
    "valor_total_original",
]


def conexion_GF() -> str:
    """Conexion local al SQL Server operativo de Gaitana."""
    return (
        r"DRIVER={ODBC Driver 17 for SQL Server};"
        r"SERVER=192.168.1.22;"
        r"DATABASE=gaitana;"
        r"UID=sa;"
        r"PWD=G41trn422*$;"
        r"Encrypt=No;"
    )


def _log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(message, flush=True)


def _summary(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {
            "rows": 0,
            "fecha_min": None,
            "fecha_max": None,
            "clientes": 0,
            "skus": 0,
            "tallos_confirmados": 0.0,
            "ventas_usd": 0.0,
        }
    fechas = pd.to_datetime(frame.get("fecha"), errors="coerce")
    tallos = pd.to_numeric(frame.get("tallos_confirmados", pd.Series(dtype=float)), errors="coerce").fillna(0)
    ventas = pd.to_numeric(frame.get("ventas_usd", pd.Series(dtype=float)), errors="coerce").fillna(0)
    return {
        "rows": int(len(frame)),
        "fecha_min": fechas.min().date() if fechas.notna().any() else None,
        "fecha_max": fechas.max().date() if fechas.notna().any() else None,
        "clientes": int(frame.get("cod_cliente", pd.Series(dtype=object)).nunique(dropna=True)),
        "skus": int(frame.get("sku_operativo", pd.Series(dtype=object)).nunique(dropna=True)),
        "tallos_confirmados": float(tallos.sum()),
        "ventas_usd": float(ventas.sum()),
    }


def _print_summary(label: str, frame: pd.DataFrame, verbose: bool = True) -> None:
    if not verbose:
        return
    info = _summary(frame)
    _log(f"{label}: {info['rows']:,} filas", verbose)
    _log(f"  fechas: {info['fecha_min']} a {info['fecha_max']}", verbose)
    _log(f"  clientes: {info['clientes']:,} | skus: {info['skus']:,}", verbose)
    _log(f"  tallos_confirmados: {info['tallos_confirmados']:,.0f} | ventas_usd: {info['ventas_usd']:,.2f}", verbose)


def connection_string_from_env() -> str:
    explicit = os.getenv("OP_SALES_CONN_STR")
    if explicit:
        explicit = explicit.replace("TrustServerCertificate=yes;", "").replace("TrustServerCertificate=Yes;", "")
        if "Encrypt=" not in explicit and "encrypt=" not in explicit:
            explicit = explicit.rstrip(";") + ";Encrypt=No;"
        return explicit
    if not any(os.getenv(name) for name in ["OP_SALES_SQL_SERVER", "OP_SALES_SQL_USER", "OP_SALES_SQL_PASSWORD"]):
        return conexion_GF()
    driver = os.getenv("OP_SALES_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("OP_SALES_SQL_SERVER", "192.168.1.22")
    database = os.getenv("OP_SALES_SQL_DATABASE", "gaitana")
    user = os.getenv("OP_SALES_SQL_USER")
    password = os.getenv("OP_SALES_SQL_PASSWORD")
    if not server:
        raise RuntimeError(
            "Falta OP_SALES_SQL_SERVER o OP_SALES_CONN_STR. "
            "El valor recomendado para este proyecto es OP_SALES_SQL_SERVER=192.168.1.22."
        )
    if not user or not password:
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            "Encrypt=No;"
        )
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=No;"
    )


def get_connection():
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError("Instala pyodbc para cargar a SQL Server: pip install pyodbc") from exc
    if not any(os.getenv(name) for name in ["OP_SALES_CONN_STR", "OP_SALES_SQL_SERVER", "OP_SALES_SQL_USER", "OP_SALES_SQL_PASSWORD"]):
        return pyodbc.connect(conexion_GF(), timeout=30, autocommit=False)
    return pyodbc.connect(connection_string_from_env(), autocommit=False)


def _split_sql_server_batches(sql_text: str) -> list[str]:
    batches: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        if line.strip().upper() == "GO":
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    batch = "\n".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def initialize_schema(schema_file: str | Path = DEFAULT_SCHEMA_FILE, conn=None) -> None:
    """Ejecuta el DDL de `op_sales` en SQL Server."""
    path = Path(schema_file)
    if not path.exists():
        raise FileNotFoundError(f"No encontre el script SQL de schema: {path}")
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        cursor = conn.cursor()
        for batch in _split_sql_server_batches(path.read_text(encoding="utf-8")):
            cursor.execute(batch)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_connection:
            conn.close()


def assert_schema_ready(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE s.name = 'op_sales'
          AND t.name IN ('fact_sales_line', 'etl_load_batch')
        """
    )
    found = int(cursor.fetchone()[0])
    if found < 2:
        raise RuntimeError(
            "No existen las tablas op_sales.fact_sales_line y op_sales.etl_load_batch. "
            "Ejecuta primero: ./carac_clients/Scripts/python.exe cargar_op_sales_sql.py --init-schema"
        )


def _normalize_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def _hash_rows(frame: pd.DataFrame, cols: Iterable[str]) -> pd.Series:
    available = [col for col in cols if col in frame.columns]
    text = frame[available].fillna("").astype(str).agg("|".join, axis=1)
    occurrence = text.groupby(text, sort=False).cumcount().astype(str)
    keyed_text = text + "|occurrence|" + occurrence
    return keyed_text.map(lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest())


def process_sales_dataframe(
    raw: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
    verbose: bool = False,
) -> pd.DataFrame:
    """Aplica las reglas actuales del proyecto y deja columnas listas para SQL."""
    t0 = time.perf_counter()
    _log(f"Procesando ventas crudas: {len(raw):,} filas, {len(raw.columns):,} columnas", verbose)
    processed = clean_historical_orders(raw)
    _log(f"Limpieza/reglas completadas: {len(processed):,} filas", verbose)
    processed["fecha"] = pd.to_datetime(processed["fecha"], errors="coerce")
    before_dates = len(processed)
    processed = processed[processed["fecha"].notna()].copy()
    dropped_dates = before_dates - len(processed)
    if dropped_dates:
        _log(f"Advertencia: {dropped_dates:,} filas sin fecha valida fueron descartadas.", verbose)
    if start_date:
        processed = processed[processed["fecha"].ge(pd.Timestamp(start_date))].copy()
    if end_date:
        processed = processed[processed["fecha"].le(pd.Timestamp(end_date))].copy()
    if processed.empty:
        _log("Advertencia: no quedaron filas despues de filtrar el rango de fechas.", verbose)
        return processed

    processed["cod_cliente"] = _normalize_code(processed["cod_cliente"])
    for source, target in COLUMN_ALIASES.items():
        if source in processed.columns and target not in processed.columns:
            processed[target] = processed[source]
    processed["line_key"] = _hash_rows(processed, LINE_KEY_COLUMNS)
    duplicated = int(processed.duplicated(["fecha", "line_key"]).sum())
    if duplicated:
        raise RuntimeError(f"Validador fallo: quedaron {duplicated:,} claves fecha+line_key duplicadas antes de SQL.")
    _print_summary("Ventas procesadas para SQL", processed, verbose)
    _log(f"Tiempo procesamiento: {time.perf_counter() - t0:,.1f} segundos", verbose)
    return processed


def read_and_process_sales(
    path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    _log(f"Leyendo archivo fuente: {path}", verbose)
    t0 = time.perf_counter()
    raw = read_table(path)
    _log(f"Archivo leido: {len(raw):,} filas, {len(raw.columns):,} columnas en {time.perf_counter() - t0:,.1f} segundos", verbose)
    return process_sales_dataframe(raw, start_date=start_date, end_date=end_date, verbose=verbose)


def read_op_sales_fact(start_date: str | None = None, end_date: str | None = None, conn=None) -> pd.DataFrame:
    """Lee la fact consolidada desde SQL Server para alimentar descriptivos."""
    owns_connection = conn is None
    conn = conn or get_connection()
    filters = []
    params = []
    if start_date:
        filters.append("fecha >= ?")
        params.append(start_date)
    if end_date:
        filters.append("fecha <= ?")
        params.append(end_date)
    where = " WHERE " + " AND ".join(filters) if filters else ""
    try:
        return pd.read_sql_query(f"SELECT * FROM {SQL_TABLE}{where}", conn, params=params)
    finally:
        if owns_connection:
            conn.close()


def read_stored_procedure_sales(
    procedure_name: str,
    start_date: str,
    end_date: str,
    exec_sql: str | None = None,
    conn=None,
) -> pd.DataFrame:
    """Ejecuta un procedimiento almacenado que recibe fecha inicial/final.

    Si el procedimiento usa parametros posicionales:
        EXEC dbo.MiProcedimiento ?, ?

    Si necesita nombres especificos, pasar exec_sql, por ejemplo:
        EXEC dbo.MiProcedimiento @FechaInicial=?, @FechaFinal=?
    """
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        sql = exec_sql or f"EXEC {procedure_name} ?, ?"
        return pd.read_sql_query(sql, conn, params=[start_date, end_date])
    finally:
        if owns_connection:
            conn.close()


def process_stored_procedure_sales(
    procedure_name: str,
    start_date: str,
    end_date: str,
    exec_sql: str | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    _log(f"Ejecutando procedimiento almacenado: {procedure_name}", verbose)
    t0 = time.perf_counter()
    raw = read_stored_procedure_sales(procedure_name, start_date, end_date, exec_sql=exec_sql)
    _log(f"Procedimiento retorno {len(raw):,} filas en {time.perf_counter() - t0:,.1f} segundos", verbose)
    return process_sales_dataframe(raw, start_date=start_date, end_date=end_date, verbose=verbose)


def prepare_sql_frame(processed: pd.DataFrame, load_id: int, verbose: bool = False) -> pd.DataFrame:
    out = processed.copy()
    out["load_id"] = int(load_id)
    for col in TARGET_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[TARGET_COLUMNS].copy()

    date_cols = ["fecha", "source_pull_date"]
    for col in date_cols:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    numeric_like = [
        "anio",
        "semana_iso",
        "tallos_x_ramo",
        "ramos_pedidos",
        "ramos_confirmados",
        "ramos_x_caja",
        "ramos_x_caja_detalle",
        "fulles",
        "piezas",
        "equivalencia",
        "tallos_total",
        "tallos_pedidos",
        "tallos_analisis",
        "tallos_confirmados",
        "faltante_tallos",
        "valor_unitario_original",
        "valor_total_original",
        "ventas_usd",
        "usd_eur",
        "usd_gbp",
        "tallos_componente_caja",
        "tallos_programa_caja",
        "tallos_componentes_caja",
        "ramos_programa_caja_inferidos",
        "tallos_programa_ramo",
    ]
    for col in numeric_like:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    too_long = []
    for col, max_len in MAX_STRING_LENGTHS.items():
        if col in out.columns:
            lengths = out[col].dropna().astype(str).str.len()
            if not lengths.empty and int(lengths.max()) > max_len:
                too_long.append((col, int(lengths.max()), max_len))
    if too_long:
        detail = ", ".join(f"{col}: {actual}>{limit}" for col, actual, limit in too_long[:12])
        raise RuntimeError(f"Validador fallo: textos exceden el largo SQL definido ({detail}).")
    out = out.replace({np.nan: None, pd.NaT: None})
    duplicated = int(out.duplicated(["fecha", "line_key"]).sum())
    if duplicated:
        raise RuntimeError(f"Validador fallo: SQL frame tiene {duplicated:,} claves fecha+line_key duplicadas.")
    _log(f"Frame SQL listo: {len(out):,} filas, {len(out.columns):,} columnas", verbose)
    return out


def insert_batch_log(conn, source_name: str, start_date: str, end_date: str) -> int:
    cursor = conn.cursor()
    cursor.execute(
        f"""
        INSERT INTO {LOAD_TABLE} (source_name, period_start, period_end)
        OUTPUT INSERTED.load_id
        VALUES (?, ?, ?)
        """,
        source_name,
        start_date,
        end_date,
    )
    return int(cursor.fetchone()[0])


def finish_batch_log(conn, load_id: int, status: str, rows_deleted: int, rows_inserted: int, frame: pd.DataFrame, message: str = "") -> None:
    tallos = float(pd.to_numeric(frame.get("tallos_confirmados", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    ventas = float(pd.to_numeric(frame.get("ventas_usd", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    conn.cursor().execute(
        f"""
        UPDATE {LOAD_TABLE}
        SET finished_at = SYSUTCDATETIME(),
            status = ?,
            rows_deleted = ?,
            rows_inserted = ?,
            tallos_confirmados = ?,
            ventas_usd = ?,
            message = ?
        WHERE load_id = ?
        """,
        status,
        int(rows_deleted),
        int(rows_inserted),
        tallos,
        ventas,
        message[:1000],
        int(load_id),
    )


def delete_period(conn, start_date: str, end_date: str) -> int:
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {SQL_TABLE} WHERE fecha >= ? AND fecha <= ?", start_date, end_date)
    return int(cursor.rowcount if cursor.rowcount is not None else 0)


def insert_sales_frame(conn, frame: pd.DataFrame, chunk_size: int = 5000, verbose: bool = True) -> int:
    if frame.empty:
        return 0
    cols_sql = ", ".join(f"[{col}]" for col in frame.columns)
    placeholders = ", ".join("?" for _ in frame.columns)
    sql = f"INSERT INTO {SQL_TABLE} ({cols_sql}) VALUES ({placeholders})"
    cursor = conn.cursor()
    cursor.fast_executemany = True
    inserted = 0
    total = len(frame)
    batches = (total + chunk_size - 1) // chunk_size
    _log(f"Insertando en SQL por lotes de {chunk_size:,} filas: {total:,} filas totales", verbose)
    t0 = time.perf_counter()
    for batch_index, start in enumerate(range(0, total, chunk_size), start=1):
        batch_frame = frame.iloc[start : start + chunk_size]
        batch = list(batch_frame.itertuples(index=False, name=None))
        cursor.executemany(sql, batch)
        inserted += len(batch)
        if batch_index == 1 or batch_index == batches or batch_index % 10 == 0:
            elapsed = time.perf_counter() - t0
            rate = inserted / elapsed if elapsed else 0
            _log(
                f"  lote {batch_index:,}/{batches:,}: {inserted:,}/{total:,} filas insertadas "
                f"({rate:,.0f} filas/seg)",
                verbose,
            )
    return inserted


def replace_period_from_processed(
    processed: pd.DataFrame,
    start_date: str,
    end_date: str,
    source_name: str,
    conn=None,
    chunk_size: int = 5000,
    verbose: bool = True,
) -> dict[str, int | str]:
    """Reemplaza un rango de fechas en SQL en una transaccion."""
    owns_connection = conn is None
    _log(f"Conectando a SQL Server para reemplazar {start_date} a {end_date}", verbose)
    conn = conn or get_connection()
    load_id = None
    rows_deleted = 0
    rows_inserted = 0
    t0 = time.perf_counter()
    try:
        _log("Validando que existan op_sales.fact_sales_line y op_sales.etl_load_batch", verbose)
        assert_schema_ready(conn)
        if processed.empty:
            raise RuntimeError("Validador fallo: el dataframe procesado esta vacio. No se toca SQL.")
        period = processed[
            pd.to_datetime(processed["fecha"], errors="coerce").between(pd.Timestamp(start_date), pd.Timestamp(end_date))
        ].copy()
        _print_summary("Rango que se va a reemplazar", period, verbose)
        if period.empty:
            raise RuntimeError(f"Validador fallo: no hay filas entre {start_date} y {end_date}. No se toca SQL.")
        duplicated = int(period.duplicated(["fecha", "line_key"]).sum())
        if duplicated:
            raise RuntimeError(f"Validador fallo: el periodo tiene {duplicated:,} claves fecha+line_key duplicadas.")
        _log("Creando registro de carga en op_sales.etl_load_batch", verbose)
        load_id = insert_batch_log(conn, source_name, start_date, end_date)
        _log(f"load_id creado: {load_id}", verbose)
        sql_frame = prepare_sql_frame(period, load_id, verbose=verbose)
        _log("Borrando de SQL el rango indicado antes de insertar", verbose)
        rows_deleted = delete_period(conn, start_date, end_date)
        _log(f"Filas eliminadas del rango: {rows_deleted:,}", verbose)
        rows_inserted = insert_sales_frame(conn, sql_frame, chunk_size=chunk_size, verbose=verbose)
        if rows_inserted != len(sql_frame):
            raise RuntimeError(f"Insertadas {rows_inserted} filas, esperadas {len(sql_frame)}.")
        finish_batch_log(conn, load_id, "OK", rows_deleted, rows_inserted, sql_frame, "Carga reemplazada correctamente.")
        _log("Confirmando transaccion en SQL", verbose)
        conn.commit()
        _log(f"Carga terminada OK en {time.perf_counter() - t0:,.1f} segundos", verbose)
        return {
            "status": "OK",
            "load_id": load_id,
            "rows_deleted": rows_deleted,
            "rows_inserted": rows_inserted,
        }
    except Exception as exc:
        if load_id is not None:
            try:
                finish_batch_log(conn, load_id, "ERROR", rows_deleted, rows_inserted, pd.DataFrame(), str(exc))
            except Exception:
                pass
        conn.rollback()
        raise
    finally:
        if owns_connection:
            conn.close()


def replace_period_from_file(
    path: str | Path,
    start_date: str,
    end_date: str,
    chunk_size: int = 5000,
    verbose: bool = True,
) -> dict[str, int | str]:
    processed = read_and_process_sales(path, start_date=start_date, end_date=end_date, verbose=verbose)
    return replace_period_from_processed(
        processed,
        start_date,
        end_date,
        source_name=str(path),
        chunk_size=chunk_size,
        verbose=verbose,
    )
