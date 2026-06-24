# Diccionario de datos

Base versionada para la entrega:

- `raw/ventas_facturadas_muestra_2021_2026.csv`

La muestra proviene de las bases historicas locales `ventas_facturadas_2021.csv`
a `ventas_facturadas_2026.csv`. El EDA del notebook usa la base cruda completa;
esta muestra queda para Git/DVC.

| Campo | Uso en el proyecto |
|---|---|
| `fecha` | Fecha base para ordenar la demanda y construir semanas de pronostico. |
| `semana`, `semana_iso` | Semana de la venta/pedido; permite agregacion semanal. |
| `anio`, `AÃ‘O` | Ano calendario de analisis. |
| `mes` | Mes de la demanda, util para revisar estacionalidad. |
| `cod_cliente` | Identificador del cliente. |
| `cliente` | Nombre del cliente. |
| `pais` | Pais destino; sirve para segmentar demanda por mercado. |
| `producto` | Tipo de flor o producto comercial. |
| `color` | Color comercial; variable clave para forecast de demanda. |
| `variedad` | Variedad especifica dentro de producto/color. |
| `tipo_orden_empaque` | Campo usado para identificar pedidos SOLIDO. |
| `tipo_empaque` | Tipo de empaque reportado por la fuente. |
| `empaque` | Descripcion operativa del empaque. |
| `tipo_caja` | Tipo de caja o presentacion. |
| `grado` | Grado/calibre del producto. |
| `tallos_x_ramo` | Tallos por ramo. |
| `tallos_total` | Tallos totales reportados en la linea. |
| `tallos_pedidos` | Tallos solicitados por el cliente. |
| `tallos_confirmados` | Tallos confirmados/facturados; variable objetivo principal. |
| `estado` | Estado de la orden/pedido. |
| `tipo_orden` | Tipo general de orden. |
| `VALORTOTAL` | Valor total en moneda de origen o registro fuente. |
| `ventas_usd` | Venta convertida a USD. |
| `archivo_origen` | Archivo historico del cual proviene la fila. |

## Variables clave para forecast

- Variable objetivo: `tallos_confirmados`.
- Tiempo: `fecha`, `anio`, `semana_iso`, `mes`.
- Segmentacion: `cliente`, `pais`, `producto`, `color`, `variedad`.
- Identificacion de SOLIDO: `tipo_orden_empaque`, `tipo_empaque`, `empaque`.


