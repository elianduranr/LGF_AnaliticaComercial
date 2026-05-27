# Visualizador Clientes General

Este documento define la lectura funcional y la lógica de negocio del modulo `Visualizador clientes general` del dashboard operativo.

## Objetivo

El visualizador debe explicar la historia comercial y operativa de un cliente desde la estructura real de compra.

La unidad principal de lectura es el `SKU operativo`, no siempre `producto + color`.

## Fuente de datos

La vista debe construirse sobre `historico_confirmado.csv` y los agregados descriptivos derivados de esa base.

Regla general:
- Usar el historico para resolver la identidad real del SKU operativo.
- Usar los agregados para KPI, ranking, composicion interna y tablas de apoyo.
- No tratar productos no solidos como si fueran lineas producto + color.

## Regla de SKU operativo

### Solidos

En `SOLIDO`, el SKU visible debe conservar el color como parte principal de la identidad.

Formato recomendado:
- `SOLIDO | producto | color`

El detalle puede ampliar con:
- `tipo_caja`
- `tallos_x_ramo`
- `variedad`
- `capuchon`
- `comida`
- `empaque`

La variedad no reemplaza el color. Va como detalle secundario.
La clave operativa base para solidos debe agrupar por `producto + color`; la variedad solo aparece como detalle opcional.

### No solidos

En `SURTIDO_M`, `RAINBOW`, `BOUQUET`, `COMBO`, `ASSORTED` y formatos similares, el SKU visible debe representar la estructura del pedido. Cualquier `SURTIDO` legacy se trata como `SURTIDO_M`.

El color no define el SKU. El color es composicion interna.

Formato recomendado:
- `TIPO | producto/familia | estructura`

El detalle puede mostrar:
- `color`
- `variedad`
- `participacion`
- `tipo_caja`
- `tallos_x_ramo`
- `capuchon`
- `comida`
- `empaque`

## Lectura visual

La pestaña debe responder a tres niveles:

1. Vista general.
2. Vista por SKU operativo.
3. Vista interna de composicion.

### Vista general

Debe mostrar:
- KPIs del periodo filtrado
- evolucion semanal
- ranking de SKUs operativos
- mix por tipo operativo
- historia reciente

### Vista de composicion interna

Debe servir para revisar:
- colores internos de un SKU
- variedades internas
- participacion por color o por color + variedad
- acumulado, promedio o semana seleccionada

## KPIs principales

Orden funcional:
- `Tallos confirmados`
- `Ventas USD`
- `Precio promedio USD/tallo`
- `Pedidos`
- `SKUs activos`
- `Cajas`
- `% cumplimiento` solo cuando haya comparacion contra tallos pedidos

La metrica por defecto es `Tallos confirmados`.

## Filtros

Todos los filtros superiores deben alimentar el mismo dataset global y afectar:
- KPIs
- graficos
- rankings
- tablas
- lectura operativa

Filtros funcionales:
- Cliente
- Ano o anos
- Semana de analisis
- Semanas hacia atras
- Producto
- Tipo operativo
- Color interno
- SKU operativo
- Metrica grafica
- Comparar contra ano anterior
- Vista de color
- Detalle interno

Reglas:
- `SKU operativo` inicia en `Todos los SKUs`.
- `Color` debe leerse como `Color interno` cuando el contexto no sea solido.
- La comparacion contra ano anterior es opcional.

## Secciones del visualizador

### 1. Lectura operativa

Texto dinamico que debe resumir:
- cuanto compro el cliente
- precio promedio
- SKUs mas importantes
- si la mezcla incluye no solidos

### 2. KPIs superiores

Tarjetas compactas y ordenadas por relevancia funcional.

### 3. Evolucion semanal

Linea por ano y por semana ISO.

Si se activa comparacion contra ano anterior:
- comparar por numero de semana
- no por fecha exacta

### 4. Ranking de SKUs operativos

Debe ordenar de mayor a menor por `tallos confirmados`.

Columnas recomendadas:
- SKU operativo visible
- Tipo operativo
- Producto/Familia
- Tallos confirmados
- Participacion
- Ventas USD
- Precio promedio USD/tallo
- Pedidos
- Cajas
- Semanas activas

### 5. Composicion interna

Debe permitir ver:
- color
- variedad
- color + variedad
- participacion interna
- semana
- ano

### 6. Mix por tipo operativo

Debe ayudar a entender si el cliente compra:
- solidos
- surtidos
- bouquets
- mixes
- combos
- otros

### 7. Historia reciente

Debe ordenar por volumen y mostrar:
- semana actual
- semana -1
- semana -2
- semana -3
- promedio ultimas 12 semanas
- variacion vs promedio
- precio promedio
- atributos de presentacion como columnas separadas

### 8. Tablas de detalle

Siempre al final.

Incluyen:
- detalle por SKU operativo
- detalle de composicion interna
- detalle por semana
- detalle por caja ID
- exportacion completa

## Reglas de presentacion

- No esconder `capuchon`, `comida` ni `empaque` dentro del nombre principal del SKU.
- No usar `producto + color` como identidad para no solidos.
- No autoseleccionar un SKU operativo al entrar.
- Mantener la lectura de solidos mas especifica que la de no solidos.
- Mantener el detalle interno como una vista opcional, no como la vista principal.

## Referencias de implementacion

Archivo principal:
- [`app_dash.py`](../app_dash.py)

Funciones clave actuales:
- `render_visualizador_clientes_general`
- `filter_visual_operational_base`
- `visual_sku_ranking`
- `visual_color_composition`
- `visual_recent_history`
- `operational_sku_label`

## Notas de mantenimiento

Si se vuelve a tocar esta pestaña, la prioridad es:
1. Conservar la identidad visual del SKU operativo.
2. Mantener el color como identidad principal en solidos.
3. Mantener el color como composicion interna en no solidos.
4. No perder el detalle de variedad, capuchon, comida y empaque.
5. Mantener todos los filtros sobre el mismo dataset filtrado global.
