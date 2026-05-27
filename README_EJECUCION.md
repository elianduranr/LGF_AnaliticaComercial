# Ejecucion Del Proyecto LGF

## Flujo Activo

El proyecto se ejecuta en modulos independientes:

```text
bases de datos historicas/historic_sales_acum.csv
        |
        +-- run_descriptivos.py ------> resultados/descriptivos/
        |                                  |
        |                                  +-- run_clusters.py ------> resultados/clusters/
        |
        +-- run_forecast_solidos.py ---> resultados/forecast_solidos/

app_dash.py consume resultados/descriptivos, resultados/clusters y resultados/forecast_solidos.
```

La carpeta obligatoria de entrada es:

```text
bases de datos historicas/
  historic_sales_acum.csv
```

Esta carpeta ya existe en el proyecto. Las bases anuales pueden conservarse como respaldo, pero el flujo usa el archivo acumulado para evitar duplicar ventas.

El acumulado oficial debe conservar los campos originales que distinguen
recetas y surtidos (`TIPORDENEMPAQUE`, `EMPAQUE`, `RECETA`, `BULKBOUQUET`,
componentes y cantidades operativas). La clasificacion se obtiene directamente
de esos campos. Los formatos con marca explicita `BQT`, `COMBO` o `RAINBOW`
se mantienen visibles y se analizan como estructuras mixtas.

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

No existe actualmente un script ETL independiente de preparacion. La limpieza se ejecuta dentro de los modulos existentes:

- `run_descriptivos.py` limpia la base historica completa, clasifica tipos desde los campos fuente y genera perfiles/SKUs.
- `run_forecast_solidos.py` limpia y cachea exclusivamente los pedidos `SOLIDO` historicos necesarios para forecast; si la fuente incluye estado filtra `Confirmado`, y si el acumulado de ventas no trae estado interpreta sus lineas como historia observada. Excluye estructuras mixtas como `SURTIDO`, `SURTIDO_M`, `RAINBOW`, `BOUQUET`, `BQT` y `COMBO`.

Validar que la entrada exista:

```bash
ls "bases de datos historicas/historic_sales_acum.csv"
```

Pendiente recomendable para una fase posterior: crear un ejecutor `run_preparacion_historica.py` que materialice una unica base limpia reutilizable. No se crea ahora porque implicaria cambiar el contrato de los modulos que ya funcionan.

No se debe ejecutar ninguna referencia tipologica adicional con la base
completa. El flujo oficial clasifica directamente desde los campos originales
de receta y estructura conservados en `historic_sales_acum.csv`.

## 2. Generacion De Descriptivos

Descriptivos puede contener toda la historia o los anos que se desean explorar
en el Visualizador general y Estructuras. Para trabajar con toda la base
historica, omite filtros de ano:

```bash
python run_descriptivos.py \
  --historico "bases de datos historicas/historic_sales_acum.csv" \
  --output "resultados/descriptivos"
```

Para restringir descriptivos a anos seleccionados:

```bash
python run_descriptivos.py \
  --historico "bases de datos historicas/historic_sales_acum.csv" \
  --output "resultados/descriptivos" \
  --years 2023 2024
```

Para una sola ventana anual tambien se admite:

```bash
python run_descriptivos.py \
  --historico "bases de datos historicas/historic_sales_acum.csv" \
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

`historico_confirmado.csv` conserva `pais`. Esta columna es obligatoria para
que el modulo de clusters asigne cada cliente a Estados Unidos/Canada, The
Netherlands, Polonia, Asia u Otros antes de agruparlo.

`historico_visualizador_comercial.csv` conserva tambien lineas monetarias sin
tallos cuando un cliente registra el valor de venta separado de los componentes
fisicos del pedido. Esta tabla alimenta tarjetas de ventas y precio del
Visualizador general; no alimenta clusters, estructuras ni forecast.

`estructura_caja.csv` y `estructura_componentes.csv` son tablas resumidas
para la vista de orden regular: consolidan por cliente, semana y version de
estructura, conservando tallos y el numero de repeticiones originales. No son
un reemplazo del detalle transaccional en `historico_confirmado.csv`.

## 3. Generacion De Clusters

Clusters siempre exige seleccionar un unico ano. Puede consumir
`resultados/descriptivos/` aunque esa carpeta tenga toda la historia: antes de
modelar filtra el ano solicitado y recalcula el perfil del cliente dentro del
mismo ano.

```bash
python run_clusters.py \
  --input-dir "resultados/descriptivos" \
  --year 2024
```

La salida se guarda automaticamente en `resultados/clusters/2024/`. Cuando la
base incorpore un nuevo ano, por ejemplo `--year 2025`, se creara
`resultados/clusters/2025/` sin sobrescribir la corrida anterior.

Para generar todos los anos historicos disponibles actualmente para el
selector del dashboard:

```bash
for anio in 2021 2022 2023 2024; do
  python run_clusters.py \
    --input-dir "resultados/descriptivos" \
    --year "$anio"
done
```

Salidas consumidas por la pestaña `Clusters`:

- `clusters_clientes.csv`
- `cluster_model_evaluation.csv`
- `cluster_resumen.csv`
- `cluster_variables_diferenciadoras.csv`
- `cluster_perfil_bloques.csv`
- `cluster_periodo_analisis.csv`
- `clientes_similares.csv`

La salida de clusters incluye, ademas del perfil usado por el modelo,
descriptores ejecutivos para el Dash: ventas USD, participacion de tallos en
el mercado, variacion de las ultimas ocho semanas frente a las ocho previas y
complejidad operativa. Estos campos describen el segmento; no cambian por si
solos el peso de la geometria del cluster.

### Criterio Recomendado Para Anos

Los clusters describen tipos de cliente, no demanda futura. Para presentacion
e interpretacion comercial se calculan siempre sobre un ano coherente y
explicito, porque evita mezclar clientes o portafolios que cambiaron entre anos.

Recomendacion operativa:

- Descriptivos: cargar todos los anos que se quieren consultar en el dashboard.
- Clusters: ejecutar `--year ANO` para el ano que se quiere caracterizar comercialmente.
- Comparacion de estabilidad: ejecutar cada ano requerido; el script lo guarda bajo `resultados/clusters/<ano>/`.
- El dashboard lee todas las carpetas anuales dentro de `--clusters-dir` y permite cambiar el ano con el filtro `Ano de cluster`.

No se calcula un cluster multianual para presentarlo como anual: el ejecutor
impide esa ambiguedad al requerir `--year`.

Si se corrige una base anual de origen, se deben volver a ejecutar primero los
descriptivos y luego los clusters de los anos que se quieran actualizar. No se
excluye automaticamente ningun ano del flujo.

## 4. Forecast Solidos Historico

El forecast es el unico modulo activo que usa de forma oficial toda la historia consolidada:

```bash
python run_forecast_solidos.py \
  --raw-historico "bases de datos historicas/historic_sales_acum.csv" \
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

Luego de ejecutar los tres modulos:

```bash
python app_dash.py \
  --data-dir "resultados/descriptivos" \
  --clusters-dir "resultados/clusters" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8050
```

Abrir:

```text
http://127.0.0.1:8050/
```

### Flujo Completo Recomendado

Este es el flujo para ver toda la historia en descriptivos, clusters del ano
elegido y forecast historico completo:

```bash
python run_descriptivos.py \
  --historico "bases de datos historicas/historic_sales_acum.csv" \
  --output "resultados/descriptivos" \
  --no-cache

for anio in 2021 2022 2023 2024; do
  python run_clusters.py \
    --input-dir "resultados/descriptivos" \
    --year "$anio"
done

python run_forecast_solidos.py \
  --raw-historico "bases de datos historicas/historic_sales_acum.csv" \
  --output "resultados/forecast_solidos" \
  --test-weeks 8 \
  --horizon-weeks 8 \
  --no-cache

python app_dash.py \
  --data-dir "resultados/descriptivos" \
  --clusters-dir "resultados/clusters" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8050
```

### Abrir La Corrida Validada Ya Migrada

La corrida validada de descriptivos y forecast historico ya se encuentra bajo la estructura canonica. Para usar el selector anual, genera al menos una corrida con `run_clusters.py --year ANO` dentro de `resultados/clusters/<ano>/`.

```bash
python app_dash.py \
  --data-dir "resultados/descriptivos" \
  --clusters-dir "resultados/clusters" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8067
```

Las nuevas corridas sobrescriben o regeneran estos resultados mediante los scripts de cada modulo.

Pestanas activas:

- `Visualizador clientes general`: descriptivo principal.
- `Ventas generales`: control rapido de tallos confirmados, ventas USD y precio promedio ponderado, filtrable por ano, semana, cliente y producto; consume `ventas_semana_cliente_producto.csv` y evita el detalle operativo pesado.
- `Estructuras y componentes`: orden regular resumida del cliente seleccionado.
- `Clusters`: caracterizacion por mercado.
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
| `resultados/descriptivos/` | Generada activa | Visualizador y estructuras. |
| `resultados/clusters/` | Generada activa | Pestaña Clusters. |
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
