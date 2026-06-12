$ErrorActionPreference = "Stop"
Set-Location "C:\Proyectos_gaitana\lgf_operativo_project"
$env:OP_SALES_USE_SQL_SERVER = "1"
.\carac_clients\Scripts\python.exe app_dash.py --data-dir resultados\descriptivos --forecast-dir resultados\forecast_solidos --host 127.0.0.1 --port 8050
