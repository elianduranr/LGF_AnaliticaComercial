@echo off
cd /d C:\Proyectos_gaitana\lgf_operativo_project
set OP_SALES_USE_SQL_SERVER=1
.\carac_clients\Scripts\python.exe app_dash.py --data-dir resultados\descriptivos --forecast-dir resultados\forecast_solidos --host 127.0.0.1 --port 8050 > dash_server_cmd.log 2>&1
