# CODEx_PROJECT_CONTEXT.md
# Proyecto: Caracterización Operativa de Clientes y Forecast Estructural - La Gaitana Farms

## 0. Cómo debe usar este archivo Codex

Este documento es el contexto funcional del proyecto. Codex debe leerlo antes de modificar código.

El objetivo no es construir un modelo genérico de ventas. El objetivo es construir una herramienta analítica-operativa para entender el comportamiento normal y reciente de cada cliente, estimar una estructura operativa probable de pedido y apoyar decisiones de compra de flor terminada, casi terminada o base, reduciendo reproceso en poscosecha.

Las reglas funcionales de este documento tienen prioridad sobre decisiones técnicas. Si una modificación de código contradice este documento, Codex debe preguntar antes de cambiar la lógica.

---

## 1. Propósito del proyecto

La Gaitana Farms produce y exporta flores, pero no produce el 100% de lo que vende. Por eso una parte importante de la operación depende de compras a terceros.

El dolor operativo principal es que muchas compras se hacen de forma reactiva: se compra flor por producto, color o necesidad general, pero no necesariamente como una estructura terminada para un cliente específico. Cuando la flor comprada no coincide con el pedido real, poscosecha debe reprocesar: cambiar capuchón, ajustar ramos, cambiar empaque, completar combinaciones, armar surtidos, corregir estructuras o reasignar flor.

La frase guía del proyecto es:

> No quiero estimar solo volumen total; quiero estimar una estructura operativa de pedido que sirva para comprar flor y reducir reproceso.

La herramienta debe ayudar a pasar de esta lógica:

```text
Comprar flor porque falta color.
```

A esta lógica:

```text
Comprar flor terminada, casi terminada o base para clientes y estructuras cuyo comportamiento histórico y reciente justifique anticiparse.
```

La herramienta debe responder:

- Cómo se comporta normalmente cada cliente.
- Cómo se viene comportando recientemente cada cliente.
- Qué pide cada cliente por producto, color, variedad, grado, tipo de pedido, caja, tallos por ramo, capuchón, comida y empaque.
- Qué clientes son estables y cuáles están cambiando.
- Qué clientes repiten estructuras operativas.
- Qué clientes manejan principalmente sólidos, surtidos, surtido M, rainbow, combo, bulk o bouquet.
- Qué tipo de análisis aplica según el tipo de pedido dominante del cliente.
- Qué clientes son buenos candidatos para compra terminada.
- Qué clientes solo sirven para compra casi terminada o compra por color/base.
- Qué clientes no deben usarse para compra anticipada porque son demasiado variables.
- Qué clientes tienen patrones similares entre sí.
- Qué clientes presentan bajo cumplimiento histórico o reciente.
- Cómo cruzar demanda futura probable contra disponibilidad/inventario proyectado.
- Cómo priorizar compras para reducir reproceso y mejorar cumplimiento.

El proyecto debe empezar simple con Python + CSV/Excel, pero debe quedar preparado para crecer hacia SQL Server + Power BI.

---

## 2. Contexto operativo de La Gaitana Farms

Actualmente existe una proyección de disponibilidad que combina varias fuentes:

- Pedidos confirmados históricos.
- Pedidos pendientes reales ya recibidos del cliente.
- Estimados comerciales.
- Estimados de compra.
- Estimados de producción.
- Disponibilidad propia.
- Inventario o disponibilidad futura proyectada por producto, variedad, color, grado, finca y fecha.

La empresa puede comprar flor a terceros de diferentes maneras:

- Flor por color o producto base.
- Flor casi terminada.
- Flor con alguna estructura parecida al pedido final.
- Flor terminada para un cliente o tipo de pedido específico.

Comprar solo flor por color puede generar más reproceso, manipulación, tiempo en poscosecha, errores, presión operativa y dificultad para cumplir pedidos.

Comprar flor terminada o casi terminada para clientes estables puede reducir:

- Reempaque.
- Cambios de capuchón.
- Cambios de caja.
- Ajustes de ramo.
- Manipulación adicional.
- Riesgo de incumplimiento.
- Tiempo operativo.
- Presión en poscosecha.

---

## 3. Decisiones funcionales ya definidas

Estas decisiones NO deben cambiarse sin confirmación del usuario.

### 3.1 Fecha oficial

La fecha oficial del análisis es:

```text
FECHA
```

Significado:

```text
Fecha de salida/despacho desde Bogotá.
```

No usar `PullDate` como fecha principal del análisis.

---

### 3.2 Cantidad oficial

La cantidad oficial del análisis es:

```text
TallosPedidos
```

El proyecto debe calcular métricas de cumplimiento usando:

```text
TallosPedidos vs TallosConfirmados
```

Definiciones:

```text
faltante_tallos = TallosPedidos - TallosConfirmados
cumplimiento = TallosConfirmados / TallosPedidos
```

El cumplimiento debe calcularse por cliente, producto, color, variedad, tipo de pedido, estructura y semana. Esta métrica es importante porque un cliente estable pero con bajo cumplimiento puede ser una gran oportunidad para compra anticipada.

---

### 3.3 Nivel de análisis

El análisis principal debe hacerse a nivel de:

```text
CLIENTE
```

Pero todos los exports deben incluir siempre:

```text
CODCUSTOM
CLIENTE
```

En el código usar nombres normalizados:

```text
cod_cliente
cliente
```

Internamente en Gaitana los clientes son más conocidos por código que por nombre. Por eso `CODCUSTOM` es obligatorio en salidas, dashboards y tablas intermedias.

No hacer el análisis principal por `CLIENTE + SUBCLIENTE`, salvo que el usuario lo pida explícitamente después.

---

### 3.4 Flor terminada

Para Gaitana, una flor terminada se define como una estructura operativa que incluye:

```text
Producto + Variedad + Color + Tipo de caja + Tallos por ramo + Capuchón + Comida + Empaque + Tipo de pedido
```

También debe considerarse:

```text
Sólido, Surtido, Surtido M, Rainbow, Combo, Bulk, Bouquet, BQT u Otro
```

No mezclar estructuras operativamente diferentes aunque compartan producto/color.

Ejemplo:

```text
Minicarnation white en sólido no debe mezclarse con minicarnation white en surtido M o rainbow.
```

---

## 4. Principio temporal clave: el cliente cambia

La caracterización debe reconocer que los clientes cambian a lo largo del tiempo.

Un cliente puede haber comprado de una forma en 2022 y estar comprando diferente hoy. Además, La Gaitana Farms también ha crecido y cambiado: cambian clientes, mercados, disponibilidad, operación, forma de vender, productos y estructura comercial.

Por eso, el histórico completo es útil, pero no debe pesar igual que la información reciente.

El análisis debe separar:

```text
Comportamiento histórico completo
Comportamiento últimas 52 semanas
Comportamiento últimas 26 semanas
Comportamiento últimas 12 semanas
Comportamiento últimas 8 semanas
Comportamiento últimas 4 semanas
Comportamiento por misma semana del año
Cambios de tendencia
Vigencia de estructuras históricas
```

Regla funcional:

```text
Mientras más reciente el dato, mayor valor operativo tiene para entender cómo se viene comportando el cliente.
```

El histórico completo debe usarse para:

- Detectar temporadas.
- Entender comportamiento de largo plazo.
- Ver semanas pico.
- Identificar estructuras históricas.
- Comparar contra el comportamiento actual.

Los datos recientes deben usarse para:

- Entender el comportamiento vigente.
- Estimar demanda futura cercana.
- Decidir compra anticipada.
- Detectar cambios recientes.
- Priorizar estructuras todavía activas.

Ponderación inicial sugerida para cálculos operativos:

```text
Últimas 4 semanas: 35%
Últimas 8 semanas: 25%
Últimas 12 semanas: 20%
Últimas 52 semanas: 10%
Histórico completo: 10%
```

Esta ponderación puede ajustarse, pero la lógica de recencia debe mantenerse.

---

## 5. Semántica obligatoria de ESTADO

El campo `ESTADO` debe interpretarse así:

| ESTADO | Significado operativo | Uso en el proyecto |
|---|---|---|
| Confirmado | Histórico real ya despachado | Base para aprender patrones, caracterizar clientes, medir cumplimiento y construir forecast histórico |
| Pendiente | Orden real futura recibida del cliente | Demanda futura real; tiene prioridad sobre forecast |
| En proceso | Estimado comercial | Se exporta y compara, pero NO debe tratarse como histórico real |
| Por verificar | Cambios sobre algo confirmado | Control operativo; no mezclar con histórico limpio |
| Reproceso | Cambios sobre algo confirmado | Control operativo; no mezclar con histórico limpio |

Regla clave:

```text
Confirmado = pasado real para aprender.
Pendiente = futuro real para operar.
En proceso = estimado comercial para comparar, no para aprender como real.
Por verificar/Reproceso = cambios sobre confirmado para control.
```

Cuando se construya demanda futura:

```text
Si existe Pendiente para cliente + fecha + estructura:
    usar Pendiente como demanda real futura.
Si no existe Pendiente:
    usar forecast histórico basado en Confirmado.
```

Los registros `En proceso` pueden servir para comparar contra `Pendiente`, `Confirmado` o forecast analítico, pero no deben entrenar ni caracterizar como demanda real.

---

## 6. Fuentes de datos principales

### 6.1 Histórico operativo de ventas/pedidos

Ruta usual en el computador de Elian:

```text
C:/Proyectos_gaitana/Visualizador historico/historic_sales_acum.csv
```

Campos esperados en el histórico:

```text
DIA, FECHA, CODCUSTOM, CLIENTE, GRUPO, SUBCLIENTE, TIPOVENTA,
TIPORDENEMPAQUE, PEDIDO, INVOICE, TIPEMPAQUE, EMPAQUE, TAMANO,
CajaId, NomColor, NomVariedad, PIEZASEQUVALENTES, FULLESEQUIVALENTES,
TYPEOFPACKAGE, TIPCAJA, TOTALTALLOS, TallosPedidos, TallosConfirmados,
TIPOCORTE, VALORUNITARIO, VALORTOTAL, MARCACAJA, PRODUCTO,
AGENCIACARGA, PAIS, CIUDAD, COMENTARIOSPEDIDO, RXCAJA, PIEZAS,
FULLES, EQUIVALENCIA, FLOREMP, TALLXRAM, TOTRAMPED, RXCAJADETALLE,
TOTRAMCONF, PO, IDCAJA, VERSION, OBSERVACIONESEMPAQUE, TipoPrecio,
TXRAMO, Comida, Capuchon, MES, TipoOrden, ESTADO, VENDEDOR, RECETA,
BULKBOUQUET, CODEMPAQUE, PullDate, GuiaMaster, SERIAL, ABREVIADOFINCA,
FINCA, NomMoneda, SEMANA
```

No asumir que todos los campos siempre vienen limpios. El código debe normalizar nombres, fechas, textos, nulos, tipos numéricos y codificaciones.

---

### 6.2 Inventario/disponibilidad futura proyectada

Ruta usual:

```text
C:/Users/elian/OneDrive - LA GAITANA FARMS SAS/Sincronizacion_PDA/basesBI/df_inventory_final.csv
```

También puede recibirse la carpeta:

```text
C:/Users/elian/OneDrive - LA GAITANA FARMS SAS/Sincronizacion_PDA/basesBI
```

Si se recibe la carpeta, el código debe buscar `df_inventory_final.csv`.

Campos esperados:

```text
PRODUCTO, COLOR, VARIEDAD, GRADO, INVENTARIO, CODFINCA, FECHA, SEMANA
```

Esta base proyectada NO trae cliente, capuchón, comida, tipo de caja ni empaque. Por eso el cruce contra demanda futura debe hacerse inicialmente por:

```text
fecha + producto + variedad + color + grado
```

Si no hay suficiente calidad de match por variedad o grado, se puede crear una segunda capa de cruce flexible por:

```text
fecha + producto + color
```

Pero debe marcarse como match flexible, no exacto.

---

## 7. MVP 1 - Caracterización 360° del comportamiento normal y reciente del cliente

### 7.1 Objetivo del módulo

El objetivo del MVP 1 es construir una caracterización operativa detallada de cada cliente, basada en datos reales, para entender cómo compra normalmente y cómo se viene comportando recientemente.

No basta con calcular un score general. La herramienta debe permitir seleccionar un cliente y saber, con datos:

- Qué pide.
- Cuándo lo pide.
- En qué semanas compra.
- Qué productos compra.
- Qué colores compra.
- Qué variedades compra.
- Qué grados usa.
- Qué tipos de pedido maneja.
- Qué estructuras repite.
- Qué sólidos repite.
- Qué surtidos repite.
- Qué rainbow, combos, bulk o bouquets maneja.
- Qué tan estable es el volumen.
- Qué tan estable es el mix de color.
- Qué tan estable es el tipo de pedido.
- Qué tan vigente es su comportamiento histórico.
- Qué ha cambiado recientemente.
- Qué estructuras históricas ya no aparecen.
- Qué estructuras nuevas están apareciendo.
- Qué tanto se le cumple.
- Qué clientes se parecen operativamente.
- Si sirve para compra terminada, casi terminada, compra por color/base o no anticipar.

La salida debe permitir una lectura como:

```text
Este cliente normalmente compra estas estructuras, pero recientemente está comprando estas otras. Tiene estos colores recurrentes, estos tipos de pedido principales, estas semanas fuertes y este nivel de cumplimiento. Por eso se recomienda comprar terminado, casi terminado, por color/base o no anticipar.
```

---

### 7.2 Niveles obligatorios de caracterización

La caracterización debe generar información en varios niveles.

#### Nivel 1: Perfil general del cliente

Archivo esperado:

```text
perfil_cliente.csv
```

Debe incluir:

```text
cod_cliente
cliente
semanas_observadas
semanas_activas
pct_semanas_activas
tallos_pedidos_total
tallos_confirmados_total
faltante_tallos_total
cumplimiento_promedio
cumplimiento_ponderado
tallos_promedio_semana
tallos_mediana_semana
cv_volumen
productos_principales
colores_principales
variedades_principales
tipos_pedido_principales
tipo_pedido_dominante_historico
tipo_pedido_dominante_reciente
producto_principal_historico
producto_principal_reciente
color_principal_historico
color_principal_reciente
score_actualidad_cliente
score_compra_terminada
segmento_cliente
recomendacion_compra
explicacion_recomendacion
```

---

#### Nivel 2: Perfil reciente del cliente

Archivo esperado:

```text
perfil_cliente_reciente.csv
```

Debe comparar ventanas de tiempo:

```text
últimas 4 semanas
últimas 8 semanas
últimas 12 semanas
últimas 26 semanas
últimas 52 semanas
histórico completo
```

Columnas sugeridas:

```text
cod_cliente
cliente
ventana_tiempo
fecha_inicio_ventana
fecha_fin_ventana
semanas_activas
tallos_pedidos
tallos_confirmados
cumplimiento_ponderado
producto_principal
color_principal
tipo_pedido_principal
sku_terminado_principal
sku_flexible_principal
colores_distintos
productos_distintos
tipos_pedido_distintos
score_estabilidad_ventana
```

---

#### Nivel 3: Cambio histórico vs reciente

Archivo esperado:

```text
cliente_cambio_comportamiento.csv
```

Debe responder si el histórico todavía representa al cliente actual.

Columnas sugeridas:

```text
cod_cliente
cliente
tallos_promedio_historico
tallos_promedio_ultimas_12
variacion_volumen_reciente_pct
top_colores_historicos
top_colores_recientes
similitud_color_historico_vs_reciente
top_productos_historicos
top_productos_recientes
similitud_producto_historico_vs_reciente
tipo_pedido_historico
tipo_pedido_reciente
cambio_tipo_pedido
cambio_mix_color
cambio_estructura
score_actualidad_cliente
clasificacion_cambio
```

Clasificaciones sugeridas:

```text
CLIENTE_ESTABLE_EN_EL_TIEMPO
CLIENTE_CON_CAMBIO_RECIENTE_LEVE
CLIENTE_CON_CAMBIO_RECIENTE_FUERTE
CLIENTE_EN_CRECIMIENTO
CLIENTE_EN_CAIDA
CLIENTE_REACTIVADO
CLIENTE_NUEVO_O_POCA_HISTORIA
```

---

#### Nivel 4: Cliente-semana

Archivo esperado:

```text
cliente_semana_comportamiento.csv
```

Debe permitir ver semana por semana qué pasó con el cliente.

Columnas sugeridas:

```text
cod_cliente
cliente
anio
semana
fecha_inicio_semana
tallos_pedidos
tallos_confirmados
faltante_tallos
cumplimiento
productos_distintos
colores_distintos
variedades_distintas
tipos_pedido_distintos
skus_terminados_distintos
top_producto_semana
top_color_semana
top_tipo_pedido_semana
es_semana_activa
es_semana_pico
es_semana_atipica
clasificacion_semana
```

Clasificaciones:

```text
SEMANA_NORMAL
SEMANA_PICO
SEMANA_BAJA
SEMANA_ATIPICA
SEMANA_SIN_COMPRA
```

---

#### Nivel 5: Semana típica del cliente

Archivo esperado:

```text
cliente_semana_tipica.csv
```

Debe permitir seleccionar una semana del año y responder:

```text
Para la semana X, ¿cómo suele comportarse este cliente?
```

Columnas sugeridas:

```text
cod_cliente
cliente
semana
producto
tipo_pedido_operativo
subtipo_pedido_operativo
variedad
color
grado
tipo_caja
tallos_por_ramo
capuchon
comida
empaque
tallos_mediana_historica_semana
tallos_promedio_historico_semana
veces_aparece_en_misma_semana
participacion_historica_semana
tallos_recientes
confianza_semana
clasificacion_semana
origen_calculo
```

Clasificaciones:

```text
SEMANA_ESTABLE
SEMANA_VARIABLE
SEMANA_PICO
SEMANA_SIN_PATRON
SEMANA_SIN_HISTORIA
```

---

## 8. Tipos de pedido operativo

El código debe clasificar tipo de pedido usando varias columnas:

```text
TIPORDENEMPAQUE, TIPEMPAQUE, EMPAQUE, RECETA, BULKBOUQUET, CODEMPAQUE, CajaId
```

Debe generar:

```text
tipo_pedido_operativo
subtipo_pedido_operativo
tipo_pedido_raw
estructura_pedido
```

Categorías esperadas:

```text
SOLIDO
SURTIDO
SURTIDO_M
RAINBOW
COMBO
BULK
BOUQUET
BQT
OTRO
```

Ejemplos:

| Texto original | tipo_pedido_operativo | subtipo |
|---|---|---|
| Sólido Por Color | SOLIDO | solido_por_color |
| Sólido Por Variedad | SOLIDO | solido_por_variedad |
| Surtido "M" | SURTIDO_M | surtido_m |
| Surtido | SURTIDO | surtido |
| Rainbow | RAINBOW | rainbow |
| Combo | COMBO | combo |
| BULK | BULK | bulk |
| Bouquet | BOUQUET | bouquet |
| BQT | BQT | bqt |

---

## 9. Regla clave: no todos los tipos de pedido se analizan igual

El código NO debe aplicar la misma lógica para sólidos, surtidos, rainbow, combos, bulk y bouquet.

| Tipo de pedido | Forma correcta de análisis |
|---|---|
| SOLIDO | Analizar SKU terminado exacto: producto + variedad + color + caja + tallos/ramo + capuchón + comida + empaque |
| SURTIDO | Analizar composición de colores, producto, empaque, caja, tallos por ramo, número de colores y patrón de mezcla |
| SURTIDO_M | Analizar estructura de mezcla: colores recurrentes, proporción de colores, empaque, tallos por ramo y, cuando exista, CajaId |
| RAINBOW | Analizar receta, colores componentes, repetición de receta y temporada |
| COMBO | Analizar combinación de productos/variedades/colores dentro de la caja |
| BULK | Analizar producto, color, volumen, frecuencia y cumplimiento |
| BOUQUET | Analizar receta, composición, empaque y repetición |
| BQT | Analizar como receta/UPC/estructura especial, parecido a bouquet/rainbow según contenido |
| OTRO | Separar para revisión manual |

Regla de negocio:

```text
Un cliente que compra principalmente surtidos no debe ser castigado por no repetir SKU terminado exacto.
```

Para surtidos, la estabilidad debe medirse principalmente por:

- Mix de color.
- Colores recurrentes.
- Número de colores.
- Producto.
- Tipo de caja.
- Tallos por ramo.
- Empaque.
- Patrón de mezcla.
- CajaId, si existe y es confiable.

Para sólidos, sí tiene sentido medir repetición exacta de SKU terminado.

---

## 10. Caracterización específica por tipo de pedido

### 10.1 Sólidos

Archivo esperado:

```text
cliente_solidos_resumen.csv
```

Debe responder:

- Qué sólidos compra el cliente.
- Qué producto, variedad y color repite.
- Qué tipo de caja usa.
- Qué tallos por ramo usa.
- Qué capuchón, comida y empaque usa.
- Qué estructuras exactas se repiten.
- Qué estructuras siguen vigentes recientemente.
- Qué estructuras eran históricas pero ya no aparecen.

Columnas sugeridas:

```text
cod_cliente
cliente
producto
variedad
color
grado
tipo_caja
tallos_por_ramo
capuchon
comida
empaque
sku_terminado
tallos_pedidos_historico
tallos_pedidos_reciente
participacion_historica
participacion_reciente
semanas_en_que_aparece
frecuencia_semanal
volumen_promedio_por_semana
cumplimiento_ponderado
nivel_repeticion
vigencia_estructura
recomendacion_solido
```

Vigencia:

```text
VIGENTE
NUEVA_RECIENTE
PERDIENDO_RELEVANCIA
HISTORICA_NO_RECIENTE
```

---

### 10.2 Surtidos y Surtido M

Archivo esperado:

```text
cliente_surtidos_resumen.csv
```

Debe responder:

- Si el cliente compra surtidos todas las semanas.
- Qué productos entran en el surtido.
- Qué colores se repiten dentro del surtido.
- Cuántos colores suele tener.
- Si el mix de colores es estable.
- Si los mismos colores aparecen juntos.
- Si la proporción de colores cambia mucho.
- Si el surtido reciente se parece al histórico.
- Si se puede comprar casi terminado.
- Si solo conviene comprar colores base.
- Si no conviene anticipar.

Columnas sugeridas:

```text
cod_cliente
cliente
tipo_pedido_operativo
subtipo_pedido_operativo
producto
empaque
tipo_caja
tallos_por_ramo
caja_id
semanas_con_surtido_historico
semanas_con_surtido_reciente
frecuencia_surtido_historica
frecuencia_surtido_reciente
tallos_pedidos_surtido_historico
tallos_pedidos_surtido_reciente
participacion_surtido_historica
participacion_surtido_reciente
colores_promedio_por_surtido
top_colores_surtido_historico
top_colores_surtido_reciente
top_3_colores_share
estabilidad_mix_color_surtido
cambio_mix_surtido
colores_recurrentes
colores_variables
cumplimiento_ponderado_surtido
recomendacion_surtido
```

Recomendaciones:

```text
SURTIDO_ESTABLE_COMPRAR_CASI_TERMINADO
SURTIDO_ESTABLE_COMPRAR_COLORES_BASE
SURTIDO_RECIENTE_CAMBIANDO_REVISAR
SURTIDO_VARIABLE_NO_ANTICIPAR
SURTIDO_REVISAR_MANUAL
```

---

### 10.3 Rainbow

Archivo esperado:

```text
cliente_rainbow_resumen.csv
```

Debe analizar receta y composición.

Columnas sugeridas:

```text
cod_cliente
cliente
receta
producto
tipo_caja
tallos_por_ramo
empaque
colores_receta
numero_colores
tallos_pedidos_historico
tallos_pedidos_reciente
semanas_en_que_aparece
frecuencia_receta
estabilidad_receta
vigencia_receta
cumplimiento_ponderado
recomendacion_rainbow
```

---

### 10.4 Combos, Bouquet y BQT

Archivo esperado:

```text
cliente_recetas_combos_resumen.csv
```

Debe analizar pedidos que son más una receta o composición interna que un SKU simple.

Debe responder:

- Qué productos aparecen juntos.
- Qué colores o variedades componen la receta.
- Si la receta se repite.
- Si está asociada a `RECETA`, `CODEMPAQUE`, `CajaId` o `BULKBOUQUET`.
- Si la receta sigue apareciendo recientemente.
- Si se puede comprar como casi terminado o si requiere manejo manual.

Columnas sugeridas:

```text
cod_cliente
cliente
tipo_pedido_operativo
subtipo_pedido_operativo
receta
codempaque
caja_id
bulkbouquet
productos_componentes
colores_componentes
variedades_componentes
numero_componentes
tallos_pedidos_historico
tallos_pedidos_reciente
frecuencia_receta
vigencia_receta
cumplimiento_ponderado
recomendacion_receta
```

---

### 10.5 Bulk

Archivo esperado:

```text
cliente_bulk_resumen.csv
```

Debe analizarse más por producto-color-volumen que por SKU terminado exacto.

Columnas sugeridas:

```text
cod_cliente
cliente
producto
color
grado
tallos_pedidos_historico
tallos_pedidos_reciente
frecuencia_bulk
cv_volumen_bulk
cumplimiento_ponderado
recomendacion_bulk
```

---

## 11. SKUs operativos

Crear tres niveles de SKU.

### 11.1 SKU terminado

Sirve para compra de flor prácticamente lista para el cliente.

```text
cod_cliente + producto + variedad + color + grado + tipo_caja + tallos_por_ramo + capuchon + comida + empaque + tipo_pedido_operativo + subtipo_pedido_operativo
```

Usar especialmente para `SOLIDO`.

---

### 11.2 SKU flexible

Sirve para compra cercana cuando no se puede conseguir todo terminado.

```text
cod_cliente + producto + color + grado + tipo_caja + tallos_por_ramo + empaque + tipo_pedido_operativo
```

Usar para compra casi terminada y para surtidos estables.

---

### 11.3 SKU composición/receta

Sirve para surtidos, rainbow, combo, bouquet, BQT y recetas.

```text
cod_cliente + tipo_pedido_operativo + producto + empaque + tipo_caja + tallos_por_ramo + receta/caja_id/codempaque + patrón de colores
```

Si `CajaId` existe y está poblado de forma confiable, usarlo como identificador de estructura. Si no, construir la estructura con empaque, producto, tipo de caja, tallos por ramo y patrón de colores.

---

## 12. Estructuras repetitivas del cliente

Archivo esperado:

```text
cliente_estructuras_repetidas.csv
```

Debe detectar estructuras que se repiten y diferenciar si siguen siendo relevantes hoy.

Columnas sugeridas:

```text
cod_cliente
cliente
tipo_pedido_operativo
subtipo_pedido_operativo
sku_terminado
sku_flexible
sku_composicion
producto
variedad
color
grado
tipo_caja
tallos_por_ramo
capuchon
comida
empaque
receta
caja_id
codempaque
tallos_pedidos_total
tallos_pedidos_reciente
participacion_cliente_total
participacion_cliente_reciente
semanas_en_que_aparece
frecuencia_semanal
volumen_promedio
volumen_mediana
cv_volumen_estructura
cumplimiento_ponderado
nivel_repeticion
vigencia_estructura
recomendacion_estructura
```

Nivel de repetición:

```text
ESTRUCTURA_FIJA
ESTRUCTURA_RECURRENTE
ESTRUCTURA_OCASIONAL
ESTRUCTURA_VARIABLE
```

Vigencia:

```text
VIGENTE
NUEVA_RECIENTE
PERDIENDO_RELEVANCIA
HISTORICA_NO_RECIENTE
```

---

## 13. Score y recomendaciones

El score de compra terminada debe estar entre 0 y 100, pero no debe ser una caja negra.

Debe considerar:

- Frecuencia reciente.
- Estabilidad de volumen reciente.
- Estabilidad de color reciente.
- Repetición de estructuras vigentes.
- Vigencia de SKUs históricos.
- Cumplimiento histórico y reciente.
- Tipo de pedido dominante.
- Complejidad operativa.
- Similitud con clientes compatibles.
- Score de actualidad del cliente.

Componentes sugeridos:

| Componente | Peso inicial |
|---|---:|
| Frecuencia reciente | 15% |
| Estabilidad de volumen reciente | 15% |
| Estabilidad de color / mix reciente | 20% |
| Repetición de estructuras vigentes | 20% |
| Estabilidad de empaque/caja/tallos por ramo | 10% |
| Cumplimiento / oportunidad de mejora | 10% |
| Actualidad del comportamiento | 10% |

Recomendaciones generales:

```text
ALTA_PRIORIDAD_COMPRAR_TERMINADO
PILOTO_SKUS_TOP
COMPRAR_CASI_TERMINADO
COMPRAR_COLOR_O_BASE_VALIDAR
NO_ANTICIPAR_TERMINADO
REVISAR_MANUALMENTE
```

La recomendación debe incluir explicación:

```text
Cliente estable en frecuencia, con colores repetitivos y estructuras vigentes. Recomendado para piloto de compra terminada.
```

```text
Cliente principalmente surtido; no conviene medirlo por SKU exacto. Tiene mix de color estable, recomendado para compra casi terminada o colores base.
```

```text
Cliente histórico estable, pero con cambio reciente fuerte. Usar histórico con cuidado y priorizar pendientes reales.
```

---

## 14. MVP 2 - Forecast estructural simple

Objetivo:

```text
Estimar una estructura operativa probable de pedido futuro usando histórico confirmado y comportamiento reciente.
```

El forecast NO debe ser solo volumen total. Debe intentar estimar:

- cod_cliente.
- cliente.
- Fecha de despacho.
- Semana.
- Producto.
- Variedad.
- Color.
- Grado.
- Tipo de caja.
- Tallos por ramo.
- Capuchón.
- Comida.
- Empaque.
- Tipo de pedido operativo.
- Subtipo de pedido operativo.
- SKU terminado/flexible/composición.
- Tallos estimados.
- Confianza.
- Origen de demanda.

El forecast debe ponderar más el comportamiento reciente que el histórico completo.

Para sólidos: estimar estructuras exactas si son vigentes y repetitivas.

Para surtidos: estimar estructura de mezcla, no solo color individual. Usar estabilidad de mix, tipo caja, tallos por ramo, empaque y patrón de colores.

Para rainbow/combo/bouquet/BQT: estimar receta o composición si es repetitiva y vigente.

Para bulk: estimar producto-color-volumen.

---

## 15. MVP 3 - Demanda futura operativa

Objetivo:

```text
Combinar pendientes reales con forecast histórico/reciente.
```

Regla:

```text
Pendiente real tiene prioridad sobre forecast.
```

Salida principal:

```text
demanda_operativa_futura.csv
```

Debe incluir:

```text
cod_cliente
cliente
fecha_despacho
semana
producto
variedad
color
grado
tipo_caja
tallos_por_ramo
capuchon
comida
empaque
tipo_pedido_operativo
subtipo_pedido_operativo
sku_terminado
sku_flexible
sku_composicion
tallos_estimados
origen_demanda
confianza_demanda
```

Valores de `origen_demanda`:

```text
PENDIENTE_REAL
FORECAST_HISTORICO_RECIENTE
ESTIMADO_COMERCIAL_REFERENCIA
```

`ESTIMADO_COMERCIAL_REFERENCIA` no debe reemplazar al pendiente real ni al forecast, salvo que se diseñe una regla explícita posterior.

---

## 16. MVP 4 - Cruce con inventario/disponibilidad futura

Objetivo:

```text
Comparar demanda futura contra disponibilidad proyectada para identificar faltantes, sobrantes y oportunidades de compra.
```

Salida principal:

```text
cruce_forecast_inventario.csv
```

Debe conservar siempre:

```text
cod_cliente
cliente
```

Debe incluir nivel de match:

```text
EXACTO_FECHA_PRODUCTO_VARIEDAD_COLOR_GRADO
FLEXIBLE_FECHA_PRODUCTO_COLOR
SIN_MATCH
```

Columnas sugeridas:

```text
cod_cliente
cliente
fecha_despacho
semana
producto
variedad
color
grado
tipo_pedido_operativo
subtipo_pedido_operativo
tallos_estimados
inventario_proyectado
diferencia
match_nivel
origen_demanda
confianza_demanda
recomendacion_compra
```

---

## 17. Outputs esperados

La herramienta debe generar una carpeta `outputs` con CSVs y un Excel consolidado.

Archivos esperados mínimos:

```text
estado_resumen.csv
pedidos_limpios.csv
historico_confirmado.csv
ordenes_pendientes_reales.csv
estimados_comerciales_en_proceso.csv
cambios_por_verificar_reproceso.csv
perfil_cliente.csv
perfil_cliente_reciente.csv
cliente_cambio_comportamiento.csv
cliente_semana_comportamiento.csv
cliente_semana_tipica.csv
cliente_sku_operativo_resumen.csv
cliente_sku_operativo_composicion.csv
cliente_semana_sku_operativo.csv
cliente_tipo_pedido_resumen.csv
cliente_solidos_resumen.csv
cliente_surtidos_resumen.csv
cliente_rainbow_resumen.csv
cliente_recetas_combos_resumen.csv
cliente_bulk_resumen.csv
cliente_estructuras_repetidas.csv
mix_color.csv
mix_tipo_pedido.csv
mix_sku_terminado.csv
mix_sku_flexible.csv
clientes_similares.csv
clusters_clientes.csv
forecast_historico_confirmado.csv
forecast_pendientes_reales.csv
demanda_operativa_futura.csv
inventario_limpio.csv
inventario_fecha_item.csv
inventario_semana_item.csv
cruce_forecast_inventario.csv
LGF_MVP_Caracterizacion_Forecast.xlsx
```

Todos los archivos relacionados con clientes deben incluir:

```text
cod_cliente
cliente
```

Todo output nuevo debe agregarse también al Excel consolidado.

---

## 18. Vista 360° en Streamlit

La interfaz debe permitir seleccionar cliente por:

```text
cod_cliente
cliente
```

Pestañas mínimas:

### 18.1 Resumen actual

Mostrar:

- Score de compra terminada.
- Score de actualidad del cliente.
- Recomendación operativa.
- Segmento.
- Total tallos histórico.
- Total tallos reciente.
- Cumplimiento histórico.
- Cumplimiento reciente.
- Tipo de pedido principal histórico.
- Tipo de pedido principal reciente.
- Producto principal histórico.
- Producto principal reciente.
- Color principal histórico.
- Color principal reciente.

### 18.2 Qué pide normalmente

Mostrar histórico completo, últimas 12 semanas y últimas 4 semanas para:

- Productos.
- Colores.
- Variedades.
- Grados.
- Tipo caja.
- Tallos por ramo.
- Capuchón.
- Comida.
- Empaque.

### 18.3 Cómo ha cambiado

Mostrar:

- Cambio de volumen.
- Cambio de mix de color.
- Cambio de producto.
- Cambio de tipo de pedido.
- Cambio de estructuras.
- Estructuras nuevas recientes.
- Estructuras históricas que ya no aparecen.

### 18.4 Tipos de pedido

Mostrar participación histórica y reciente de:

- Sólidos.
- Surtidos.
- Surtido M.
- Rainbow.
- Combo.
- Bulk.
- Bouquet/BQT.

### 18.5 Sólidos

Mostrar:

- Sólidos más repetidos.
- SKUs terminados sólidos.
- Repetición semanal.
- Vigencia actual.
- Cumplimiento.
- Recomendación de compra terminada.

### 18.6 Surtidos

Mostrar:

- Surtidos más frecuentes.
- Colores dentro del surtido.
- Estabilidad del mix.
- Colores recurrentes.
- Colores variables.
- Cambio reciente del surtido.
- Recomendación de compra para surtido.

### 18.7 Semana típica

Permitir elegir una semana y mostrar:

- Qué suele pedir ese cliente en esa semana.
- Qué tan confiable es el patrón.
- Si hay pedido pendiente real.
- Si la semana es estable, variable, pico o sin patrón.
- Si la semana reciente se parece al histórico.

### 18.8 Cumplimiento

Mostrar:

- Tallos pedidos vs confirmados.
- Faltantes por producto.
- Faltantes por color.
- Faltantes por tipo de pedido.
- Faltantes recientes.

### 18.9 Similares

Mostrar:

- Clientes parecidos.
- Similitud por producto/color.
- Similitud por tipo de pedido.
- Similitud por empaque.
- Similitud reciente.
- Posibilidad de compartir compra anticipada.

---

## 19. Estructura recomendada del proyecto

```text
lgf_operativo_project/
│
├── README.md
├── requirements.txt
├── run_mvp.py
├── app_streamlit.py
├── CODEx_PROJECT_CONTEXT.md
│
├── src/
│   └── lgf_operativo/
│       ├── __init__.py
│       ├── cleaning.py
│       ├── metrics.py
│       ├── similarity.py
│       ├── forecast.py
│       ├── inventory.py
│       ├── pipeline.py
│       └── utils.py
│
├── sql/
│   └── 01_create_tables.sql
│
└── outputs/
```

---

## 20. Reglas de desarrollo para Codex

Cuando modifiques código:

1. No cambiar decisiones funcionales sin pedir confirmación.
2. No mezclar estados operativos.
3. No usar `En proceso` como histórico real.
4. No usar `Pendiente` para entrenar histórico; usarlo como demanda futura real.
5. Todos los exports de clientes deben incluir `cod_cliente` y `cliente`.
6. Mantener funciones separadas por módulo.
7. Evitar código gigante en `run_mvp.py`; debe orquestar, no contener toda la lógica.
8. Toda nueva regla de negocio debe quedar comentada en el código.
9. Todo output nuevo debe agregarse también al Excel consolidado.
10. Si un campo no existe, crear la columna vacía y advertir; no romper innecesariamente.
11. Normalizar textos para matches, pero conservar columnas raw cuando sirvan para auditoría.
12. Mantener columnas de auditoría como `estado_raw`, `tipo_pedido_raw`, `sku_terminado`, `sku_flexible`, `sku_composicion`.
13. No eliminar columnas importantes sin justificación.
14. Evitar dependencias pesadas si no son necesarias.
15. Priorizar claridad, trazabilidad e interpretabilidad sobre sofisticación.
16. Para cualquier métrica nueva, explicar en una columna o documentación cómo se calcula.
17. Si se agrega una recomendación, agregar también la razón de la recomendación.
18. No castigar clientes de surtidos por no repetir SKU terminado exacto.
19. Distinguir siempre histórico completo vs reciente.
20. Usar datos recientes con mayor peso en forecast y recomendaciones operativas.

---

## 21. Requisitos técnicos

Archivo `requirements.txt` mínimo:

```text
jupyterlab>=4.0
ipykernel>=6.29
numpy>=1.26
pandas>=2.2
matplotlib>=3.8
scikit-learn>=1.4
openpyxl>=3.1
xlsxwriter>=3.2
xlrd>=2.0
mlxtend>=0.23
streamlit>=1.35
pyarrow>=15.0
```

---

## 22. Comando de ejecución usual

Comando recomendado dentro de la carpeta del proyecto. Usar una sola linea evita errores como `bash: --horizon-days: command not found`:

```bash
python run_mvp.py --historico "C:/Proyectos_gaitana/Visualizador historico/historic_sales_acum.csv" --output "outputs_baseline" --horizon-days 14 --lookback-weeks 8 --forecast-model baseline
```

Si se usa Bash/Git Bash en varias lineas, cada linea intermedia debe terminar en `\`:

python run_mvp.py \
  --historico "C:/Proyectos_gaitana/Visualizador historico/historic_sales_acum.csv" \
  --output "outputs_baseline" \
  --horizon-days 14 \
  --lookback-weeks 8 \
  --forecast-model baseline
```

En PowerShell, el equivalente multilinea usa backtick, no `\`:

```powershell
python run_mvp.py `
  --historico "C:\Proyectos_gaitana\Visualizador historico\historic_sales_acum.csv" `
  --output "outputs_baseline" `
  --horizon-days 14 `
  --lookback-weeks 8 `
  --forecast-model baseline
```

Para interfaz:

```bash
streamlit run app_streamlit.py
```

Flujo de trabajo recomendado para cambios visuales:

```bash
python app_dash.py --data-dir outputs_baseline --host 127.0.0.1 --port 8050
```

No correr el pipeline completo para cambios pequenos de visualizador. Regenerar outputs solo cuando cambien datos, limpieza, metricas o forecast. `run_mvp.py` tiene defaults para el historico nuevo, `outputs_baseline` y modelo `baseline` rapido; el inventario se pasa solo cuando se trabaje compra/demanda contra disponibilidad.

---

## 23. Validaciones mínimas después de cada cambio

Después de modificar el código, validar:

1. El pipeline corre completo sin errores.
2. `estado_resumen.csv` separa correctamente estados.
3. `pedidos_limpios.csv` conserva `cod_cliente` y `cliente`.
4. `historico_confirmado.csv` contiene solo Confirmado.
5. `ordenes_pendientes_reales.csv` contiene solo Pendiente.
6. `estimados_comerciales_en_proceso.csv` contiene solo En proceso.
7. `perfil_cliente.csv` tiene scores no nulos.
8. `perfil_cliente_reciente.csv` existe y compara ventanas.
9. `cliente_cambio_comportamiento.csv` mide histórico vs reciente.
10. `cliente_tipo_pedido_resumen.csv` diferencia tipos de pedido.
11. `cliente_solidos_resumen.csv` existe.
12. `cliente_surtidos_resumen.csv` existe.
13. `cliente_estructuras_repetidas.csv` existe.
14. `mix_tipo_pedido.csv` diferencia SOLIDO, SURTIDO, SURTIDO_M, RAINBOW, COMBO, BULK, BOUQUET/BQT.
15. `demanda_operativa_futura.csv` incluye `origen_demanda`.
16. `cruce_forecast_inventario.csv` conserva `cod_cliente` y tiene `match_nivel`.
17. El Excel consolidado se genera.
18. No se pierden columnas críticas de auditoría.

---

## 24. Prioridades de mejora

### Prioridad 1 - Base funcional

- Validar limpieza.
- Validar estados.
- Validar cod_cliente.
- Validar tipos de pedido.
- Validar perfil_cliente.
- Validar histórico vs reciente.
- Validar SKUs y estructuras con clientes reales conocidos.

### Prioridad 2 - Caracterización 360°

- Crear perfil_cliente_reciente.
- Crear cliente_cambio_comportamiento.
- Crear cliente_semana_comportamiento.
- Crear cliente_semana_tipica.
- Crear cliente_tipo_pedido_resumen.
- Crear cliente_solidos_resumen.
- Crear cliente_surtidos_resumen.
- Crear cliente_estructuras_repetidas.

### Prioridad 3 - Forecast y comparación

- Mejorar forecast con recencia.
- Diferenciar forecast por tipo de pedido.
- Comparar forecast vs real cuando pase la semana.
- Guardar versiones de forecast.
- Medir WAPE, bias, error color, error SKU.
- Medir porcentaje de flor usable sin reproceso.

### Prioridad 4 - Escalamiento

- Agregar Power BI friendly exports.
- Agregar tablas SQL.
- Mejorar cruce flexible con inventario.
- Crear interfaz más robusta.
- Optimización de compra entre clientes compatibles.

---

## 25. Prompt corto para usar con Codex

```text
Estoy trabajando en el proyecto LGF de caracterización operativa de clientes y forecast estructural para compras de flor. Lee primero CODEx_PROJECT_CONTEXT.md y respeta sus reglas.

Necesito modificar el código sin romper la lógica funcional:
- FECHA es la fecha oficial de despacho.
- TallosPedidos es la cantidad oficial.
- CODCUSTOM debe salir en todos los exports como cod_cliente.
- Confirmado es histórico real.
- Pendiente es orden real futura y tiene prioridad sobre forecast.
- En proceso es estimado comercial, no histórico real.
- Por verificar/Reproceso son cambios de control.
- La caracterización debe permitir seleccionar un cliente y entender qué pide, cómo lo pide, qué estructuras repite, cómo ha cambiado y cómo se comporta recientemente.
- Los datos recientes pesan más que el histórico completo para recomendaciones operativas.
- No mezcles sólido, surtido, surtido M, rainbow, combo, bulk, bouquet o BQT.
- No castigues clientes de surtidos por no repetir SKU terminado exacto; analiza estabilidad de mix, colores recurrentes y estructura.

Tarea:
[ESCRIBE AQUÍ LO QUE NECESITAS]

Antes de cambiar, revisa los módulos existentes. Después del cambio, asegúrate de que el pipeline siga generando todos los outputs esperados y el Excel consolidado.
```

---

## 26. Criterio de éxito del proyecto

El proyecto será exitoso si permite seleccionar un cliente y entender con datos:

```text
Qué pide normalmente.
Qué está pidiendo recientemente.
Qué cambió.
Qué estructuras se mantienen vigentes.
Qué tipo de pedido domina.
Qué tan estable es su mix de color.
Qué tanto se le cumple.
Qué se puede comprar terminado, casi terminado, por color/base o qué no se debe anticipar.
```

El criterio operativo final es reducir reproceso y mejorar decisiones de compra.

La herramienta debe servir para compras, poscosecha, planeación y comercial, pero el primer usuario operativo es quien decide qué comprar y con cuánto riesgo.
