# LGF - MVP Caracterización de clientes y compra terminada

## Flujo Oficial Actual

La ejecucion modular vigente, las carpetas canonicas `resultados/` y los
comandos Bash actualizados estan documentados en:

- [README_EJECUCION.md](README_EJECUCION.md)
- [README_FUNCIONES.md](README_FUNCIONES.md)

Los comandos `outputs_*` que aparecen mas adelante corresponden a pruebas y
versiones anteriores; se conservan como referencia, pero no son el flujo
recomendado para nuevas corridas.

Este proyecto separa correctamente los estados de la orden antes de hacer análisis:

| Estado | Significado operativo | Uso en el MVP |
|---|---|---|
| Confirmado | Histórico real ya despachado | Base para caracterización, estabilidad, cumplimiento y forecast histórico |
| Pendiente | Orden real futura recibida del cliente | Se usa primero como demanda operativa futura |
| En proceso | Estimado comercial | Se exporta separado; no se mezcla con histórico real |
| Por verificar / Reproceso | Cambios sobre algo ya confirmado | Se exporta separado para control |

Reglas principales:

- Fecha oficial: `FECHA`.
- Cantidad oficial: `TallosPedidos`.
- Cumplimiento: `TallosConfirmados / TallosPedidos`.
- Nivel de análisis: `CLIENTE`, pero todos los exports incluyen `cod_cliente` / `CODCUSTOM`.
- Flor terminada: producto + variedad + color + grado + tipo caja + tallos por ramo + capuchón + comida + empaque.

## Instalación

```bash
python -m venv carac_clients
source carac_clients/Scripts/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecutar

## Organizacion modular de trabajo

El proyecto queda separado por focos para no mezclar todo en una sola iteracion:

- Descriptivos: clientes, productos, historicos, precios y Cliente 360. Entrada recomendada: `run_descriptivos.py`.
- Clusters/similares: agrupacion y parecidos de clientes por mercado. Modulos: `src/lgf_operativo/clustering.py`, `src/lgf_operativo/similarity.py` y comando `run_clusters.py`.
- Forecast/proyeccion: demanda futura baseline o estacional. Modulos: `src/lgf_operativo/forecast.py` y `src/lgf_operativo/seasonal_model.py`.
- Inventario/compra: cruce de demanda contra disponibilidad. Modulo: `src/lgf_operativo/inventory.py`.
- Dashboard: solo debe leer outputs generados; no debe recalcular modelos pesados.

Documentacion nueva:

- `docs/INSTRUCCIONES_INGENIERO.md`
- `docs/ARQUITECTURA_MODULAR.md`
- `docs/FOCO_DESCRIPTIVO.md`

Para trabajar solo descriptivos:

```powershell
python run_descriptivos.py --output "outputs_descriptivo"
```

Para trabajar solo clusters con ejemplos 2026:

```powershell
python run_clusters.py --input-dir "outputs_descriptivo_2026_demo" --output "outputs_clusters_2026"
```

Este modulo evalua K-medias, K-modas y clustering jerarquico dentro de cinco mercados definidos: Estados Unidos/Canada, The Netherlands, Polonia, Asia y Otros. La version actual pondera con mayor fuerza color, producto, tipo de pedido y constancia, y exporta variables diferenciadoras por cluster.

Para abrir **todo junto** en Dash 2026, escribe los clusters dentro de la carpeta completa del dashboard y levanta Dash contra esa misma carpeta:

```powershell
python run_clusters.py --input-dir "outputs_descriptivo_2026_demo" --output "outputs_descriptivo_2026_dash"
python app_dash.py --data-dir "outputs_descriptivo_2026_dash" --host 127.0.0.1 --port 8054
```

No uses `outputs_clusters_2026` para el visualizador general de clientes; esa carpeta sirve para revisar solo clusters.

La primera corrida limpia y clasifica el historico, y guarda un cache en `outputs_descriptivo/_cache`.
Las siguientes corridas con el mismo archivo reutilizan ese cache y saltan la limpieza pesada.

Para generar solo CSVs, sin Excel:

```powershell
python run_descriptivos.py --output "outputs_descriptivo" --no-excel
```

Por defecto no se escribe `pedidos_limpios_todos_estados.csv` completo porque puede pesar varios GB y no es necesario para el Dash.
Si necesitas ese archivo completo para auditoria:

```powershell
python run_descriptivos.py --output "outputs_descriptivo" --full-clean-csv
```

Luego levanta Dash contra esos outputs si vas a trabajar vistas descriptivas:

```powershell
python app_dash.py --data-dir "outputs_descriptivo" --host 127.0.0.1 --port 8050
```

### Rutas temporales de trabajo

Estas son las rutas temporales usadas actualmente para correr el pipeline:

- Historico: `C:/Proyectos_gaitana/Visualizador historico/historic_sales_acum.csv`
- Inventario: `C:/Users/elian/OneDrive - LA GAITANA FARMS SAS/Sincronizacion_PDA/basesBI/df_inventory_final.csv`
- Output: `outputs_baseline`

Comando recomendado para evitar errores de continuacion de linea:

```powershell
python run_mvp.py --historico "C:\Proyectos_gaitana\Visualizador historico\historic_sales_acum.csv" --output "outputs_baseline" --horizon-days 14 --lookback-weeks 8 --forecast-model baseline
```

En PowerShell tambien puedes escribirlo en varias lineas usando backtick al final de cada linea:

```powershell
python run_mvp.py `
  --historico "C:\Proyectos_gaitana\Visualizador historico\historic_sales_acum.csv" `
  --output "outputs_baseline" `
  --horizon-days 14 `
  --lookback-weeks 8 `
  --forecast-model baseline
```

Y luego levanta Dash con esos mismos outputs:

```powershell
python app_dash.py --data-dir "outputs_baseline" --host 127.0.0.1 --port 8050
```

Para cambios visuales del dashboard no vuelvas a correr el pipeline. Usa los CSV ya generados:

```powershell
python app_dash.py --data-dir "outputs_baseline" --host 127.0.0.1 --port 8050
```

El comando corto para regenerar outputs usa por defecto el historico nuevo, `outputs_baseline` y modelo `baseline` rapido. No carga inventario para que el ciclo de Cliente 360 sea mas liviano:

```powershell
python run_mvp.py
```

Agrega inventario solo cuando vayas a trabajar compras/demanda contra disponibilidad:

```powershell
python run_mvp.py --inventario "C:/Users/elian/OneDrive - LA GAITANA FARMS SAS/Sincronizacion_PDA/basesBI/df_inventory_final.csv"
```

Solo corre el modelo estacional completo cuando quieras recalcular forecast con mas costo:

```powershell
python run_mvp.py --forecast-model seasonal_boosting --output "outputs_modelo"
```

En Bash/Git Bash, si lo escribes en varias lineas, usa `\` al final de cada linea. No mezcles este formato con PowerShell:

```bash
python run_mvp.py \
  --historico "C:/Proyectos_gaitana/Visualizador historico/historic_sales_acum.csv" \
  --output "outputs_baseline" \
  --horizon-days 14 \
  --lookback-weeks 8 \
  --forecast-model baseline
```

## Interfaz

```bash
streamlit run app_streamlit.py
```

Dashboard avanzado Cliente 360 con Dash y Plotly:

```bash
python app_dash.py --data-dir outputs --host 127.0.0.1 --port 8050
```

Luego abre en el navegador:

```text
http://127.0.0.1:8050
```

El dashboard Dash usa los CSV ya generados en `outputs/`. Si cambias la carpeta de salida en `run_mvp.py`, pasa esa carpeta con `--data-dir`.

Pestañas principales del dashboard:

- `Cliente 360`: estabilidad, score, mix, SKUs y clientes similares.
- `Clusters`: exploración de clusters y segmentos; muestra qué clientes pertenecen a cada grupo.
- `Comprador`: lista accionable de qué comprar, por prioridad, fecha, cliente, producto, variedad, color, grado y caja.
- `Demanda e inventario`: lectura de demanda futura, historico reciente y riesgos de disponibilidad. Para pedidos `SOLIDO` permite filtrar por producto, ver las 3 semanas reales previas, y comparar contra el año anterior por mismas fechas o por mismas semanas ISO.

El selector de cliente es opcional. Si se deja vacío, las pestañas trabajan con todos los clientes que cumplan los filtros de segmento, recomendación y score.

### Vista de forecast para solidos

En la pestaña `Demanda e inventario` el bloque de forecast trabaja con pedidos `SOLIDO` y agrega controles de usuario para:

- Filtrar por `producto`, por ejemplo `carnation` o `minicarnation`.
- Ver la demanda real recibida en las 3 semanas anteriores a la ventana futura seleccionada.
- Ver la demanda futura por fecha, incluyendo la semana ISO en hover y tablas.
- Ver la demanda futura agregada por semana.
- Comparar contra el año anterior de dos formas:
  - `Mismas fechas`: compara contra el rango calendario equivalente del año anterior.
  - `Mismas semanas`: compara contra las mismas semanas ISO del año anterior.

Los graficos y tablas de esta vista incluyen `fecha_semana` y/o `semana_label` para que la lectura no dependa solo de la fecha diaria.

## Outputs principales

- `estado_resumen.csv`: control de estados encontrados.
- `historico_confirmado.csv`: base real despachada usada para caracterización.
- `ordenes_pendientes_reales.csv`: órdenes reales futuras del cliente.
- `estimados_comerciales_en_proceso.csv`: estimados comerciales.
- `cambios_por_verificar_reproceso.csv`: cambios sobre confirmado.
- `perfil_cliente.csv`: perfil y score por `cod_cliente` + `cliente`.
- `clientes_similares.csv`: clientes similares con códigos.
- `forecast_historico_confirmado.csv`: baseline basado solo en histórico confirmado, usando mediana reciente por estructura y día de semana.
- `forecast_modelo_estacional.csv`: forecast robusto con boosting estacional. Usa histórico confirmado, recencia, país, ciudad, semana ISO, ventanas florales pico, cliente, producto/color, estructura operativa y rezagos históricos.
- `forecast_pendientes_reales.csv`: pendientes reales convertidos al formato de demanda futura.
- `demanda_operativa_futura.csv`: demanda final usada para inventario. Usa Pendiente primero y forecast solo donde no hay Pendiente para ese cliente/fecha. Por defecto `run_mvp.py` usa el baseline rapido; el modelo estacional queda disponible con `--forecast-model seasonal_boosting`.
- `cliente_estructuras_repetidas.csv`: tabla accionable para Cliente 360. En SOLIDO evalua SKU terminado; en SURTIDO_M evalua mezcla; en recetas evalua composicion; en BULK evalua producto-color. El clasificador normaliza cualquier `SURTIDO` legacy a `SURTIDO_M`.
- `cliente_semana_tipica.csv`: comportamiento por semana del ano para seleccionar una semana y ver estructura, mediana, promedio, comportamiento reciente, confianza y clasificacion.
- `cliente_sku_operativo_resumen.csv`: base principal del 360 para pedido tipico. SOLIDO se lee por SKU terminado exacto; surtidos/rainbow/combo/bouquet se leen como estructura operativa; BULK por producto-color.
- `cliente_sku_operativo_composicion.csv`: composicion interna de cada SKU operativo por producto, color, variedad, porcentaje, tallos/ramos promedio y estabilidad.
- `cliente_semana_sku_operativo.csv`: comportamiento semana a semana por cliente y SKU operativo para comparar repeticion, participacion y cumplimiento.
- `cruce_forecast_inventario.csv`: cruce contra disponibilidad futura.

## Nota clave

El forecast histórico no reemplaza al pedido real pendiente. Si ya existe `Pendiente` para un cliente y fecha, esa orden manda.

## Modelo de forecast

Para flujo rapido de trabajo la demanda futura usa:

```bash
--forecast-model baseline
```

El baseline es una mediana historica reciente por estructura y es el recomendado para trabajo diario rapido. El modelo `seasonal_boosting` usa `HistGradientBoostingRegressor` de scikit-learn. Ninguno aprende de `Pendiente`, `En proceso`, `Por verificar` ni `Reproceso`; solo aprenden de `Confirmado`.

Para correr el modelo estacional completo:

```bash
python run_mvp.py --forecast-model seasonal_boosting --output "outputs_modelo"
```


## Corrección v3 - tipos de pedido operativos

Esta versión diferencia explícitamente los formatos de pedido usando `TIPORDENEMPAQUE`, `TIPEMPAQUE`, `EMPAQUE` y `RECETA`.

Clasifica y exporta:

- `tipo_pedido_operativo`: `RAINBOW`, `SURTIDO_M`, `SOLIDO`, `COMBO`, `BULK`, `OTRO_NO_CLASIFICADO`. Cualquier `SURTIDO` legacy se normaliza a `SURTIDO_M`.
- `subtipo_pedido_operativo`: por ejemplo `solido_por_color`, `solido_por_variedad`, `surtido_m`, `rainbow`.
- `tipo_pedido_raw`: texto base usado para clasificar.
- `estructura_pedido`: llave de estructura de pedido para forecast y perfiles.

El forecast estructural ahora agrupa por tipo de pedido operativo además de cliente, producto, variedad, color, grado, caja, tallos por ramo, capuchón, comida y empaque. Esto evita mezclar, por ejemplo, una línea Rainbow con una línea Sólido o Surtido M aunque compartan color/producto.
