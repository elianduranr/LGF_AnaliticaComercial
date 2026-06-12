# Diseno practico para `op_sales`

## Objetivo

Consolidar las ventas procesadas por el pipeline en SQL Server, bajo el schema `op_sales`, para que el Dash, descriptivos y consultas posteriores lean una fuente estable y no dependan directamente del procedimiento almacenado.

## Estructura recomendada

Implementacion inicial:

- `op_sales.fact_sales_line`: tabla grande de lineas procesadas. Guarda la salida del pipeline con reglas de negocio ya aplicadas: tipo operativo, SKU operativo, estructura de pedido, tallos, ventas, cliente, producto, color, caja, capuchon, comida, empaque y campos de control.
- `op_sales.etl_load_batch`: auditoria de cada carga: periodo reemplazado, filas eliminadas, filas insertadas, estado y totales.
- Vistas:
  - `op_sales.vw_sales_dashboard_week_client_product`
  - `op_sales.vw_visualizador_cliente_sku_semana`

Esto evita una normalizacion prematura. Para el volumen actual es mas facil mantener una tabla fact consolidada con buenos indices que separar desde ya clientes, productos, cajas, colores y SKUs en muchas dimensiones.

## Por que no separar todo ahora

Una estructura dimensional completa es util a futuro, pero hoy agregaria complejidad:

- deduplicacion de dimensiones;
- llaves sustitutas;
- cambios historicos en nombres de cliente/producto/color;
- mas puntos de falla en cargas semanales.

El paso robusto ahora es una fact procesada y estable. Mas adelante se pueden agregar dimensiones o tablas agregadas sin rehacer la fact.

## Carga semanal controlada

La carga sigue este patron:

1. Ejecutar el pipeline para el periodo deseado o leer un CSV local.
2. Procesar con `clean_historical_orders`.
3. Abrir transaccion SQL.
4. Registrar carga en `op_sales.etl_load_batch`.
5. Borrar `op_sales.fact_sales_line` donde `fecha` este entre `period_start` y `period_end`.
6. Insertar las nuevas lineas procesadas.
7. Registrar filas eliminadas, insertadas, tallos y ventas.
8. Confirmar transaccion.

Si algo falla, se hace rollback.

## Indices principales

- `(fecha, line_key)` como clave primaria clusterizada.
- `line_key` unico para evitar duplicados.
- `(cod_cliente, anio, semana_iso)` para visualizadores por cliente.
- `(sku_operativo, anio, semana_iso)` para SKU/composicion.
- `(producto, anio, semana_iso)` para ventas generales.
- `(pedido, caja_operativa, cod_cliente)` para trazabilidad operativa.

## Errores a evitar

- Guardar credenciales en notebooks o scripts versionados.
- Insertar encima sin borrar el periodo que se esta reemplazando.
- Reprocesar una semana sin registrar filas eliminadas/insertadas.
- Usar el procedimiento almacenado como fuente directa del Dash.
- Guardar solo agregados y perder trazabilidad de lineas/cajas/componentes.
- Cambiar reglas de SKU sin versionar o invalidar caches.

## Carga inicial

Usar el acumulado local existente:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17
```

`2026-05-17` corresponde al cierre de la semana ISO 20 de 2026.

## Reemplazo semanal futuro

Desde CSV:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/ventas_facturadas_2026.csv" \
  --start-date 2026-05-18 \
  --end-date 2026-05-24
```

Desde procedimiento almacenado:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --stored-procedure "dbo.NombreDelProcedimiento" \
  --exec-sql "EXEC dbo.NombreDelProcedimiento @FechaInicial=?, @FechaFinal=?" \
  --start-date 2026-05-18 \
  --end-date 2026-05-24
```

## Variables de entorno

Usar una de estas opciones:

```bash
export OP_SALES_CONN_STR='DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=gaitana;UID=...;PWD=...;TrustServerCertificate=yes;'
```

o:

```bash
export OP_SALES_SQL_DRIVER='ODBC Driver 18 for SQL Server'
export OP_SALES_SQL_SERVER='servidor'
export OP_SALES_SQL_DATABASE='gaitana'
export OP_SALES_SQL_USER='usuario'
export OP_SALES_SQL_PASSWORD='password'
```

En Windows PowerShell usar `$env:OP_SALES_SQL_SERVER='...'`.
