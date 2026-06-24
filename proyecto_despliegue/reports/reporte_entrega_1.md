# Entrega 1 - Proyecto despliegue LGF

## Problema y contexto

La Gaitana Farms necesita anticipar demanda de productos SOLIDO para apoyar
decisiones comerciales y operativas. El problema no es solo describir ventas:
es entender que volumen, color, producto-color, cliente y pais explican la
demanda futura.

## Pregunta de negocio

Como puede LGF usar su historia de ventas/pedidos para anticipar demanda
semanal de productos SOLIDO y soportar decisiones de compra, planeacion y
poscosecha?

## Datos

EDA y forecast se trabajan desde las bases crudas locales:

- `bases de datos historicas/ventas_facturadas_2021.csv`
- `bases de datos historicas/ventas_facturadas_2022.csv`
- `bases de datos historicas/ventas_facturadas_2023.csv`
- `bases de datos historicas/ventas_facturadas_2024.csv`
- `bases de datos historicas/ventas_facturadas_2025.csv`
- `bases de datos historicas/ventas_facturadas_2026.csv`

Para versionamiento DVC/Git se usa solo la muestra:

- `datos/raw/ventas_facturadas_muestra_2021_2026.csv`

## Exploracion

El EDA principal esta en:

- `notebooks/eda_pronostico_demanda_solidos.ipynb`

Hallazgos principales:

- Base cruda analizada: 1.685.454 registros.
- Rango temporal: 2021-01-04 a 2026-05-16.
- Demanda SOLIDO acumulada: 193.320.621 tallos.
- 472 clientes, 47 paises y 56 colores.
- El promedio movil de 8 semanas obtiene WAPE 20,69%.
- La misma semana del ano anterior obtiene WAPE 14,04%.

El notebook se enfoca en demanda: tendencia semanal, estacionalidad, colores,
producto-color, clientes, paises, volatilidad y correlacion entre colores.

## Prototipo

El soporte del prototipo no es un mockup inventado. Se usan pantallazos del
prototipo existente:

- `supports/prototipo/ventas_general.png`
- `supports/prototipo/forecast_solidos.png`
- `supports/prototipo/visualizador_skus.png`

Estos pantallazos tambien fueron insertados en el Word principal:

- `ENTREGA 1 PROYECTO DESPLIGUE.docx`

## Repositorios

- Git: `https://github.com/elianduranr/LGF_AnaliticaComercial.git`
- Rama preparada para entrega: `proyecto_despliegue_lgf`
- DVC: versiona la muestra local en `datos/raw/`.

## Trabajo en equipo

Reporte separado:

- `reports/reporte_trabajo_equipo.md`


