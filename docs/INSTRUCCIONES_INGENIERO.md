# Instrucciones para el ingeniero

> Nota de vigencia: ejecutar nuevas corridas con las rutas y comandos de
> `../README_EJECUCION.md`. Los ejemplos `outputs_*` que se conservan abajo
> corresponden a la etapa previa de validacion.

Esta guia es el punto de entrada operativo del proyecto. La idea es saber que correr, que archivo tocar y que no mezclar.

## Regla principal

No trabajar descriptivos, clusters, forecast e inventario al mismo tiempo.

Orden recomendado:

1. Descriptivos.
2. Dashboard descriptivo.
3. Clusters y similares.
4. Forecast / proyeccion.
5. Inventario y compra.

Ahora el foco recomendado es **descriptivos**.

## Estructura mental del proyecto

### Limpieza

Convierte el historico crudo en una base usable.

Archivos:

- `src/lgf_operativo/cleaning.py`
- `src/lgf_operativo/io_utils.py`

Tocar solo si hay problemas de columnas, estados, fechas, monedas, productos o clasificacion de pedidos.

### Descriptivos

Genera lectura historica de clientes, productos, precios, semanas, colores y SKUs.

Archivos:

- `run_descriptivos.py`
- `src/lgf_operativo/descriptive.py`
- `src/lgf_operativo/metrics.py`

Este es el modulo que debes usar para mejorar Cliente 360 y Visualizador clientes general.

### Clusters

Agrupa clientes y calcula similares.

Archivo:

- `src/lgf_operativo/similarity.py`

No tocar mientras se este trabajando descriptivos, salvo que el objetivo sea explicitamente clusters.

### Forecast

Proyecta demanda futura.

Archivos:

- `src/lgf_operativo/forecast.py`
- `src/lgf_operativo/seasonal_model.py`

No tocar mientras el objetivo sea solo entender historicos.

### Inventario y compra

Cruza demanda futura contra disponibilidad.

Archivo:

- `src/lgf_operativo/inventory.py`

Solo tocar cuando se este trabajando faltantes, sobrantes o prioridad de compra.

### Dashboard

Muestra los CSV ya generados.

Archivo:

- `app_dash.py`

Regla: el dashboard no debe recalcular modelos pesados. Debe leer outputs ya preparados.

## Comandos principales

### Trabajar solo descriptivos

```powershell
python run_descriptivos.py --output "outputs_descriptivo"
```

Luego abrir Dash con esos outputs:

```powershell
python app_dash.py --data-dir "outputs_descriptivo" --host 127.0.0.1 --port 8050
```

Abrir:

```text
http://127.0.0.1:8050
```

### Correr MVP completo rapido

```powershell
python run_mvp.py --output "outputs_baseline" --forecast-model baseline
```

Usar cuando necesites forecast baseline y demanda futura.

### Correr con inventario

```powershell
python run_mvp.py --output "outputs_baseline" --forecast-model baseline --inventario "RUTA_INVENTARIO"
```

Usar solo cuando vayas a trabajar compra o disponibilidad.

### Correr modelo estacional

```powershell
python run_mvp.py --forecast-model seasonal_boosting --output "outputs_modelo"
```

Usar solo cuando el foco sea mejorar proyeccion.

## Que outputs mirar para descriptivos

Los principales son:

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
- `ventas_semana_cliente_producto.csv`
- `ventas_producto_periodo.csv`
- `ventas_cliente_periodo.csv`
- `ventas_caja_periodo.csv`

Evitar usar `historico_confirmado.csv` para vistas generales porque es muy pesado. Usarlo solo para detalle de un cliente seleccionado o para construir nuevos agregados.

Para el Visualizador clientes general, usar los agregados `ventas_*`. Las reglas son:

- USD/tallo = `ventas_usd / tallos_confirmados`.
- Moneda original/tallo = `valor_total_original / tallos_confirmados`.
- Fuente = historico confirmado de la base, sin forecast.

## Como avanzar desde aqui

### Paso 1: mejorar descriptivos

Crear agregados especificos de precio:

- `precio_cliente_producto.csv`
- `precio_cliente_semana.csv`
- `precio_producto_moneda.csv`
- `precio_cliente_sku_operativo.csv`

Objetivo: que el dashboard pueda mostrar precio USD y moneda original sin leer el historico gigante.

### Paso 2: limpiar dashboard descriptivo

Separar dentro de Dash:

- Cliente 360.
- Visualizador clientes general.
- Historicos.
- Productos/precios.

Cada vista debe leer CSV agregados.

### Paso 3: volver a clusters

Cuando descriptivos este estable, revisar:

- `clientes_similares.csv`
- `clusters_clientes.csv`
- nombres de clusters;
- explicacion de por que un cliente pertenece a cada grupo.

### Paso 4: volver a forecast

Despues revisar:

- calidad del baseline;
- ventanas de semanas;
- modelo estacional;
- comparacion contra anio anterior.

### Paso 5: volver a inventario

Al final revisar:

- faltantes;
- sobrantes;
- prioridad de compra;
- cruce por color, variedad, grado y finca.

## Checklist antes de tocar codigo

- Que modulo estoy tocando?
- Necesito correr todo el MVP o solo descriptivos?
- El cambio afecta outputs o solo dashboard?
- Estoy usando agregados o estoy leyendo historico gigante?
- Si el dashboard queda en `Updating...`, probablemente esta leyendo demasiado dato en un callback.

## Checklist despues de tocar codigo

Compilar:

```powershell
python -m py_compile app_dash.py run_descriptivos.py run_mvp.py
```

Si tocaste descriptivos:

```powershell
python run_descriptivos.py --help
```

Si tocaste Dash:

```powershell
python app_dash.py --data-dir "outputs_descriptivo" --host 127.0.0.1 --port 8050
```

## Documentos relacionados

- [`docs/VISUALIZADOR_CLIENTES_GENERAL.md`](VISUALIZADOR_CLIENTES_GENERAL.md): reglas funcionales y de presentacion del visualizador de clientes general.

- `docs/ARQUITECTURA_MODULAR.md`
- `docs/FOCO_DESCRIPTIVO.md`
- `README.md`
