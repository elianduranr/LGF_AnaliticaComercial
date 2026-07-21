# Ejecucion Del Proyecto LGF

## Flujo Activo

El proyecto se ejecuta en modulos independientes:

```text
SQL Server 192.168.1.22 / op_sales.fact_sales_line
        |
        +-- run_descriptivos.py ------> resultados/descriptivos/
        |
        +-- run_forecast_solidos.py ---> resultados/forecast_solidos/

app_dash.py consume resultados/descriptivos, vistas `op_sales` y resultados/forecast_solidos.
```

Para despliegue local con SQL Server no se suben los CSV historicos pesados a
GitHub. La maquina de ejecucion debe tener acceso a `192.168.1.22`, base
`gaitana`, schema `op_sales`, y el driver ODBC de SQL Server instalado.

Si la maquina usa autenticacion integrada de Windows, no hace falta definir
usuario ni clave. Si usa autenticacion SQL, las credenciales se guardan en
`configurar_credenciales.local.ps1`; el lanzador Bash lee ese archivo y exporta
las variables necesarias sin imprimirlas en la terminal.

Desde Git Bash o la terminal Bash de Visual Studio Code, el dashboard debe
abrirse en modo SQL con:

```bash
cd /c/Proyectos_gaitana/lgf_operativo_project
bash ./run_dash_sql.sh
```

Luego abrir `http://localhost:8085/` en el navegador. El proceso permanece
activo en esa terminal; para detenerlo se usa `Ctrl+C`.

La carpeta local de respaldo/carga inicial es:

```text
bases de datos historicas/
  historic_sales_acum.csv
```

Esta carpeta ya existe en el proyecto. Las bases anuales pueden conservarse como respaldo, pero el flujo oficial carga el acumulado en SQL Server y luego lee `op_sales.fact_sales_line`.

El acumulado oficial debe conservar los campos originales del sistema. Para
`tipo_pedido_operativo`, la unica fuente autorizada es `TIPEMPAQUE`
(`tipo_empaque` en el modelo canonico). No se infiere desde `EMPAQUE`,
`TIPORDENEMPAQUE`, `RECETA`, `BULKBOUQUET`, codigos de caja ni referencias
historicas.

La regla aplicada es deliberadamente directa:

- `solido por variedad` y `solido por color` se consolidan como `SOLIDO`.
- Los demas valores conservan el nombre del sistema: `SURTIDO "M"`, `BOUQUET`,
  `COMBO`, `RAINBOW` y `BQT`.
- Si el sistema incorpora un valor nuevo, este se conserva visible; el pipeline
  no intenta adivinar otra clasificacion.

`TIPORDENEMPAQUE` se conserva como atributo independiente de la orden
(`regular`, `adicional`, `fija`, etc.), pero nunca define el tipo operativo.

## Terminal Bash

Todos los comandos siguientes estan preparados para Git Bash o la terminal Bash de Visual Studio Code en Windows:

```bash
cd /c/Proyectos_gaitana/lgf_operativo_project
```

Si `python` no resuelve el entorno del proyecto, reemplazalo por:

```bash
./carac_clients/Scripts/python.exe
```

## 1. Preparacion De Bases Historicas

La preparacion oficial empieza cargando el acumulado local en SQL Server:

```bash
python cargar_op_sales_sql.py --init-schema

python cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17 \
  --split-by month
```

Para validar antes sin escribir en SQL:

```bash
python cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17 \
  --dry-run
```

Luego:

- `run_descriptivos.py` lee `op_sales.fact_sales_line`, toma el tipo operativo exclusivamente de `tipo_empaque` y genera perfiles/SKUs.
- `run_forecast_solidos.py` lee `op_sales.fact_sales_line` y conserva exclusivamente pedidos `SOLIDO` historicos necesarios para forecast.

Validar que la entrada exista:

```bash
ls "bases de datos historicas/historic_sales_acum.csv"
```

Pendiente recomendable para una fase posterior: crear un ejecutor `run_preparacion_historica.py` que materialice una unica base limpia reutilizable. No se crea ahora porque implicaria cambiar el contrato de los modulos que ya funcionan.

No se debe ejecutar ninguna referencia tipologica adicional. El flujo oficial
usa exclusivamente `TIPEMPAQUE` para el tipo operativo y conserva por separado
los campos de receta, empaque y estructura para sus respectivos analisis.

## 2. Generacion De Descriptivos

Descriptivos puede contener toda la historia o los anos que se desean explorar
en el Visualizador general y Estructuras. Para trabajar con toda la base
historica, omite filtros de ano:

```bash
python run_descriptivos.py \
  --output "resultados/descriptivos"
```

Para restringir descriptivos a anos seleccionados:

```bash
python run_descriptivos.py \
  --output "resultados/descriptivos" \
  --years 2023 2024
```

Para una sola ventana anual tambien se admite:

```bash
python run_descriptivos.py \
  --output "resultados/descriptivos" \
  --year 2024
```

Salidas principales consumidas por el Dash:

- `perfil_cliente.csv`
- `historico_confirmado.csv`
- `historico_visualizador_comercial.csv`
- `ventas_semana_cliente_producto.csv`
- `cliente_sku_operativo_resumen.csv`
- `cliente_sku_operativo_composicion.csv`
- `estructura_caja.csv`
- `estructura_componentes.csv`

`historico_confirmado.csv` conserva `pais` para lectura comercial y forecast.

`historico_visualizador_comercial.csv` conserva tambien lineas monetarias sin
tallos cuando un cliente registra el valor de venta separado de los componentes
fisicos del pedido. Esta tabla alimenta tarjetas de ventas y precio del
Visualizador general; no alimenta estructuras ni forecast.

`estructura_caja.csv` y `estructura_componentes.csv` son tablas resumidas
para la vista de orden regular: consolidan por cliente, semana y version de
estructura, conservando tallos y el numero de repeticiones originales. No son
un reemplazo del detalle transaccional en `historico_confirmado.csv`.

## 3. Modulo De Clusters Archivado

Clusters queda fuera del flujo master actual. Su codigo, notebook, informe,
presentacion y resultados historicos se conservan en:

```text
pruebas antiguas/cluster_archivado_2026-06-09/
```

No se ejecuta en el dashboard ni en el flujo recomendado mientras no vuelva a
ser una prioridad del proyecto.

## 4. Forecast Solidos Historico

El forecast es el unico modulo activo que usa de forma oficial toda la historia consolidada:

```bash
python run_forecast_solidos.py \
  --output "resultados/forecast_solidos" \
  --test-weeks 8 \
  --horizon-weeks 8
```

Alcance:

- Pedidos `Confirmado` cuando la fuente informa estado; en el acumulado de ventas sin estado, todas las lineas representan historia observada.
- Solo tipo `SOLIDO`.
- Unidad pronosticada: `cliente + mercado + pais + producto + color + semana`.
- Modelos evaluados: baseline reciente, estacional anual y boosting de ocurrencia/volumen.
- La etapa de volumen del boosting se estima en escala logaritmica y aplica una correccion de retransformacion aprendida exclusivamente en entrenamiento. El objetivo es reducir subpronostico agregado en picos sin usar informacion futura.
- Para boosting, se revisa el sesgo de volumen por mercado en dos mitades temporales del backtest. Solo se aplica calibracion si el subpronostico es sostenido.
- La calibracion corrige el nivel de tallos futuro del mercado; la composicion por cliente, producto y color sigue proviniendo del modelo.
- El boosting incorpora fases de temporada floral (`preparacion`, `pico` y `post-fiesta`), distancia al pico e indice estacional semanal por mercado-producto-color, calculados solo con historia disponible antes del corte.
- En preparacion o pico floral, el forecast puede reforzar el nivel con la misma semana del ano anterior ajustada por tendencia historica del mercado. Las semanas posteriores no reciben ese refuerzo para que el modelo capture la caida historica; la regla se recalcula al agregar anos.
- El pipeline materializa hasta ocho semanas futuras y el dashboard permite mostrar solo `2`, `5` u `8` semanas segun la decision comercial.
- La validacion retrospectiva estacional permite escoger ano, inicio y duracion (`2`, `5` u `8` semanas). Solo habilita ventanas completas con ano anterior comparable, y calcula WAPE y bias sobre esa ventana, no sobre el ano agregado.

Salidas principales:

- `solid_forecast_model_evaluation.csv`
- `solid_forecast_test_predictions.csv`
- `solid_forecast_future.csv`
- `solid_forecast_feature_importance.csv`
- `solid_forecast_market_feature_importance.csv`
- `solid_forecast_market_calibration.csv`
- `solid_forecast_historical_validation.csv`
- `solid_forecast_predictors.csv`

## 5. Dashboard

Para abrir localmente la corrida disponible en modo SQL:

```bash
bash ./run_dash_sql.sh
```

Abrir:

```text
http://localhost:8085/
```

El lanzador selecciona automaticamente `.venv`, `carac_clients`, el entorno
`SDG_env` o el `python` disponible. Tambien carga
`configurar_credenciales.local.ps1` y consume los resultados de
`resultados/descriptivos` y `resultados/forecast_solidos`.

Si se necesita ejecutar `app_dash.py` directamente y elegir otro puerto:

```bash
python app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8050
```

En ese caso abrir:

```text
http://127.0.0.1:8050/
```

### Flujo Completo Recomendado

Este es el flujo para ver toda la historia en descriptivos y forecast historico
completo:

```bash
python run_descriptivos.py \
  --output "resultados/descriptivos" \
  --no-cache

python run_forecast_solidos.py \
  --output "resultados/forecast_solidos" \
  --test-weeks 8 \
  --horizon-weeks 8 \
  --no-cache

python app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8050
```

### Abrir La Corrida Validada Ya Migrada

La corrida validada de descriptivos y forecast historico ya se encuentra bajo la estructura canonica.

```bash
python app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8067
```

Las nuevas corridas sobrescriben o regeneran estos resultados mediante los scripts de cada modulo.

Pestanas activas:

- `Visualizador clientes general`: descriptivo principal.
- `Ventas generales`: control rapido de tallos confirmados, ventas USD y precio promedio ponderado, filtrable por ano, semana, cliente y producto; consume `ventas_semana_cliente_producto.csv` y evita el detalle operativo pesado.
- `Fletes`: control de flete CIF/DEL/total, flete por tallo y FOB estimado desde la tabla distribuida de fletes.
- `Forecast solidos historico`: estacionalidad, validacion, explicabilidad y escenarios.

En `Forecast solidos historico`, los controles se separan por efecto:
`Alcance comercial` modifica todas las lecturas filtradas; `Proyeccion futura`
define las semanas proyectadas visibles; `Historia comparativa` solo modifica
las lineas reales de referencia; `Validacion historica` calcula WAPE y bias de
una ventana pasada; y `Escenario comercial` simula ajustes sin reentrenar.

Pestanas reservadas:

- `Comprador`: pendiente de proyeccion de inventario.
- `Demanda e inventario`: pendiente de proyeccion de inventario.

## Estructura De Carpetas

| Carpeta | Estado | Uso |
|---|---|---|
| `bases de datos historicas/` | Obligatoria | Archivos crudos; no editar mediante el Dash. |
| `resultados/descriptivos/` | Generada activa | Visualizador y salidas descriptivas internas. |
| `resultados/forecast_solidos/` | Generada activa | Pestaña Forecast. |
| `notebooks/` | Documentacion analitica | Metodologias para estudio/revision. |
| `pruebas antiguas/` | Archivo legado | Corridas anteriores o pruebas 2026; fuera del flujo oficial. |

## Depuracion De Outputs Anteriores

La corrida vigente fue migrada a `resultados/`. Las siguientes carpetas de corridas reemplazadas fueron retiradas de la raiz y archivadas en `pruebas antiguas/`:

```text
pruebas antiguas/outputs/
pruebas antiguas/outputs_baseline/
pruebas antiguas/outputs_clusters_2026/
pruebas antiguas/outputs_descriptivo/
pruebas antiguas/outputs_descriptivo_2026_demo/
pruebas antiguas/outputs_descriptivo_2026_pipeline/
pruebas antiguas/outputs_forecast_solidos_2026/
```

No editar manualmente archivos en `resultados/` ni en caches `_cache/`; se regeneran con sus scripts. No usar `pruebas antiguas/` como entrada del Dash salvo para auditoria puntual de corridas previas.
