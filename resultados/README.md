# Resultados generados

Esta carpeta es la salida canonica del flujo activo. Sus subcarpetas y archivos
CSV/XLSX se generan por ejecucion y no deben editarse manualmente.

Estructura esperada:

```text
resultados/
  descriptivos/       # run_descriptivos.py; toda la historia o anos elegidos
  clusters/
    2025/              # run_clusters.py --year 2025
    2026/              # run_clusters.py --year 2026
  forecast_solidos/    # run_forecast_solidos.py
```

La corrida validada existente fue migrada a estas carpetas el 2026-05-25.
Las corridas reemplazadas se conservaron bajo `pruebas antiguas/` y no deben
usarse como entrada regular del dashboard.

Las carpetas antiguas `outputs*` corresponden a pruebas o flujos anteriores y
no son la ruta recomendada para nuevas corridas.
