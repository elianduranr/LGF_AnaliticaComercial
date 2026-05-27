from __future__ import annotations

from pathlib import Path
from time import perf_counter

import pandas as pd

from .cleaning import clean_historical_orders, clean_inventory, split_orders_by_estado, summarize_estado
from .forecast import build_structural_forecast, pending_orders_to_forecast_format, combine_pending_and_forecast
from .inventory import summarize_inventory, cross_forecast_inventory
from .io_utils import read_table, resolve_path, write_outputs
from .metrics import (
    build_client_profile,
    build_client_week_operational_sku,
    build_mix_tables,
    build_operational_sku_composition,
    build_operational_sku_summary,
    build_repeated_structures,
    build_typical_week,
    summarize_operational_demand,
)
from .similarity import compute_client_similarity, cluster_clients


def _empty() -> pd.DataFrame:
    return pd.DataFrame()


def _format_duration(seconds: float) -> str:
    seconds = max(float(seconds), 0.0)
    if seconds < 60:
        return f"{seconds:,.1f}s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {sec:02d}s"


class PipelineProgress:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.total_weight = 1.0
        self.done_weight = 0.0
        self.current_weight = 0.0
        self.current_name = ""
        self.start_time = perf_counter()
        self.step_time = self.start_time

    def configure(self, steps: list[tuple[str, float]]) -> None:
        self.total_weight = max(sum(weight for _, weight in steps), 1.0)

    def start(self, name: str, weight: float) -> None:
        self.current_name = name
        self.current_weight = weight
        self.step_time = perf_counter()
        self._print(f"[INICIO] {name}")

    def finish(self, detail: str = "") -> None:
        elapsed = perf_counter() - self.step_time
        self.done_weight += self.current_weight
        suffix = f" | {detail}" if detail else ""
        self._print(f"[OK] {self.current_name} en {_format_duration(elapsed)}{suffix}")
        self._print_progress()

    def note(self, message: str) -> None:
        self._print(f"  - {message}")

    def total_elapsed(self) -> str:
        return _format_duration(perf_counter() - self.start_time)

    def _print_progress(self) -> None:
        if not self.enabled:
            return
        elapsed = perf_counter() - self.start_time
        pct = min(self.done_weight / self.total_weight, 1.0)
        eta_text = "calculando"
        if pct > 0:
            eta_text = _format_duration(elapsed * (1 - pct) / pct)
        print(
            f"[PROGRESO] {pct * 100:5.1f}% | transcurrido {_format_duration(elapsed)} | ETA {eta_text}",
            flush=True,
        )

    def _print(self, message: str) -> None:
        if self.enabled:
            print(message, flush=True)


def run_mvp_pipeline(
    historical_path: str | Path,
    inventory_path: str | Path | None = None,
    output_dir: str | Path = "outputs",
    historical_sheet: str | None = None,
    inventory_sheet: str | None = None,
    target_start: str | None = None,
    target_end: str | None = None,
    horizon_days: int = 7,
    lookback_weeks: int = 8,
    min_forecast_score: float = 0,
    max_client_inactive_weeks: int = 16,
    min_recent_active_weeks: int = 2,
    use_pending_as_demand: bool = True,
    forecast_model: str = "seasonal_boosting",
    show_progress: bool = True,
) -> dict[str, pd.DataFrame]:
    """Run the LGF MVP.

    Important business separation by ESTADO:
    - Confirmado: historical real dispatched orders. Used for characterization and statistical forecast.
    - Pendiente: real future order from client. Used as future operational demand.
    - En proceso: commercial estimate. Exported separately, not mixed with historical real.
    - Por verificar/Reproceso: changes over confirmed orders. Exported separately for control.
    """
    progress = PipelineProgress(show_progress)
    progress.configure([
        ("Resolver rutas", 1),
        ("Leer historico", 12),
        ("Limpiar historico y clasificar pedidos", 18),
        ("Separar estados", 3),
        ("Perfil, mixes, similares y clusters", 22),
        ("Forecast baseline", 12),
        ("Forecast estacional", 22 if forecast_model == "seasonal_boosting" else 0),
        ("Demanda futura y estructuras", 8),
        ("Inventario y cruce", 16 if inventory_path else 0),
        ("Escribir outputs", 14),
    ])

    progress.start("Resolver rutas", 1)
    hist_path = resolve_path(historical_path)
    if hist_path is None or not hist_path.exists():
        raise FileNotFoundError(f"No encontré el histórico: {historical_path}")

    progress.finish(str(hist_path))

    progress.start("Leer historico", 12)
    progress.note(f"Archivo: {hist_path}")
    raw_hist = read_table(hist_path, sheet=historical_sheet)
    progress.finish(f"{raw_hist.shape[0]:,} filas x {raw_hist.shape[1]:,} columnas")

    progress.start("Limpiar historico y clasificar pedidos", 18)
    pedidos_all = clean_historical_orders(raw_hist)
    progress.finish(f"{pedidos_all.shape[0]:,} filas limpias")

    progress.start("Separar estados", 3)
    splits = split_orders_by_estado(pedidos_all)

    historico_confirmado = splits["historico_confirmado"]
    # Fallback: if extract has no estado or no confirmed rows, use all records to avoid an empty MVP.
    if historico_confirmado.empty:
        historico_confirmado = pedidos_all.copy()
    progress.finish(
        f"confirmado {historico_confirmado.shape[0]:,}, pendiente {splits['ordenes_pendientes_reales'].shape[0]:,}, en proceso {splits['estimados_comerciales_en_proceso'].shape[0]:,}"
    )

    progress.start("Perfil, mixes, similares y clusters", 22)
    perfil = build_client_profile(historico_confirmado)
    progress.note(f"Perfil cliente: {perfil.shape[0]:,} clientes")
    mix_tables = build_mix_tables(historico_confirmado)
    estructuras_repetidas = build_repeated_structures(historico_confirmado)
    semana_tipica = build_typical_week(historico_confirmado)
    sku_operativo_resumen = build_operational_sku_summary(historico_confirmado)
    sku_operativo_composicion = build_operational_sku_composition(historico_confirmado)
    cliente_semana_sku_operativo = build_client_week_operational_sku(historico_confirmado)
    progress.note(f"Mixes generados: {len(mix_tables):,}")
    similares = compute_client_similarity(historico_confirmado)
    clusters = cluster_clients(historico_confirmado, perfil)
    progress.finish(f"similares {similares.shape[0]:,}, clusters {clusters.shape[0]:,}")

    progress.start("Forecast baseline", 12)
    forecast_hist = build_structural_forecast(
        historico_confirmado,
        perfil,
        target_start=target_start,
        target_end=target_end,
        horizon_days=horizon_days,
        lookback_weeks=lookback_weeks,
        min_score=min_forecast_score,
        max_client_inactive_weeks=max_client_inactive_weeks,
        min_recent_active_weeks=min_recent_active_weeks,
    )
    progress.finish(f"{forecast_hist.shape[0]:,} filas")
    forecast_modelo_estacional = _empty()
    if forecast_model == "seasonal_boosting":
        progress.start("Forecast estacional", 22)
        from .seasonal_model import build_seasonal_boosting_forecast

        forecast_modelo_estacional = build_seasonal_boosting_forecast(
            historico_confirmado,
            perfil,
            baseline_forecast=forecast_hist,
            target_start=target_start,
            target_end=target_end,
            horizon_days=horizon_days,
            lookback_weeks=lookback_weeks,
            min_score=min_forecast_score,
            max_client_inactive_weeks=max_client_inactive_weeks,
            min_recent_active_weeks=min_recent_active_weeks,
        )
        progress.finish(f"{forecast_modelo_estacional.shape[0]:,} filas")
    forecast_para_demanda = forecast_modelo_estacional if not forecast_modelo_estacional.empty else forecast_hist

    progress.start("Demanda futura y estructuras", 8)
    pendientes_reales = splits["ordenes_pendientes_reales"]
    forecast_pendiente = pending_orders_to_forecast_format(pendientes_reales, perfil)
    demanda_operativa_futura = combine_pending_and_forecast(forecast_pendiente, forecast_para_demanda) if use_pending_as_demand else forecast_para_demanda.copy()

    demanda_pendiente_estructura = summarize_operational_demand(pendientes_reales, "PENDIENTE_REAL_CLIENTE")
    estimados_comerciales_estructura = summarize_operational_demand(splits["estimados_comerciales_en_proceso"], "EN_PROCESO_ESTIMADO_COMERCIAL")
    cambios_estructura = summarize_operational_demand(splits["cambios_por_verificar_reproceso"], "CAMBIO_SOBRE_CONFIRMADO")
    progress.finish(f"demanda futura {demanda_operativa_futura.shape[0]:,} filas")

    inv_clean = _empty()
    inv_summaries: dict[str, pd.DataFrame] = {}
    cruce = _empty()
    if inventory_path:
        progress.start("Inventario y cruce", 16)
        inv_path = resolve_path(inventory_path, default_filename="df_inventory_final.csv")
        if inv_path is not None and inv_path.exists():
            progress.note(f"Archivo: {inv_path}")
            raw_inv = read_table(inv_path, sheet=inventory_sheet)
            progress.note(f"Inventario crudo: {raw_inv.shape[0]:,} filas x {raw_inv.shape[1]:,} columnas")
            inv_clean = clean_inventory(raw_inv)
            inv_summaries = summarize_inventory(inv_clean)
            cruce = cross_forecast_inventory(demanda_operativa_futura, inv_clean)
            progress.finish(f"inventario {inv_clean.shape[0]:,}, cruce {cruce.shape[0]:,}")
        else:
            raise FileNotFoundError(f"No encontré el inventario/disponibilidad: {inventory_path}")

    progress.start("Escribir outputs", 14)
    outputs: dict[str, pd.DataFrame] = {
        "estado_resumen": summarize_estado(pedidos_all),
        "pedidos_limpios_todos_estados": pedidos_all,
        "historico_confirmado": historico_confirmado,
        "ordenes_pendientes_reales": pendientes_reales,
        "estimados_comerciales_en_proceso": splits["estimados_comerciales_en_proceso"],
        "cambios_por_verificar_reproceso": splits["cambios_por_verificar_reproceso"],
        "perfil_cliente": perfil,
        "cliente_estructuras_repetidas": estructuras_repetidas,
        "cliente_semana_tipica": semana_tipica,
        "cliente_sku_operativo_resumen": sku_operativo_resumen,
        "cliente_sku_operativo_composicion": sku_operativo_composicion,
        "cliente_semana_sku_operativo": cliente_semana_sku_operativo,
        "clientes_similares": similares,
        "clusters_clientes": clusters,
        "forecast_historico_confirmado": forecast_hist,
        "forecast_modelo_estacional": forecast_modelo_estacional,
        "forecast_pendientes_reales": forecast_pendiente,
        "demanda_operativa_futura": demanda_operativa_futura,
        "demanda_pendiente_estructura": demanda_pendiente_estructura,
        "estimados_comerciales_estructura": estimados_comerciales_estructura,
        "cambios_estructura": cambios_estructura,
        "inventario_limpio": inv_clean,
        "cruce_forecast_inventario": cruce,
    }
    outputs.update(mix_tables)
    outputs.update(inv_summaries)

    # Remove empty sheets only if they have truly no rows and no useful columns? Keep them for visibility.
    write_outputs(outputs, output_dir)
    progress.finish(f"{len(outputs):,} tablas en {Path(output_dir).resolve()}")
    progress.note(f"Tiempo total: {progress.total_elapsed()}")
    return outputs
