# Arquitectura modular LGF Operativo

> Nota de vigencia: el flujo oficial actual, sus carpetas canonicas
> `resultados/` y los comandos ejecutables estan en
> `../README_EJECUCION.md` y `../README_FUNCIONES.md`. Las rutas
> `outputs_*` de este documento registran iteraciones anteriores.

Este proyecto debe evolucionar por modulos separados. La regla de trabajo es no mezclar descriptivos, modelos, clusters, forecast e inventario en una sola iteracion.

## Objetivo inmediato

El foco actual queda en la parte descriptiva:

- entender cliente;
- entender productos;
- leer historicos;
- leer precios en USD y moneda original;
- mejorar el tablero tipo Power BI;
- optimizar consultas para no depender del historico completo en cada callback.

Clusters, forecast, compra e inventario quedan como modulos separados y se tocan despues.

## Capas del proyecto

### 1. Entrada y limpieza

Responsabilidad: convertir historico e inventario crudo en columnas canonicas confiables.

Archivos actuales:

- `src/lgf_operativo/cleaning.py`
- `src/lgf_operativo/io_utils.py`

No debe contener logica visual, forecast ni cluster.

### 2. Descriptivos

Responsabilidad: generar tablas de lectura historica para clientes, productos, SKUs, colores, semanas y precios.

Archivos actuales:

- `src/lgf_operativo/metrics.py`
- `src/lgf_operativo/descriptive.py`
- `run_descriptivos.py`

Outputs principales:

- `perfil_cliente.csv`
- `serie_cliente_semana.csv`
- `serie_cliente_mes_color.csv`
- `mix_producto.csv`
- `mix_color.csv`
- `mix_tipo_pedido.csv`
- `mix_sku_terminado.csv`
- `mix_sku_flexible.csv`
- `mix_variedad.csv`
- `mix_empaque.csv`
- `cliente_estructuras_repetidas.csv`
- `cliente_semana_tipica.csv`
- `cliente_sku_operativo_resumen.csv`
- `cliente_sku_operativo_composicion.csv`
- `cliente_semana_sku_operativo.csv`

Este es el modulo prioritario.

### 3. Clusters y similares

Responsabilidad: agrupar clientes y encontrar clientes parecidos.

Archivos actuales:

- `src/lgf_operativo/similarity.py`
- `src/lgf_operativo/clustering.py`
- `run_clusters.py`

Outputs:

- `clientes_similares.csv`
- `clusters_clientes.csv`
- `cluster_model_evaluation.csv`
- `cluster_features_cliente.csv`
- `cluster_resumen.csv`

No debe bloquear el trabajo descriptivo. Si se recalcula, debe correr como paso separado.

Comando recomendado para 2026:

```powershell
python run_clusters.py --input-dir "outputs_descriptivo_2026_demo" --output "outputs_clusters_2026"
```

Para abrir visualizador descriptivo y clusters en una sola instancia Dash:

```powershell
python run_clusters.py --input-dir "outputs_descriptivo_2026_demo" --output "outputs_descriptivo_2026_dash"
python app_dash.py --data-dir "outputs_descriptivo_2026_dash" --host 127.0.0.1 --port 8054
```

### 4. Forecast / proyeccion

Responsabilidad: estimar demanda futura cuando no existe pedido pendiente real.

Archivos actuales:

- `src/lgf_operativo/forecast.py`
- `src/lgf_operativo/seasonal_model.py`

Outputs:

- `forecast_historico_confirmado.csv`
- `forecast_modelo_estacional.csv`
- `forecast_pendientes_reales.csv`
- `demanda_operativa_futura.csv`

No debe mezclarse con el tablero descriptivo, salvo como contexto futuro.

### 5. Inventario y compra

Responsabilidad: cruzar demanda futura contra disponibilidad.

Archivos actuales:

- `src/lgf_operativo/inventory.py`

Outputs:

- `inventario_limpio.csv`
- `inventario_fecha_item.csv`
- `inventario_fecha_color.csv`
- `inventario_fecha_finca.csv`
- `inventario_semana_item.csv`
- `cruce_forecast_inventario.csv`

Debe depender de demanda futura ya generada, no de descriptivos directos.

### 6. Dashboards

Responsabilidad: leer outputs ya generados y mostrar visualizaciones.

Archivos actuales:

- `app_dash.py`
- `app_streamlit.py`

Regla: el dashboard no debe recalcular modelos pesados. Debe usar CSV agregados y tocar `historico_confirmado.csv` solo para detalle de cliente cuando sea necesario.

## Comandos de trabajo

### Solo descriptivos

```powershell
python run_descriptivos.py --output "outputs_descriptivo"
```

Usar este comando para trabajar Cliente 360 y Visualizador clientes general.

### MVP completo rapido

```powershell
python run_mvp.py --output "outputs_baseline" --forecast-model baseline
```

Usar cuando se necesite demanda futura baseline.

### MVP con inventario

```powershell
python run_mvp.py --output "outputs_baseline" --forecast-model baseline --inventario "RUTA_INVENTARIO"
```

Usar solo cuando se vaya a trabajar compra, disponibilidad o faltantes.

### Modelo estacional

```powershell
python run_mvp.py --forecast-model seasonal_boosting --output "outputs_modelo"
```

Usar solo cuando el foco sea mejorar proyeccion.

## Orden recomendado de trabajo

1. Estabilizar outputs descriptivos y dashboard descriptivo.
2. Optimizar carga del dashboard para usar agregados.
3. Separar pantallas: descriptivos, clusters, forecast, inventario.
4. Mejorar clusters y similares.
5. Mejorar forecast.
6. Mejorar compra e inventario.

## Decisiones tomadas

- Se mantiene `run_mvp.py` para no romper el flujo actual.
- Se agrega `run_descriptivos.py` como entrada rapida y separada.
- Se agrega `src/lgf_operativo/descriptive.py` como orquestador solo descriptivo.
- No se mueven archivos grandes ni se reescribe `app_dash.py` completo en esta etapa.
