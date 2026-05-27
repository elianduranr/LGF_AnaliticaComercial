"""Pipeline descriptivo que prepara perfiles, estructuras y tablas del Dash.

El resultado de este modulo alimenta el visualizador general, la vista de
orden regular y constituye la entrada controlada para entrenar clusters.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .cleaning import clean_historical_orders, load_tipo_pedido_reference, split_orders_by_estado, summarize_estado
from .io_utils import read_table, resolve_path, write_outputs
from .metrics import (
    build_client_profile,
    build_client_week_operational_sku,
    build_mix_tables,
    build_operational_structure_tables,
    build_operational_sku_composition,
    build_operational_sku_summary,
    build_repeated_structures,
    build_sales_visualizer_tables,
    build_typical_week,
    summarize_operational_demand,
)
from .pipeline import PipelineProgress


DESCRIPTIVE_DASH_COLUMNS = {
    "pedidos_limpios_todos_estados": [
        "fecha", "cod_cliente", "cliente", "pais", "pedido", "estado_canonico", "estado_categoria",
        "tipo_pedido_operativo", "origen_tipologia_operativa", "producto", "variedad", "color", "grado", "tipo_caja",
        "tallos_x_ramo", "capuchon", "comida", "empaque", "tallos_analisis",
        "tallos_total", "tallos_confirmados", "faltante_tallos", "ventas_usd",
        "valor_unitario_original", "valor_total_original", "moneda_original",
        "sku_terminado", "sku_flexible", "llave_analisis_operativo", "color_componente_key",
        "receta_estructura_key", "receta_programa_key", "receta_programa_tamano_key", "sku_operativo", "sku_composicion", "instancia_pedido_operativo",
        "caja_operativa", "ramos_pedidos", "ramos_x_caja", "ramos_x_caja_detalle", "piezas", "fulles", "equivalencia",
        "tallos_componente_caja", "tallos_programa_caja", "tallos_componentes_caja", "ramos_programa_caja_inferidos", "tallos_programa_ramo",
    ],
    "historico_confirmado": [
        "fecha", "cod_cliente", "cliente", "pais", "pedido", "tipo_pedido_operativo", "origen_tipologia_operativa",
        "familia_analisis_operativa", "enfoque_analisis_operativo", "rol_color_operativo",
        "producto", "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo",
        "capuchon", "comida", "empaque", "tallos_analisis", "tallos_total",
        "tallos_confirmados", "faltante_tallos", "ventas_usd", "valor_unitario_original",
        "valor_total_original", "moneda_original", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key", "receta_programa_key", "receta_programa_tamano_key",
        "sku_operativo", "sku_composicion", "instancia_pedido_operativo", "caja_operativa",
        "ramos_pedidos", "ramos_x_caja", "ramos_x_caja_detalle", "piezas", "fulles", "equivalencia",
        "tallos_componente_caja", "tallos_programa_caja", "tallos_componentes_caja", "ramos_programa_caja_inferidos", "tallos_programa_ramo",
        "anio", "semana_iso", "anio_semana", "mes_num",
    ],
    "ordenes_pendientes_reales": [
        "fecha", "cod_cliente", "cliente", "pais", "pedido", "tipo_pedido_operativo", "producto",
        "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "tallos_analisis",
        "tallos_confirmados", "faltante_tallos", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key", "receta_programa_key", "receta_programa_tamano_key",
    ],
    "estimados_comerciales_en_proceso": [
        "fecha", "cod_cliente", "cliente", "pais", "pedido", "tipo_pedido_operativo", "producto",
        "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "tallos_analisis",
        "tallos_confirmados", "faltante_tallos", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key", "receta_programa_key", "receta_programa_tamano_key",
    ],
    "cambios_por_verificar_reproceso": [
        "fecha", "cod_cliente", "cliente", "pais", "pedido", "tipo_pedido_operativo", "producto",
        "variedad", "color", "grado", "tipo_caja", "tallos_x_ramo", "tallos_analisis",
        "tallos_confirmados", "faltante_tallos", "sku_terminado", "sku_flexible",
        "llave_analisis_operativo", "color_componente_key", "receta_estructura_key", "receta_programa_key", "receta_programa_tamano_key",
    ],
}
DESCRIPTIVE_DASH_COLUMNS["historico_visualizador_comercial"] = DESCRIPTIVE_DASH_COLUMNS["historico_confirmado"]


def _clean_cache_paths(
    hist_path: Path,
    output_dir: str | Path,
    historical_sheet: str | None,
    tipo_reference_path: str | Path | None = None,
) -> tuple[Path, Path]:
    stat = hist_path.stat()
    reference = Path(tipo_reference_path) if tipo_reference_path else None
    reference_stat = reference.stat() if reference and reference.exists() else None
    payload = {
        "path": str(hist_path.resolve()).lower(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sheet": historical_sheet,
        "version": 8,
        "tipo_reference": str(reference.resolve()).lower() if reference and reference.exists() else "",
        "tipo_reference_size": reference_stat.st_size if reference_stat else 0,
        "tipo_reference_mtime_ns": reference_stat.st_mtime_ns if reference_stat else 0,
    }
    key = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    cache_dir = Path(output_dir) / "_cache"
    return cache_dir / f"historico_limpio_{key}.pkl", cache_dir


def _load_or_clean_historical(
    raw_hist: pd.DataFrame,
    hist_path: Path,
    output_dir: str | Path,
    historical_sheet: str | None,
    tipo_reference_path: str | Path | None,
    use_cache: bool,
    progress: PipelineProgress,
) -> pd.DataFrame:
    cache_path, cache_dir = _clean_cache_paths(hist_path, output_dir, historical_sheet, tipo_reference_path)
    if use_cache and cache_path.exists():
        progress.note(f"Usando cache limpio: {cache_path}")
        return pd.read_pickle(cache_path)
    tipo_reference = load_tipo_pedido_reference(tipo_reference_path)
    if tipo_reference:
        progress.note(f"Aplicando referencia tipologica: {tipo_reference_path}")
    pedidos_all = clean_historical_orders(raw_hist, tipo_reference=tipo_reference)
    if use_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        pedidos_all.to_pickle(cache_path)
        progress.note(f"Cache limpio guardado: {cache_path}")
    return pedidos_all


def run_descriptive_pipeline(
    historical_path: str | Path,
    output_dir: str | Path = Path("resultados") / "descriptivos",
    historical_sheet: str | None = None,
    show_progress: bool = True,
    use_cache: bool = True,
    write_full_clean_csv: bool = False,
    write_excel: bool = True,
    analysis_year: int | None = None,
    analysis_years: list[int] | tuple[int, ...] | None = None,
    tipo_reference_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Build only descriptive outputs for client/product analysis.

    This intentionally excludes clustering, similarity, forecast and inventory.
    Use it when the work is focused on understanding historical client behavior
    and improving the descriptive dashboard.

    Parameters
    ----------
    analysis_year : int, optional
        Compatibility option for a single calendar year.
    analysis_years : sequence of int, optional
        Calendar years included in the descriptive window. If omitted together
        with ``analysis_year``, all historical years are processed.
    tipo_reference_path : path-like, optional
        Emergency fallback for reduced historical extracts that do not contain
        the source recipe fields. The complete accumulated base is classified
        directly and must not provide this argument.
    """
    if analysis_year is not None and analysis_years:
        raise ValueError("Usa analysis_year o analysis_years, no ambos.")
    selected_years = (
        sorted({int(year) for year in analysis_years})
        if analysis_years
        else ([int(analysis_year)] if analysis_year is not None else [])
    )
    progress = PipelineProgress(show_progress)
    progress.configure([
        ("Resolver rutas", 1),
        ("Leer historico", 12),
        ("Limpiar y clasificar pedidos", 18),
        ("Filtrar anos de analisis", 2 if selected_years else 0),
        ("Separar estados", 3),
        ("Perfil cliente", 4),
        ("Mixes generales", 5),
        ("Estructuras repetidas", 4),
        ("Semana tipica", 4),
        ("SKU operativo resumen", 5),
        ("SKU operativo composicion", 5),
        ("Estructuras caja/componentes", 5),
        ("Cliente semana SKU operativo", 5),
        ("Agregados ventas visualizador", 4),
        ("Estados no confirmados", 2),
        ("Escribir outputs descriptivos", 10),
    ])

    progress.start("Resolver rutas", 1)
    hist_path = resolve_path(historical_path)
    if hist_path is None or not hist_path.exists():
        raise FileNotFoundError(f"No encontre el historico: {historical_path}")
    progress.finish(str(hist_path))

    cache_path, _ = _clean_cache_paths(hist_path, output_dir, historical_sheet, tipo_reference_path)
    cache_ready = use_cache and cache_path.exists()

    progress.start("Leer historico", 12)
    if cache_ready:
        raw_hist = pd.DataFrame()
        progress.finish(f"saltado; cache limpio disponible en {cache_path}")
    else:
        raw_hist = read_table(hist_path, sheet=historical_sheet)
        progress.finish(f"{raw_hist.shape[0]:,} filas x {raw_hist.shape[1]:,} columnas")

    progress.start("Limpiar y clasificar pedidos", 18)
    pedidos_all = _load_or_clean_historical(
        raw_hist, hist_path, output_dir, historical_sheet, tipo_reference_path, use_cache, progress
    )
    progress.finish(f"{pedidos_all.shape[0]:,} filas limpias")

    if selected_years:
        progress.start("Filtrar anos de analisis", 2)
        pedidos_all = pedidos_all[pedidos_all["fecha"].dt.year.isin(selected_years)].copy()
        progress.finish(f"{', '.join(map(str, selected_years))}: {pedidos_all.shape[0]:,} filas")

    progress.start("Separar estados", 3)
    splits = split_orders_by_estado(pedidos_all)
    historico_visualizador_comercial = splits["historico_confirmado"]
    if historico_visualizador_comercial.empty:
        historico_visualizador_comercial = pedidos_all.copy()
    # Models and structure profiles are based on physical stem movement only.
    # The commercial copy additionally retains value-only lines used for sales
    # and price metrics when invoicing is separate from recipe components.
    historico_confirmado = historico_visualizador_comercial[
        pd.to_numeric(historico_visualizador_comercial["tallos_analisis"], errors="coerce").fillna(0).gt(0)
    ].copy()
    progress.finish(
        f"confirmado volumen {historico_confirmado.shape[0]:,}, "
        f"comercial {historico_visualizador_comercial.shape[0]:,}, "
        f"pendiente {splits['ordenes_pendientes_reales'].shape[0]:,}"
    )

    progress.start("Perfil cliente", 4)
    perfil = build_client_profile(historico_confirmado)
    progress.finish(f"{perfil.shape[0]:,} clientes x {perfil.shape[1]:,} columnas")

    progress.start("Mixes generales", 5)
    mix_tables = build_mix_tables(historico_confirmado)
    mix_rows = sum(frame.shape[0] for frame in mix_tables.values())
    progress.finish(f"{len(mix_tables):,} tablas, {mix_rows:,} filas totales")

    progress.start("Estructuras repetidas", 4)
    estructuras_repetidas = build_repeated_structures(historico_confirmado)
    progress.finish(f"{estructuras_repetidas.shape[0]:,} filas x {estructuras_repetidas.shape[1]:,} columnas")

    progress.start("Semana tipica", 4)
    semana_tipica = build_typical_week(historico_confirmado)
    progress.finish(f"{semana_tipica.shape[0]:,} filas x {semana_tipica.shape[1]:,} columnas")

    progress.start("SKU operativo resumen", 5)
    sku_operativo_resumen = build_operational_sku_summary(historico_confirmado)
    progress.finish(f"{sku_operativo_resumen.shape[0]:,} filas x {sku_operativo_resumen.shape[1]:,} columnas")

    progress.start("SKU operativo composicion", 5)
    sku_operativo_composicion = build_operational_sku_composition(historico_confirmado)
    progress.finish(f"{sku_operativo_composicion.shape[0]:,} filas x {sku_operativo_composicion.shape[1]:,} columnas")

    progress.start("Estructuras caja/componentes", 5)
    estructura_tables = build_operational_structure_tables(historico_confirmado)
    progress.finish(
        f"cabeceras {estructura_tables['estructura_caja'].shape[0]:,}, "
        f"componentes {estructura_tables['estructura_componentes'].shape[0]:,}, "
        f"versiones {estructura_tables['catalogo_estructura_version'].shape[0]:,}"
    )

    progress.start("Cliente semana SKU operativo", 5)
    cliente_semana_sku_operativo = build_client_week_operational_sku(historico_confirmado)
    progress.finish(f"{cliente_semana_sku_operativo.shape[0]:,} filas x {cliente_semana_sku_operativo.shape[1]:,} columnas")

    progress.start("Agregados ventas visualizador", 4)
    ventas_visualizador = build_sales_visualizer_tables(historico_visualizador_comercial)
    ventas_rows = sum(frame.shape[0] for frame in ventas_visualizador.values())
    progress.finish(f"{len(ventas_visualizador):,} tablas, {ventas_rows:,} filas totales")

    progress.start("Estados no confirmados", 2)
    demanda_pendiente_estructura = summarize_operational_demand(
        splits["ordenes_pendientes_reales"],
        "PENDIENTE_REAL_CLIENTE",
    )
    estimados_comerciales_estructura = summarize_operational_demand(
        splits["estimados_comerciales_en_proceso"],
        "EN_PROCESO_ESTIMADO_COMERCIAL",
    )
    cambios_estructura = summarize_operational_demand(
        splits["cambios_por_verificar_reproceso"],
        "CAMBIO_SOBRE_CONFIRMADO",
    )
    progress.finish(
        f"pendientes {demanda_pendiente_estructura.shape[0]:,}, "
        f"estimados {estimados_comerciales_estructura.shape[0]:,}, "
        f"cambios {cambios_estructura.shape[0]:,}"
    )

    outputs: dict[str, pd.DataFrame] = {
        "estado_resumen": summarize_estado(pedidos_all),
        "pedidos_limpios_todos_estados": pedidos_all,
        "historico_confirmado": historico_confirmado,
        "historico_visualizador_comercial": historico_visualizador_comercial,
        "ordenes_pendientes_reales": splits["ordenes_pendientes_reales"],
        "estimados_comerciales_en_proceso": splits["estimados_comerciales_en_proceso"],
        "cambios_por_verificar_reproceso": splits["cambios_por_verificar_reproceso"],
        "perfil_cliente": perfil,
        "cliente_estructuras_repetidas": estructuras_repetidas,
        "cliente_semana_tipica": semana_tipica,
        "cliente_sku_operativo_resumen": sku_operativo_resumen,
        "cliente_sku_operativo_composicion": sku_operativo_composicion,
        "estructura_caja": estructura_tables["estructura_caja"],
        "estructura_componentes": estructura_tables["estructura_componentes"],
        "catalogo_estructura_version": estructura_tables["catalogo_estructura_version"],
        "cliente_semana_sku_operativo": cliente_semana_sku_operativo,
        "demanda_pendiente_estructura": demanda_pendiente_estructura,
        "estimados_comerciales_estructura": estimados_comerciales_estructura,
        "cambios_estructura": cambios_estructura,
    }
    outputs.update(mix_tables)
    outputs.update(estructura_tables)
    outputs.update(ventas_visualizador)

    progress.start("Escribir outputs descriptivos", 10)
    skip_csv = set() if write_full_clean_csv else {"pedidos_limpios_todos_estados"}
    write_outputs(
        outputs,
        output_dir,
        excel_name="LGF_Descriptivo_Clientes.xlsx",
        csv_columns=DESCRIPTIVE_DASH_COLUMNS,
        skip_csv=skip_csv,
        write_excel=write_excel,
    )
    progress.finish(str(Path(output_dir).resolve()))
    progress.note(f"Tiempo total: {progress.total_elapsed()}")
    return outputs
