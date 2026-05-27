# Foco descriptivo

Este documento define el alcance inmediato para no complejizar todo al mismo tiempo.

## Lo que si entra ahora

- Cliente 360.
- Visualizador clientes general.
- Historicos por semana, mes, producto, color, variedad, SKU y tipo de pedido.
- Precio en USD.
- Precio en moneda original.
- Tablas de productos y clientes faciles de leer.
- Lecturas descriptivas automaticas.
- Performance del dashboard usando agregados.

## Lo que no entra ahora

- Reentrenar forecast.
- Redisenar modelo estacional.
- Cambiar logica de inventario.
- Rehacer clusters.
- Meter acciones de compra dentro del descriptivo.

## Preguntas que debe responder el descriptivo

- Que compra este cliente?
- Con que frecuencia compra?
- Que productos y colores dominan?
- Que SKUs o estructuras se repiten?
- Cual es el precio promedio en dolares?
- Cual es el precio promedio en moneda original?
- Como cambia el cliente por semana y por ano?
- Que tan estable es el cliente?
- Que productos explican el volumen?

## Fuentes preferidas para dashboard

Orden de preferencia:

1. CSV agregados descriptivos.
2. `cliente_*` ya calculados.
3. `historico_confirmado.csv` solo para detalle de un cliente seleccionado.

Evitar usar `historico_confirmado.csv` para vistas generales porque es demasiado grande.

## Proxima mejora sugerida

Crear agregados especificos para precio:

- `precio_cliente_producto.csv`
- `precio_cliente_semana.csv`
- `precio_producto_moneda.csv`
- `precio_cliente_sku_operativo.csv`

Con esos archivos el visualizador podria mostrar precio USD y moneda original sin tocar el historico pesado en callbacks.

## Agregados de ventas creados para el visualizador

El visualizador general debe trabajar desde ventas reales confirmadas, no desde forecast.

CSV descriptivos nuevos:

- `ventas_semana_cliente_producto.csv`: base principal para comparar ventas por ano, semana, CODCUSTOM, producto, color, tipo operativo y moneda.
- `ventas_producto_periodo.csv`: ventas por ano, semana, producto, color, tipo operativo y moneda.
- `ventas_cliente_periodo.csv`: ventas por ano, semana y cliente.
- `ventas_caja_periodo.csv`: ventas por ano, semana, cliente, producto, color, tipo operativo y caja ID.

Reglas de precio:

- Precio venta en dolares: `ventas_usd / tallos_confirmados`.
- Precio en moneda original: `valor_total_original / tallos_confirmados`.

Estos calculos salen de la base limpia confirmada. No usan proyecciones del modelo.
