# Mapa Tecnico De Funciones

Este documento identifica los componentes del flujo activo. Los archivos de inventario/MVP se conservan como legado, pero no forman parte de la ejecucion oficial actual.

## Preparacion De Bases Historicas

**Archivo:** `src/lgf_operativo/cleaning.py`

| Funcion | Descripcion | Entradas | Salidas | Donde se usa |
|---|---|---|---|---|
| `clean_historical_orders()` | Normaliza columnas crudas, fechas, tallos, estados, tipo de pedido y llaves/SKUs operativos. | DataFrame crudo del acumulado historico. | DataFrame limpio de ordenes. | Descriptivos y forecast. |
| `build_tipo_pedido_reference()` / `attach_tipo_pedido_reference()` | Respaldo de contingencia para recuperar tipos no ambiguos solo si llega un extracto incompleto sin campos originales de receta. | Historico enriquecido anterior / referencia materializada. | Clasificacion restaurada y origen auditable. | Uso manual opcional en descriptivos y forecast. |
| `split_orders_by_estado()` | Separa confirmado, pendiente, en proceso y cambios. | Ordenes limpias. | Diccionario de DataFrames por estado. | Descriptivos. |
| `classify_tipo_pedido_operativo()` | Clasifica `SOLIDO`, `SURTIDO`, `SURTIDO_M`, `RAINBOW`, `BOUQUET`, `BQT`, `COMBO`, `BULK`, etc.; formatos especiales explicitos prevalecen sobre marcas genericas de solido y se leen como estructuras mixtas. | Lineas normalizadas. | Variables de tipo operativo y fuente de clasificacion. | Todos los analisis operativos. |

**Regla de entrada:** la fuente cruda canonica es `bases de datos historicas/historic_sales_acum.csv` con campos originales de receta y estructura. La clasificacion normal se hace directamente desde esa fuente y no requiere un ejecutor adicional de referencia tipologica.

## Generacion De Descriptivos

**Ejecutor:** `run_descriptivos.py`  
**Modulo:** `src/lgf_operativo/descriptive.py`

| Funcion | Descripcion | Entradas | Salidas | Donde se usa |
|---|---|---|---|---|
| `run_descriptive_pipeline()` | Ejecuta limpieza, filtro temporal opcional, perfiles, mixes, SKUs y estructuras. | Ruta historica, `analysis_year` o `analysis_years`, carpeta de salida. | CSV/XLSX en `resultados/descriptivos/`. | Visualizador y estructuras; entrada para clusters. |
| `_load_or_clean_historical()` | Reutiliza cache de limpieza para evitar reprocesar la base cruda. | DataFrame crudo/ruta/cache. | Ordenes limpias. | Interno del descriptivo. |
| `build_operational_structure_tables()` | Resume la orden regular por cliente, semana y version de estructura; conserva repeticiones y composicion sin materializar cada linea historica repetida. | Historico confirmado limpio. | `estructura_caja.csv`, `estructura_componentes.csv`, `catalogo_estructura_version.csv`. | Pestana Estructuras y componentes. |

**Outputs importantes:** `historico_confirmado.csv`, `historico_visualizador_comercial.csv`, `perfil_cliente.csv`, `ventas_semana_cliente_producto.csv`, `estructura_caja.csv`, `estructura_componentes.csv`.
`historico_confirmado.csv` preserva `pais`, requerido para clasificar los cinco
mercados antes de entrenar clusters.
`historico_visualizador_comercial.csv` agrega las lineas con valor monetario
aunque no transporten tallos; se usa solo para ventas y precio promedio en el
visualizador cuando factura y composicion fisica vienen en lineas distintas.
`estructura_caja.csv` y `estructura_componentes.csv` son salidas compactas
para el dashboard: cada fila resume una estructura/version observada en una
semana y sus contadores preservan la cantidad real de pedidos representados.

## Generacion De Clusters

**Ejecutor:** `run_clusters.py`  
**Modulo:** `src/lgf_operativo/clustering.py`

| Funcion / Clase | Descripcion | Entradas | Salidas | Donde se usa |
|---|---|---|---|---|
| `ClusterConfig` | Parametros de k, pesos de bloques y evaluacion. | Configuracion opcional. | Configuracion inmutable. | Pipeline clusters. |
| `classify_market()` | Separa los cinco mercados definidos por negocio. | Pais. | Mercado. | Clusters y forecast. |
| `build_client_clustering_dataset()` | Crea atributos por cliente: constancia, volumen, composicion, formato y cumplimiento; agrega ventas, tendencia reciente, participacion de mercado y complejidad para lectura ejecutiva. | Historico confirmado con `pais` y perfil. | Base modelable y descriptiva por cliente. | Modelos cluster/Dash. |
| `run_cluster_pipeline()` | Evalua K-medias, K-modas y jerarquico dentro de cada mercado; genera explicaciones y similares. | Historico descriptivo filtrado al `--year` requerido por el ejecutor. | CSV/XLSX en `resultados/clusters/<ano>/`. | Pestaña Clusters. |

**Ventana temporal:** `run_clusters.py` exige `--year`. Filtra
`historico_confirmado.csv` al ano seleccionado y recalcula el perfil sobre ese
mismo ano, aunque descriptivos contenga toda la historia. Además exporta
`cluster_periodo_analisis.csv` para auditoria. El Dash descubre las carpetas
anuales y el filtro `Ano de cluster` cambia el conjunto de resultados cargado.
Las variables comerciales agregadas se muestran como caracterizacion y no
alteran los pesos actuales del modelo de segmentacion.

## Visualizador General De Clientes

**Archivo:** `app_dash.py`

| Funcion | Descripcion | Entradas | Salidas |
|---|---|---|---|
| `load_data()` | Lee separadamente descriptivos, clusters y forecast. | Tres carpetas de resultados. | Diccionario de DataFrames. |
| `render_visualizador_clientes_general()` | Presenta historico, ventas, SKUs y composicion del cliente. | Filtros de cliente, producto, color, periodo y metricas. | Componentes Dash. |
| `filter_visual_operational_base()` | Aplica filtros operativos del visualizador. | Historico y selecciones. | Base filtrada. |

## Ventas Generales

**Archivo:** `app_dash.py`
**Fuente:** `resultados/descriptivos/ventas_semana_cliente_producto.csv`

| Funcion | Descripcion | Entradas | Salidas |
|---|---|---|---|
| `filter_general_sales_frame()` | Filtra el agregado comercial semanal sin consultar receta, SKU ni estructura de caja. | Anos, semanas, clientes y productos. | Ventas agregadas filtradas. |
| `render_ventas_generales_tab()` | Presenta tallos confirmados, ventas USD y precio promedio ponderado con graficas semanales y resumen anual. | Tabla agregada y filtros minimos. | Vista Dash ligera. |

Esta pestana se usa para control general rapido. El precio se calcula como
`ventas_usd / tallos_confirmados`; no es el promedio simple de precios por
linea. Para analizar color, SKU o composicion se utiliza el visualizador
detallado.

## Estructuras Y Componentes

**Archivo:** `app_dash.py`

| Funcion | Descripcion | Entradas | Salidas |
|---|---|---|---|
| `render_estructuras_componentes_tab()` | Identifica la orden base mas repetida y sus componentes habituales. | Cliente seleccionado y filtros del visualizador. | Vista resumida de orden regular. |

Esta pestaña no muestra cada caja como objetivo principal; se limita a explicar la estructura regular del cliente.

## Forecast Solidos Historico

**Ejecutor:** `run_forecast_solidos.py`  
**Modulo:** `src/lgf_operativo/solid_forecast.py`

| Funcion / Clase | Descripcion | Entradas | Salidas | Donde se usa |
|---|---|---|---|---|
| `_load_raw_solids()` | Limpia por bloques y cachea solidos historicos; filtra confirmados si existe estado y asume historia observada si el acumulado de ventas no lo informa. | Base cruda acumulada. | DataFrame compacto de solidos. | Ejecutable forecast. |
| `SolidForecastConfig` | Configura test, horizonte y controles de series. | Parametros CLI. | Configuracion. | Pipeline forecast. |
| `build_solid_weekly_demand()` | Agrega tallos por cliente, mercado, pais, producto, color y semana. | Solidos confirmados. | Serie semanal. | Modelos. |
| `evaluate_solid_forecast_models()` | Compara baseline, anual, boosting e hibrido estacional; el boosting incorpora fases pre/pico/post-fiesta e indice estacional mercado-producto-color, y corrige la retransformacion logaritmica con informacion exclusiva de entrenamiento. | Serie semanal. | Metricas, predicciones e importancias. | Dash/notebook. |
| `build_future_solid_forecast()` | Genera hasta ocho semanas futuras con el modelo seleccionado; el Dash permite visualizar horizontes de 2, 5 u 8 semanas. | Serie y modelo elegido. | Pronostico futuro. | Dash. |
| `build_market_volume_calibration()` | Detecta subpronostico consistente por mercado en dos mitades del backtest y define ajuste acotado. | Predicciones de test del modelo usado. | Factor y lectura por mercado. | Forecast/Dash. |
| `apply_market_volume_calibration()` | Corrige el nivel futuro solo en mercados con evidencia sostenida de subpronostico. | Pronostico base y calibracion. | Forecast comercial ajustado. | Dash. |
| `apply_floral_seasonal_overlay()` | Refuerza solo preparacion/pico floral con la misma semana del ano anterior ajustada por tendencia; excluye salida post-fiesta para preservar la caida aprendida por el modelo. | Forecast calibrado y anclas estacionales. | Pronostico con ajuste floral trazable. | Dash. |
| `build_historical_seasonal_validation()` | Simula temporadas pasadas usando solo senales conocidas antes del ano evaluado; el Dash permite medir ventanas de 2, 5 u 8 semanas con referencia anual disponible. | Serie semanal. | `solid_forecast_historical_validation.csv`. | Dash/notebook. |
| `run_solid_forecast_pipeline()` | Coordina la corrida completa y exportaciones. | Historico confirmado SOLIDO. | CSV/XLSX en `resultados/forecast_solidos/`. | Dashboard. |

El boosting es de dos etapas:

- `probabilidad_compra`: si el cliente compra el producto-color en la semana.
- `volumen_si_compra`: tallos esperados condicionados a compra.

La etapa de volumen recupera tallos desde escala logaritmica con una correccion
de retransformacion calculada solamente en entrenamiento. Esta regla busca
reducir el sesgo a la baja en volumen agregado sin contaminar el test.

La estacionalidad no se representa solo con un indicador de fiesta: el modelo
recibe la fase comercial de la temporada, si la semana ocurre despues del
pico, la distancia al pico y el nivel semanal habitual del producto-color en
su mercado. Esto permite aprender el descenso posterior a San Valentin,
Madres o fin de ano sin aplicar una reduccion manual a la prediccion.

El Dash muestra notas ejecutivas, importancia de variables por mercado,
ajuste de nivel aplicado y validacion retrospectiva de ventanas seleccionables
de 2, 5 u 8 semanas para inspeccionar fiestas ya ocurridas. La importancia por
mercado evalua el mismo modelo general dentro de cada mercado; no corresponde
a modelos independientes.

## Dashboard Principal

**Ejecutor:** `app_dash.py`

| Funcion | Descripcion |
|---|---|
| `build_app()` | Construye layout, pestañas y callbacks con carpetas modulares. |
| `render_ventas_generales_tab()` | Presenta el control comercial rapido desde el agregado semanal de ventas. |
| `render_clusters_tab()` | Prioriza resumen ejecutivo, diferencias contra el mercado, clientes representativos/similares y acciones; conserva el detalle metodologico en una seccion avanzada. |
| `render_forecast_solidos_tab()` | Organiza alcance, proyeccion, historia comparativa, validacion, escenario y explicabilidad; visualiza horizonte futuro filtrable y validacion retrospectiva de 2, 5 u 8 semanas. |
| `render_reserved_module()` | Mantiene pestañas de inventario creadas, sin activar analisis no disponible. |

Argumentos:

- `--data-dir`: resultados descriptivos.
- `--clusters-dir`: resultados de clusters.
- `--forecast-dir`: resultados de forecast solidos.

## Utilidades

**Archivo:** `src/lgf_operativo/io_utils.py`

| Funcion | Descripcion |
|---|---|
| `read_table()` | Lectura comun de CSV/TXT/XLSX. |
| `resolve_path()` | Resuelve archivos o carpetas de entrada. |
| `write_outputs()` | Escribe CSV completos y Excel liviano para revision. |

## Componentes Conservados Pero Fuera Del Flujo Activo

| Archivo / Vista | Estado |
|---|---|
| `run_mvp.py` y `src/lgf_operativo/pipeline.py` | Legado del MVP con inventario; conservar para una fase futura, no ejecutar en el flujo oficial actual. |
| `render_comprador_tab()` | Implementacion previa no expuesta funcionalmente; la pestaña muestra reserva hasta tener inventario proyectado. |
| `render_demanda_tab()` / `render_colores_tab()` | Logica previa no activa en el menu actual; forecast reemplaza la lectura de colores proyectados. |
| `render_cliente_tab()` | Vista anterior no activa; el visualizador general es la vista descriptiva oficial. |
