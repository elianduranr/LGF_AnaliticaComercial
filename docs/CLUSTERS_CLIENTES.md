# Clusters de clientes por mercado

> Nota de mantenimiento: el flujo oficial actualizado utiliza
> `resultados/descriptivos/` y `resultados/clusters/`, segun
> `README_EJECUCION.md`. Las rutas `outputs_*_2026` de este documento
> registran la corrida de validacion original y no deben usarse como nombres
> de salida para nuevas ejecuciones.

Este modulo queda separado del descriptivo. Usa los CSV limpios ya generados por el descriptivo 2026 o por el MVP, pero escribe sus propios outputs en una carpeta independiente.

## Objetivo

Agrupar clientes parecidos dentro de mercados definidos previamente:

- `01_ESTADOS_UNIDOS_CANADA`
- `02_THE_NETHERLANDS`
- `03_POLONIA`
- `04_ASIA`
- `05_OTROS`

La decision funcional es importante: no se comparan clientes globalmente antes de separar mercado, porque cada mercado tiene comportamientos comerciales, empaques y composiciones distintas.

## Variables usadas y ponderacion

El modelo no usa solo las variables sugeridas inicialmente. Se construye un perfil operativo por cliente y se agrupa por bloques:

- frecuencia y constancia: semanas activas, porcentaje de semanas activas, recencia cuando existe en `perfil_cliente`;
- volumen: tallos totales, promedio y mediana semanal;
- estabilidad: coeficiente de variacion semanal;
- cumplimiento: tallos confirmados contra tallos pedidos/analisis;
- composicion: concentracion de color, producto, tipo de pedido, SKU y empaque;
- complejidad: entropia de color, producto, tipo de pedido y SKU;
- formato operativo: tallos por ramo, ramos por caja, tipo de caja dominante;
- dominantes interpretables: producto, color, tipo de pedido y caja mas representativos.

La matriz de clustering pondera mas fuerte:

- composicion y concentracion de colores;
- composicion y concentracion de productos;
- tipo de pedido operativo: `SOLIDO`, `SURTIDO_M`, `RAINBOW`, `COMBO`, `BOUQUET`, `BULK`;
- constancia del cliente.

SKUs y empaques se mantienen como variables resumidas y explicativas, pero no dominan la geometria del cluster porque son demasiado granulares para tomar decisiones comerciales generales.

## Metodos evaluados

Por cada mercado se prueban:

- K-medias: sobre variables numericas y participaciones de mix.
- K-modas: sobre variables categoricas dominantes.
- Clustering jerarquico: sobre variables numericas y participaciones de mix.

Para cada metodo se prueba `k` desde 2 hasta `--max-k`, limitado por el numero de clientes del mercado. La seleccion usa `silhouette`, pero penaliza soluciones poco utiles: clusters de un solo cliente y soluciones donde un cluster absorbe casi todo el mercado.

Si un mercado tiene pocos clientes, se marca como `SIN_CLUSTER`.

## Comando

```powershell
python run_clusters.py --input-dir "resultados/descriptivos" --year 2026
```

Tambien puede correrse sobre outputs descriptivos sin sufijo:

```powershell
python run_clusters.py --input-dir "resultados/descriptivos" --year 2026
```

## Outputs

- `cluster_features_cliente.csv`: base modelable, una fila por cliente.
- `cluster_model_evaluation.csv`: comparacion de K-medias, K-modas y jerarquico por mercado y k.
- `clusters_clientes.csv`: asignacion final de cliente a mercado, metodo, k y cluster.
- `cluster_resumen.csv`: lectura agregada de cada cluster.
- `cluster_variables_diferenciadoras.csv`: variables que diferencian cada cluster contra el promedio de su mercado.
- `cluster_perfil_bloques.csv`: bloque principal que explica cada cluster: color, producto, tipo de pedido, constancia, etc.
- `clientes_similares.csv`: clientes mas parecidos dentro del mismo mercado.
- `LGF_Clusters_Clientes.xlsx`: resumen liviano para revisar en Excel.

## Dashboard

La pestana `Clusters` del Dash lee `clusters_clientes.csv`, `cluster_resumen.csv`, `cluster_model_evaluation.csv` y `clientes_similares.csv`.

Para explorar solo clustering:

```powershell
python app_dash.py --data-dir "resultados/descriptivos" --clusters-dir "resultados/clusters" --forecast-dir "resultados/forecast_solidos" --host 127.0.0.1 --port 8050
```

Para explorar clustering junto con el visualizador descriptivo 2026:

```powershell
python run_clusters.py --input-dir "resultados/descriptivos" --year 2026
python app_dash.py --data-dir "resultados/descriptivos" --clusters-dir "resultados/clusters" --forecast-dir "resultados/forecast_solidos" --host 127.0.0.1 --port 8054
```

Las carpetas `resultados/clusters/<ano>/` no contienen los CSV descriptivos; por eso su carpeta raiz debe pasarse en `--clusters-dir`, mientras `--data-dir` apunta a `resultados/descriptivos`.
