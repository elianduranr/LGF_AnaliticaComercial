@echo off
cd /d C:\Users\LGF\Documents\carac_clientes
set OP_SALES_USE_SQL_SERVER=1
C:\Users\LGF\miniconda3\envs\SDG_env\python.exe app_dash.py --data-dir resultados\descriptivos --forecast-dir resultados\forecast_solidos --host 0.0.0.0 --port 8085 > dash_server_cmd.log 2>&1
