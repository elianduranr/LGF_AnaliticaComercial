"""Ejecutor del forecast historico semanal para pedidos SOLIDO confirmados.

Este modulo es el unico que usa directamente todo el historico consolidado
durante la etapa actual del proyecto. Limpia solo el universo necesario,
mantiene cache propio y genera outputs separados para el Dash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.lgf_operativo.cleaning import clean_historical_orders, load_tipo_pedido_reference
from src.lgf_operativo.io_utils import read_table, write_outputs
from src.lgf_operativo.solid_forecast import SolidForecastConfig, run_solid_forecast_pipeline


DEFAULT_RAW_HISTORICO = Path("bases de datos historicas") / "historic_sales_acum.csv"
DEFAULT_OUTPUT = str(Path("resultados") / "forecast_solidos")

SOLID_COLS = [
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
    "estado_canonico",
    "tallos_analisis",
    "tallos_confirmados",
    "faltante_tallos",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LGF: forecast semanal de demanda SOLIDO a partir del historico crudo completo."
    )
    parser.add_argument(
        "--raw-historico",
        default=str(DEFAULT_RAW_HISTORICO),
        help="CSV/TXT/XLSX crudo acumulado. Se limpia solo para este modulo.",
    )
    parser.add_argument(
        "--historico-limpio",
        default=None,
        help="Opcional: CSV ya limpio y confirmado. Si se informa, reemplaza --raw-historico.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Carpeta de salida separada del forecast.")
    parser.add_argument(
        "--tipo-reference",
        default=None,
        help="Respaldo opcional para extractos incompletos sin campos de receta; no usar con la base completa.",
    )
    parser.add_argument("--historico-sheet", default=None, help="Hoja Excel, si la fuente cruda es XLSX/XLS.")
    parser.add_argument("--chunk-size", type=int, default=150_000, help="Filas por bloque para CSV crudo.")
    parser.add_argument("--no-cache", action="store_true", help="Ignora cache limpio del forecast.")
    parser.add_argument("--test-weeks", type=int, default=8, help="Semanas finales usadas como test.")
    parser.add_argument("--lookback-weeks", type=int, default=8, help="Ventana reciente del baseline.")
    parser.add_argument("--horizon-weeks", type=int, default=8, help="Semanas futuras a proyectar.")
    parser.add_argument("--no-excel", action="store_true", help="Escribe solo CSV; omite Excel.")
    return parser.parse_args()


def _forecast_cache_path(source: Path, output: Path, tipo_reference_path: Path | None = None) -> Path:
    stat = source.stat()
    reference_stat = tipo_reference_path.stat() if tipo_reference_path and tipo_reference_path.exists() else None
    payload = {
        "path": str(source.resolve()).lower(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "version": 5,
        "scope": "confirmado_solido_forecast",
        "tipo_reference": str(tipo_reference_path.resolve()).lower() if tipo_reference_path and tipo_reference_path.exists() else "",
        "tipo_reference_size": reference_stat.st_size if reference_stat else 0,
        "tipo_reference_mtime_ns": reference_stat.st_mtime_ns if reference_stat else 0,
    }
    key = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return output / "_cache" / f"historico_confirmado_solidos_{key}.pkl"


def _only_confirmed_solids(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Conserva solidos de demanda historica observada.

    Las fuentes de ordenes con estado filtran exclusivamente ``confirmado``.
    El acumulado de ventas facturadas no contiene columna de estado; en ese
    caso todas sus lineas representan historia observada, igual que en el
    modulo descriptivo.
    """
    if cleaned.empty:
        return cleaned
    estado_original = cleaned.get("estado_original_norm", pd.Series("sin_info", index=cleaned.index))
    estado_no_informado = estado_original.fillna("sin_info").astype(str).str.lower().isin(
        ["", "nan", "none", "sin_info"]
    ).all()
    confirmed_mask = (
        pd.Series(True, index=cleaned.index)
        if estado_no_informado
        else cleaned["estado_canonico"].eq("confirmado")
    )
    subset = cleaned[
        confirmed_mask
        & cleaned["tipo_pedido_operativo"].eq("SOLIDO")
        & pd.to_numeric(cleaned["tallos_analisis"], errors="coerce").fillna(0).gt(0)
    ].copy()
    subset = _exclude_mixed_structure_markers(subset)
    keep = [col for col in SOLID_COLS if col in subset.columns]
    return subset[keep].copy()


def _exclude_mixed_structure_markers(frame: pd.DataFrame) -> pd.DataFrame:
    """Evita que historicos antiguos etiquetados SOLIDO incluyan BQT/COMBO."""
    if frame.empty:
        return frame
    text = pd.Series("", index=frame.index, dtype="object")
    for col in ["empaque", "sku_operativo", "sku_terminado"]:
        if col in frame.columns:
            text = text.str.cat(frame[col].fillna("").astype(str), sep=" ")
    mixed = text.str.lower().str.contains(r"\bcombo\b|\bbqt\b|\bbouquet\b", regex=True, na=False)
    return frame[~mixed].copy()


def _read_clean_confirmed(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    if "fecha" in frame.columns:
        frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce")
    if "tipo_pedido_operativo" in frame.columns:
        frame = frame[frame["tipo_pedido_operativo"].astype(str).str.upper().eq("SOLIDO")].copy()
    return _exclude_mixed_structure_markers(frame)


def _load_raw_solids(
    source: Path,
    output: Path,
    sheet: str | None,
    chunk_size: int,
    use_cache: bool,
    tipo_reference_path: Path | None = None,
) -> tuple[pd.DataFrame, str]:
    """Limpia la fuente cruda por bloques y conserva solo SOLIDO confirmado.

    El cache pertenece exclusivamente al forecast para evitar forzar al
    descriptivo o a clusters a usar toda la historia durante sus pruebas.
    """
    cache = _forecast_cache_path(source, output, tipo_reference_path)
    if use_cache and cache.exists():
        return pd.read_pickle(cache), f"cache limpio forecast: {cache}"

    suffix = source.suffix.lower()
    tipo_reference = load_tipo_pedido_reference(tipo_reference_path)
    if tipo_reference:
        print(f"- Referencia tipologica aplicada: {tipo_reference_path}", flush=True)
    chunks: list[pd.DataFrame] = []
    if suffix in {".csv", ".txt"}:
        try:
            reader = pd.read_csv(source, encoding="utf-8-sig", low_memory=False, chunksize=chunk_size)
            for idx, raw_chunk in enumerate(reader, start=1):
                chunks.append(_only_confirmed_solids(clean_historical_orders(raw_chunk, tipo_reference=tipo_reference)))
                print(f"  bloque {idx:,}: {sum(len(item) for item in chunks):,} lineas solidas confirmadas", flush=True)
        except UnicodeDecodeError:
            reader = pd.read_csv(source, encoding="latin-1", low_memory=False, chunksize=chunk_size)
            for idx, raw_chunk in enumerate(reader, start=1):
                chunks.append(_only_confirmed_solids(clean_historical_orders(raw_chunk, tipo_reference=tipo_reference)))
                print(f"  bloque {idx:,}: {sum(len(item) for item in chunks):,} lineas solidas confirmadas", flush=True)
    else:
        chunks.append(_only_confirmed_solids(clean_historical_orders(read_table(source, sheet=sheet), tipo_reference=tipo_reference)))

    solids = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=SOLID_COLS)
    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        solids.to_pickle(cache)
    return solids, (
        f"base cruda limpiada para forecast: {source}; "
        "si no existe estado, ventas historicas se interpretan como observadas"
    )


def build_source_summary(historico: pd.DataFrame, source: str, source_path: Path | None) -> pd.DataFrame:
    """Documenta fuente, cobertura temporal y volumen usado por el forecast."""
    fecha = pd.to_datetime(historico.get("fecha"), errors="coerce")
    tallos = pd.to_numeric(historico.get("tallos_analisis"), errors="coerce").fillna(0)
    return pd.DataFrame(
        [
            {
                "fuente": source,
                "ruta_fuente": str(source_path.resolve()) if source_path else "",
                "alcance": "SOLIDO historico observado/confirmado; excluye SURTIDO, SURTIDO_M, RAINBOW, BOUQUET, BQT y COMBO",
                "fecha_min": fecha.min(),
                "fecha_max": fecha.max(),
                "anios": int(fecha.dt.year.nunique()),
                "lineas_solidas_confirmadas": int(len(historico)),
                "clientes": int(historico["cod_cliente"].nunique()) if "cod_cliente" in historico else 0,
                "tallos": float(tallos.sum()),
            }
        ]
    )


if __name__ == "__main__":
    args = parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    print("Iniciando forecast historico de solidos LGF...", flush=True)
    if args.historico_limpio:
        source_path = Path(args.historico_limpio)
        print(f"- Historico limpio informado: {source_path}", flush=True)
        historico = _read_clean_confirmed(source_path)
        source_note = "historico limpio confirmado informado por argumento"
    else:
        source_path = Path(args.raw_historico)
        if not source_path.exists():
            raise FileNotFoundError(f"No encontre la base cruda historica: {source_path}")
        print(f"- Base cruda historica: {source_path}", flush=True)
        historico, source_note = _load_raw_solids(
            source=source_path,
            output=output,
            sheet=args.historico_sheet,
            chunk_size=args.chunk_size,
            use_cache=not args.no_cache,
            tipo_reference_path=Path(args.tipo_reference) if args.tipo_reference else None,
        )
    if historico.empty:
        raise ValueError("No quedaron pedidos SOLIDO confirmados para construir el forecast.")

    config = SolidForecastConfig(
        test_weeks=args.test_weeks,
        lookback_weeks=args.lookback_weeks,
        horizon_weeks=args.horizon_weeks,
    )
    fecha = pd.to_datetime(historico["fecha"], errors="coerce")
    print(f"- Alcance forecast: SOLIDO confirmado, {fecha.min():%Y-%m-%d} a {fecha.max():%Y-%m-%d}", flush=True)
    print(f"- Lineas solidas confirmadas: {len(historico):,}", flush=True)
    print(f"- Test: {args.test_weeks} semanas | Horizonte: {args.horizon_weeks} semanas", flush=True)

    outputs = run_solid_forecast_pipeline(
        historico_confirmado=historico,
        perfil_cliente=None,
        output_dir=None,
        config=config,
    )
    outputs = {
        "solid_forecast_fuente_datos": build_source_summary(historico, source_note, source_path),
        **outputs,
    }
    write_outputs(
        outputs,
        output,
        excel_name="LGF_Forecast_Solidos_Historico.xlsx",
        write_excel=not args.no_excel,
    )

    print("\nForecast de solidos terminado. Archivos generados en:", output.resolve())
    print("\nTablas generadas:")
    for name, frame in outputs.items():
        print(f"- {name}: {frame.shape[0]:,} filas x {frame.shape[1]:,} columnas")
