from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.lgf_operativo.pipeline import run_mvp_pipeline

st.set_page_config(page_title="LGF - Clientes y Compra Terminada", layout="wide")
st.title("LGF - Caracterización de clientes y compra terminada")

st.markdown(
    """
Esta herramienta separa los estados de la orden antes de analizar:
**Confirmado** = histórico real despachado; **Pendiente** = orden real futura del cliente;
**En proceso** = estimado comercial; **Por verificar/Reproceso** = cambios sobre confirmado.

El objetivo es identificar clientes estables, tipos de pedido (Surtido, Sólido, Surtido M, Rainbow, etc.), SKUs repetitivos, demanda futura operativa y oportunidades de compra terminada.
"""
)

with st.sidebar:
    st.header("Archivos")
    hist_file = st.file_uploader("Histórico / órdenes", type=["csv", "txt", "tsv", "xlsx", "xls"])
    inv_file = st.file_uploader("Inventario / disponibilidad futura", type=["csv", "txt", "tsv", "xlsx", "xls"])
    st.header("Parámetros")
    lookback_weeks = st.slider("Semanas recientes para forecast histórico", 4, 26, 8)
    horizon_days = st.slider("Días a estimar", 1, 30, 7)
    min_score = st.slider("Score mínimo para forecast histórico", 0, 100, 0)
    forecast_model = st.selectbox(
        "Modelo de forecast para demanda",
        options=["seasonal_boosting", "baseline"],
        format_func=lambda v: "Boosting estacional" if v == "seasonal_boosting" else "Baseline mediana histórica",
    )
    use_pending = st.checkbox("Usar Pendiente como demanda futura oficial", value=True)
    run = st.button("Ejecutar análisis", type="primary")


def save_uploaded(uploaded_file, folder: Path) -> Path:
    path = folder / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


if run:
    if hist_file is None:
        st.error("Sube primero el histórico/órdenes.")
        st.stop()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        hist_path = save_uploaded(hist_file, tmp)
        inv_path = save_uploaded(inv_file, tmp) if inv_file is not None else None
        out_dir = tmp / "outputs"
        with st.spinner("Procesando información..."):
            outputs = run_mvp_pipeline(
                historical_path=hist_path,
                inventory_path=inv_path,
                output_dir=out_dir,
                lookback_weeks=lookback_weeks,
                horizon_days=horizon_days,
                min_forecast_score=min_score,
                use_pending_as_demand=use_pending,
                forecast_model=forecast_model,
            )

        st.success("Análisis terminado")
        perfil = outputs.get("perfil_cliente", pd.DataFrame())
        demanda = outputs.get("demanda_operativa_futura", pd.DataFrame())
        cruce = outputs.get("cruce_forecast_inventario", pd.DataFrame())
        estado_resumen = outputs.get("estado_resumen", pd.DataFrame())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Códigos cliente", f"{perfil['cod_cliente'].nunique():,}" if not perfil.empty else "0")
        c2.metric("Clientes alta prioridad", f"{(perfil['recomendacion_compra'] == 'ALTA_PRIORIDAD_COMPRAR_TERMINADO').sum():,}" if not perfil.empty else "0")
        c3.metric("Líneas demanda futura", f"{len(demanda):,}" if not demanda.empty else "0")
        c4.metric("Líneas cruce inventario", f"{len(cruce):,}" if not cruce.empty else "0")

        tabs = st.tabs(["Estados", "Perfil clientes", "Demanda futura", "Comparación modelos", "Cruce inventario", "Similares", "Descargas"])

        with tabs[0]:
            st.subheader("Resumen por estado")
            st.dataframe(estado_resumen, use_container_width=True, height=300)

        with tabs[1]:
            st.subheader("Perfil de clientes")
            st.dataframe(perfil, use_container_width=True, height=420)
            if not perfil.empty:
                top = perfil.head(20).copy()
                top["cliente_label"] = top["cod_cliente"].astype(str) + " - " + top["cliente"].astype(str)
                fig = px.bar(top, x="cliente_label", y="score_compra_terminada", color="recomendacion_compra", title="Top 20 clientes por score de compra terminada")
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

        with tabs[2]:
            st.subheader("Demanda operativa futura")
            st.caption("Incluye Pendiente real del cliente y el modelo seleccionado para cliente/fecha donde no hay Pendiente.")
            st.dataframe(demanda, use_container_width=True, height=420)

        with tabs[3]:
            st.subheader("Comparación forecast estacional vs baseline")
            comparacion = outputs.get("comparacion_forecast_modelos", pd.DataFrame())
            if comparacion.empty:
                st.info("No hay comparación disponible para los modelos de forecast.")
            else:
                st.dataframe(comparacion, use_container_width=True, height=420)
                resumen_modelos = comparacion.groupby("lectura_comercial", as_index=False).agg(
                    diferencia_tallos=("diferencia_tallos_estacional_vs_baseline", "sum")
                )
                fig = px.bar(resumen_modelos, x="lectura_comercial", y="diferencia_tallos", title="Diferencia de tallos del modelo estacional contra baseline")
                fig.update_layout(xaxis_tickangle=-35)
                st.plotly_chart(fig, use_container_width=True)

        with tabs[4]:
            st.subheader("Cruce demanda futura vs inventario")
            if cruce is None or cruce.empty:
                st.info("No se generó cruce porque no se cargó inventario o no hubo coincidencias.")
            else:
                st.dataframe(cruce, use_container_width=True, height=420)
                resumen = cruce.groupby("prioridad_compra", as_index=False)["tallos_prioridad_compra_cliente"].sum()
                fig = px.bar(resumen, x="prioridad_compra", y="tallos_prioridad_compra_cliente", title="Tallos sugeridos por prioridad de compra")
                fig.update_layout(xaxis_tickangle=-35)
                st.plotly_chart(fig, use_container_width=True)

        with tabs[5]:
            st.subheader("Clientes similares")
            st.dataframe(outputs.get("clientes_similares", pd.DataFrame()), use_container_width=True, height=420)

        with tabs[6]:
            excel_path = out_dir / "LGF_MVP_Caracterizacion_Forecast.xlsx"
            with open(excel_path, "rb") as f:
                st.download_button(
                    "Descargar Excel completo",
                    data=f.read(),
                    file_name="LGF_MVP_Caracterizacion_Forecast.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            for csv_path in sorted(out_dir.glob("*.csv")):
                with open(csv_path, "rb") as f:
                    st.download_button(f"Descargar {csv_path.name}", data=f.read(), file_name=csv_path.name, mime="text/csv")
else:
    st.info("Sube los archivos y ejecuta el análisis desde el panel izquierdo.")
