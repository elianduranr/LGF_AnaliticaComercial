# Procedimiento operativo `op_sales` SQL Server

Este README explica el flujo correcto para consolidar ventas en SQL Server y luego regenerar los resultados del proyecto.

## Idea General

El orden correcto es:

```text
CSV historico / procedimiento almacenado
        -> pipeline Python de limpieza y reglas
        -> SQL Server: op_sales.fact_sales_line
        -> descriptivos
        -> forecast
        -> dashboard
```

`op_sales.fact_sales_line` debe quedar como la fuente oficial consolidada. El forecast no se corre antes de cargar SQL; se corre despues, leyendo la base consolidada o los descriptivos generados desde ella.

## 1. Configurar Conexion

No pongas credenciales en el codigo. En Git Bash configura las variables:

```bash
export OP_SALES_SQL_DRIVER="ODBC Driver 18 for SQL Server"
export OP_SALES_SQL_SERVER="192.168.1.22"
export OP_SALES_SQL_DATABASE="gaitana"
export OP_SALES_SQL_USER="sa"
export OP_SALES_SQL_PASSWORD="TU_PASSWORD_REAL"
```

Tambien puedes usar una sola variable:

```bash
export OP_SALES_CONN_STR="DRIVER={ODBC Driver 18 for SQL Server};SERVER=192.168.1.22;DATABASE=gaitana;UID=sa;PWD=TU_PASSWORD_REAL;TrustServerCertificate=yes;"
```

Si no defines usuario/clave, los scripts intentan autenticacion integrada de
Windows contra `192.168.1.22`. En entornos sin credenciales de dominio debes
usar `OP_SALES_SQL_USER`/`OP_SALES_SQL_PASSWORD` o `OP_SALES_CONN_STR`.

## 2. Crear Schema y Tablas

Esto se hace una sola vez, o cada vez que cambie el DDL:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py --init-schema
```

Esto crea o actualiza:

```text
op_sales.etl_load_batch
op_sales.fact_sales_line
op_sales.vw_sales_dashboard_week_client_product
op_sales.vw_visualizador_cliente_sku_semana
```

Si falla por permisos, ejecuta manualmente en SQL Server el archivo:

```text
sql/op_sales_schema.sql
```

en la base `gaitana`.

## 3. Carga Inicial Historica

Las bases historicas hasta semana 20 de 2026 ya estan locales en:

```text
bases de datos historicas/historic_sales_acum.csv
```

No vuelvas a descargar esas semanas desde el procedimiento. Carga el acumulado local:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17 \
  --split-by month
```

Para validar lectura, limpieza y rango sin escribir en SQL:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17 \
  --dry-run
```

`2026-05-17` es el cierre de la semana ISO 20 de 2026.

Para el acumulado completo se recomienda `--split-by month`: procesa el CSV
una sola vez y reemplaza SQL en transacciones mensuales. Evita que SQL Server
corte conexiones largas por una unica transaccion de mas de 1.6 millones de
filas.

Cada periodo cargado hace esto en una transaccion:

```text
1. Lee el CSV.
2. Aplica clean_historical_orders y las reglas actuales del proyecto.
3. Crea line_key para evitar duplicados.
4. Registra una carga en op_sales.etl_load_batch.
5. Borra el rango de fechas indicado en op_sales.fact_sales_line.
6. Inserta los datos procesados.
7. Guarda filas eliminadas, filas insertadas, tallos y ventas.
```

Durante la ejecucion ahora imprime validadores y avance en consola:

```text
Carga op_sales iniciada
- rango: 2021-01-01 a 2026-05-17
- fuente: archivo bases de datos historicas/historic_sales_acum.csv
Archivo leido: ...
Ventas procesadas para SQL: ...
Rango que se va a reemplazar: ...
Filas eliminadas del rango: ...
Insertando en SQL por lotes de 5,000 filas: ...
  lote 1/...
  lote 10/...
Confirmando transaccion en SQL
Carga terminada OK
```

Si no ves nuevos lotes durante mucho tiempo, normalmente SQL Server esta ocupado insertando el lote actual. Puedes bajar el tamano del lote para tener feedback mas frecuente:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17 \
  --chunk-size 1000
```

Para reducir mensajes:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17 \
  --quiet
```

Validadores que detienen la carga antes de insertar:

```text
- El dataframe procesado queda vacio.
- El rango de fechas no tiene filas.
- Quedan claves fecha + line_key duplicadas.
- SQL inserta menos filas que las esperadas.
```

## 4. Validar Carga En SQL Server

Despues de cargar, ejecuta:

```sql
SELECT COUNT(*) AS filas
FROM op_sales.fact_sales_line;

SELECT MIN(fecha) AS fecha_min, MAX(fecha) AS fecha_max
FROM op_sales.fact_sales_line;

SELECT TOP 20 *
FROM op_sales.etl_load_batch
ORDER BY load_id DESC;
```

Validacion por semana:

```sql
SELECT
    anio,
    semana_iso,
    COUNT(*) AS filas,
    SUM(tallos_confirmados) AS tallos_confirmados,
    SUM(ventas_usd) AS ventas_usd
FROM op_sales.fact_sales_line
GROUP BY anio, semana_iso
ORDER BY anio, semana_iso;
```

Validacion de duplicados:

```sql
SELECT line_key, COUNT(*) AS veces
FROM op_sales.fact_sales_line
GROUP BY line_key
HAVING COUNT(*) > 1;
```

Debe retornar cero filas.

Nota: `line_key` se genera con los campos comerciales de la linea mas un consecutivo interno para ocurrencias repetidas. Esto es necesario porque en ventas pueden existir varias lineas comercialmente identicas en la misma fecha/caja/pedido.

## 5. Actualizar Una Semana Nueva Desde El Cuadernillo

Este es el flujo oficial para semanas nuevas. Ejecuta la logica del cuadernillo
`Pipeline_ETL_ventas_notebooks/ETL_ventas_por_anios_csv.ipynb`, pero desde Python,
y carga el resultado a `op_sales`.

Ejemplo semana 21 de 2026:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --from-cuadernillo \
  --start-date 2026-05-18 \
  --end-date 2026-05-24
```

Esto borra e inserta solo `2026-05-18` a `2026-05-24`.

Si corriges una semana ya cargada, ejecuta el mismo comando con el rango de esa semana. No insertes encima sin borrar.

El script siempre hace reemplazo controlado:

```text
DELETE del rango en op_sales.fact_sales_line
INSERT del rango procesado por el cuadernillo
registro en op_sales.etl_load_batch
```

Si quieres guardar tambien el CSV y el archivo de control que produce la logica del cuadernillo:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --from-cuadernillo \
  --start-date 2026-05-18 \
  --end-date 2026-05-24 \
  --save-cuadernillo-output "bases de datos historicas/actualizaciones_sql"
```

Si `Master_table_varieties.xlsx` no esta en la ruta original del cuadernillo, pasalo explicitamente:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --from-cuadernillo \
  --master-varieties "C:/ruta/Master_table_varieties.xlsx" \
  --start-date 2026-05-18 \
  --end-date 2026-05-24
```

## 6. Variables Necesarias Para El Cuadernillo

El cuadernillo usa dos conexiones:

- Webflor, para `Reporte.InformeDeVentasFacturadas`.
- Gaitana, para divisas y maestros.

Configura Webflor:

```bash
export ETL_WEBFLOR_SQL_DRIVER="ODBC Driver 18 for SQL Server"
export ETL_WEBFLOR_SQL_SERVER="SERVIDOR_WEBFLOR"
export ETL_WEBFLOR_SQL_DATABASE="WF_Gaitana"
export ETL_WEBFLOR_SQL_USER="USUARIO_WEBFLOR"
export ETL_WEBFLOR_SQL_PASSWORD="PASSWORD_WEBFLOR"
```

Configura Gaitana/op_sales:

```bash
export OP_SALES_SQL_DRIVER="ODBC Driver 18 for SQL Server"
export OP_SALES_SQL_SERVER="192.168.1.22"
export OP_SALES_SQL_DATABASE="gaitana"
export OP_SALES_SQL_USER="sa"
export OP_SALES_SQL_PASSWORD="TU_PASSWORD_REAL"
```

Tambien puedes configurar la ruta del maestro de variedades:

```bash
export ETL_MASTER_VARIETIES_PATH="C:/ruta/Master_table_varieties.xlsx"
```

## 7. Actualizar Directo Desde Procedimiento Almacenado

No es el flujo recomendado para produccion porque salta reglas del cuadernillo.
Solo usar para pruebas puntuales.

Ejemplo:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --stored-procedure "dbo.NOMBRE_DEL_PROCEDIMIENTO" \
  --exec-sql "EXEC dbo.NOMBRE_DEL_PROCEDIMIENTO @FechaInicial=?, @FechaFinal=?" \
  --start-date 2026-05-18 \
  --end-date 2026-05-24
```

Cambia `dbo.NOMBRE_DEL_PROCEDIMIENTO` por el nombre real del procedimiento.

El procedimiento sigue siendo fuente interna del cuadernillo. La fuente oficial para analisis queda en:

```text
op_sales.fact_sales_line
```

## 8. Regenerar Resultados Del Proyecto Desde SQL

Despues de actualizar SQL, se deben regenerar los resultados derivados.

Despues de actualizar `op_sales.fact_sales_line`, los resultados derivados se regeneran desde SQL.

### 8.1 Descriptivos Desde SQL

Toda la historia disponible en SQL:

```bash
./carac_clients/Scripts/python.exe run_descriptivos.py --no-cache
```

Rango opcional:

```bash
./carac_clients/Scripts/python.exe run_descriptivos.py \
  --source sql \
  --start-date 2021-01-01 \
  --end-date 2026-05-24 \
  --no-cache
```

Esto lee:

```sql
SELECT *
FROM op_sales.fact_sales_line;
```

y escribe en:

```text
resultados/descriptivos
```

### 8.2 Forecast Solidos

Usa el historico limpio que acaba de generar descriptivos:

```bash
./carac_clients/Scripts/python.exe run_forecast_solidos.py \
  --historico-limpio "resultados/descriptivos/historico_confirmado.csv" \
  --no-cache
```

Salida:

```text
resultados/forecast_solidos
```

### 8.3 Orden Completo Despues De Actualizar SQL

```bash
./carac_clients/Scripts/python.exe run_descriptivos.py --source sql --no-cache

./carac_clients/Scripts/python.exe run_forecast_solidos.py \
  --historico-limpio "resultados/descriptivos/historico_confirmado.csv" \
  --no-cache
```

## 9. Correr Dashboard

Mientras el flujo principal siga usando outputs generados:

```bash
./carac_clients/Scripts/python.exe app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8050
```

No uses el Dash como sustituto de descriptivos/forecast. El Dash debe ser consumidor final.

## 10. Que Hacer Si Falla

### Error: `op_sales.etl_load_batch no es valido`

Falta crear el schema:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py --init-schema
```

### Error de credenciales o conexion

Revisa variables:

```bash
echo $OP_SALES_SQL_SERVER
echo $OP_SALES_SQL_DATABASE
echo $OP_SALES_SQL_USER
```

No imprimas la clave en consola compartida.

### Error por ODBC Driver

Verifica que exista `ODBC Driver 18 for SQL Server` instalado en Windows. Si tienes otro driver, ajusta:

```bash
export OP_SALES_SQL_DRIVER="ODBC Driver 17 for SQL Server"
```

### La carga queda a medias

El script usa transaccion. Si falla, hace rollback. Revisa:

```sql
SELECT TOP 20 *
FROM op_sales.etl_load_batch
ORDER BY load_id DESC;
```

### Error de clave duplicada `PK_op_sales_fact_sales_line`

Ejemplo:

```text
Infraccion de la restriccion PRIMARY KEY 'PK_op_sales_fact_sales_line'
```

Esto significa que SQL intento insertar dos filas con la misma `fecha + line_key`.

La version actual del cargador ya corrige esto agregando un consecutivo interno a `line_key` para lineas repetidas legitimas. Si ves este error:

1. Asegurate de tener el codigo actualizado.
2. Vuelve a correr exactamente el mismo comando de carga.
3. No borres datos manualmente; el script hace rollback si falla.

Validacion posterior:

```sql
SELECT line_key, COUNT(*) AS veces
FROM op_sales.fact_sales_line
GROUP BY line_key
HAVING COUNT(*) > 1;
```

Debe retornar cero filas.

## 11. Resumen Operativo

Primera vez:

```bash
export OP_SALES_SQL_SERVER="192.168.1.22"
export OP_SALES_SQL_DATABASE="gaitana"
export OP_SALES_SQL_USER="sa"
export OP_SALES_SQL_PASSWORD="TU_PASSWORD_REAL"

./carac_clients/Scripts/python.exe cargar_op_sales_sql.py --init-schema

./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --input "bases de datos historicas/historic_sales_acum.csv" \
  --start-date 2021-01-01 \
  --end-date 2026-05-17
```

Cada semana:

```bash
./carac_clients/Scripts/python.exe cargar_op_sales_sql.py \
  --from-cuadernillo \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD
```

Despues de actualizar SQL:

```bash
./carac_clients/Scripts/python.exe run_descriptivos.py --source sql --no-cache
./carac_clients/Scripts/python.exe run_forecast_solidos.py --no-cache
./carac_clients/Scripts/python.exe app_dash.py --data-dir "resultados/descriptivos" --forecast-dir "resultados/forecast_solidos"
```
