"""Carga controlada de ventas procesadas a SQL Server op_sales.

Ejemplos:

    # Carga inicial desde el acumulado local hasta semana 20 de 2026.
    python cargar_op_sales_sql.py --start-date 2021-01-01 --end-date 2026-05-17

    # Reemplazar una semana concreta desde un CSV local ya descargado.
    python cargar_op_sales_sql.py --input "bases de datos historicas/ventas_facturadas_2026.csv" --start-date 2026-05-18 --end-date 2026-05-24

La conexion se lee desde OP_SALES_CONN_STR o variables OP_SALES_SQL_*.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.lgf_operativo.op_sales_sql import get_connection, initialize_schema, process_sales_dataframe, process_stored_procedure_sales, replace_period_from_file, replace_period_from_processed


DEFAULT_INPUT = Path("bases de datos historicas") / "historic_sales_acum.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga ventas procesadas al schema op_sales en SQL Server.")
    parser.add_argument("--init-schema", action="store_true", help="Crea/actualiza el schema op_sales y termina sin cargar datos.")
    parser.add_argument("--schema-file", default="sql/op_sales_schema.sql", help="Script SQL usado con --init-schema.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="CSV/XLSX fuente. Por defecto usa el acumulado historico local.")
    parser.add_argument("--from-cuadernillo", action="store_true", help="Ejecuta la logica del cuadernillo ETL_ventas_por_anios_csv para el rango.")
    parser.add_argument("--master-varieties", default=None, help="Ruta opcional a Master_table_varieties.xlsx para --from-cuadernillo.")
    parser.add_argument("--save-cuadernillo-output", default=None, help="Carpeta opcional para guardar CSV/control generados por el cuadernillo.")
    parser.add_argument("--stored-procedure", default=None, help="Nombre del procedimiento almacenado a ejecutar para el periodo.")
    parser.add_argument("--exec-sql", default=None, help="SQL EXEC parametrizado opcional, por ejemplo: EXEC dbo.proc @inicio=?, @fin=?")
    parser.add_argument("--start-date", required=False, help="Fecha inicial incluida, formato YYYY-MM-DD.")
    parser.add_argument("--end-date", required=False, help="Fecha final incluida, formato YYYY-MM-DD.")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Filas por lote al insertar en SQL. Default: 5000.")
    parser.add_argument(
        "--split-by",
        choices=["none", "year", "month"],
        default="none",
        help="Divide el reemplazo SQL en transacciones por ano o mes despues de procesar la fuente una sola vez.",
    )
    parser.add_argument(
        "--resume-ok",
        action="store_true",
        help="Con --split-by, salta periodos que ya aparecen OK en op_sales.etl_load_batch.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Procesa y valida la fuente, pero no conecta ni escribe en SQL.")
    parser.add_argument("--quiet", action="store_true", help="Reduce los mensajes de avance en consola.")
    return parser.parse_args()


def iter_periods(start_date: str, end_date: str, split_by: str) -> list[tuple[str, str]]:
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if split_by == "none":
        return [(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))]
    periods: list[tuple[str, str]] = []
    current = start
    while current <= end:
        if split_by == "year":
            period_end = min(pd.Timestamp(year=current.year, month=12, day=31), end)
        else:
            period_end = min(current + pd.offsets.MonthEnd(0), end)
        periods.append((current.strftime("%Y-%m-%d"), period_end.strftime("%Y-%m-%d")))
        current = period_end + pd.Timedelta(days=1)
    return periods


def replace_processed_periods(
    processed: pd.DataFrame,
    start_date: str,
    end_date: str,
    source_name: str,
    split_by: str,
    chunk_size: int,
    verbose: bool,
    resume_ok: bool = False,
) -> list[dict[str, int | str]]:
    results = []
    periods = iter_periods(start_date, end_date, split_by)
    ok_periods: set[tuple[str, str]] = set()
    if resume_ok:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT period_start, period_end
                FROM op_sales.etl_load_batch
                WHERE status = 'OK'
                """
            )
            ok_periods = {
                (row[0].strftime("%Y-%m-%d"), row[1].strftime("%Y-%m-%d"))
                for row in cursor.fetchall()
            }
        finally:
            conn.close()
    for index, (period_start, period_end) in enumerate(periods, start=1):
        if resume_ok and (period_start, period_end) in ok_periods:
            if verbose:
                print(f"\nPeriodo {index:,}/{len(periods):,}: {period_start} a {period_end} ya esta OK; se salta.", flush=True)
            continue
        if verbose and split_by != "none":
            print(f"\nPeriodo {index:,}/{len(periods):,}: {period_start} a {period_end}", flush=True)
        result = replace_period_from_processed(
            processed,
            period_start,
            period_end,
            source_name=source_name,
            chunk_size=chunk_size,
            verbose=verbose,
        )
        results.append(result)
    return results


def main() -> None:
    args = parse_args()
    verbose = not args.quiet
    if args.init_schema:
        if verbose:
            print(f"Inicializando schema desde {args.schema_file}", flush=True)
        initialize_schema(args.schema_file)
        print("Schema op_sales creado/actualizado correctamente.")
        return
    if not args.start_date or not args.end_date:
        raise SystemExit("--start-date y --end-date son obligatorios cuando no usas --init-schema.")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size debe ser mayor que cero.")
    if verbose:
        print("Carga op_sales iniciada", flush=True)
        print(f"- rango: {args.start_date} a {args.end_date}", flush=True)
        print(f"- chunk_size: {args.chunk_size:,}", flush=True)
    if args.from_cuadernillo:
        from Pipeline_ETL_ventas_notebooks.etl_ventas_cuadernillo import exportar_ventas_rango, preparar_ventas_rango

        if verbose:
            print("- fuente: cuadernillo ETL_ventas_por_anios_csv", flush=True)
        if args.save_cuadernillo_output:
            raw_export, _, ventas_path, control_path = exportar_ventas_rango(
                args.start_date,
                args.end_date,
                output_dir=args.save_cuadernillo_output,
                master_path=args.master_varieties,
            )
            print(f"CSV cuadernillo guardado: {ventas_path}")
            print(f"Control cuadernillo guardado: {control_path}")
        else:
            raw_export, _ = preparar_ventas_rango(args.start_date, args.end_date, master_path=args.master_varieties)
        processed = process_sales_dataframe(raw_export, args.start_date, args.end_date, verbose=verbose)
        if args.dry_run:
            print("Dry-run terminado: fuente procesada y rango validado; no se escribio en SQL.")
            print(f"- filas procesadas: {len(processed):,}")
            return
        results = replace_processed_periods(
            processed,
            args.start_date,
            args.end_date,
            "ETL_ventas_por_anios_csv.ipynb",
            args.split_by,
            args.chunk_size,
            verbose,
            args.resume_ok,
        )
    elif args.stored_procedure:
        if verbose:
            print(f"- fuente: procedimiento almacenado {args.stored_procedure}", flush=True)
        processed = process_stored_procedure_sales(
            args.stored_procedure,
            args.start_date,
            args.end_date,
            exec_sql=args.exec_sql,
            verbose=verbose,
        )
        if args.dry_run:
            print("Dry-run terminado: procedimiento procesado y rango validado; no se escribio en SQL.")
            print(f"- filas procesadas: {len(processed):,}")
            return
        results = replace_processed_periods(
            processed,
            args.start_date,
            args.end_date,
            args.stored_procedure,
            args.split_by,
            args.chunk_size,
            verbose,
            args.resume_ok,
        )
    else:
        if verbose:
            print(f"- fuente: archivo {args.input}", flush=True)
        from src.lgf_operativo.op_sales_sql import read_and_process_sales

        processed = read_and_process_sales(args.input, args.start_date, args.end_date, verbose=verbose)
        if args.dry_run:
            print("Dry-run terminado: archivo procesado y rango validado; no se escribio en SQL.")
            print(f"- filas procesadas: {len(processed):,}")
            return
        results = replace_processed_periods(
            processed,
            args.start_date,
            args.end_date,
            str(args.input),
            args.split_by,
            args.chunk_size,
            verbose,
            args.resume_ok,
        )
    print("Carga op_sales terminada")
    print(f"- periodos cargados: {len(results):,}")
    print(f"- filas eliminadas: {sum(int(result['rows_deleted']) for result in results):,}")
    print(f"- filas insertadas: {sum(int(result['rows_inserted']) for result in results):,}")
    if results:
        print(f"- ultimo load_id: {results[-1]['load_id']}")


if __name__ == "__main__":
    main()
