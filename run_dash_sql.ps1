$ErrorActionPreference = "Stop"
Set-Location "C:\Users\LGF\Documents\carac_clientes"
if (Test-Path ".\configurar_credenciales.local.ps1") {
    . ".\configurar_credenciales.local.ps1"
}
$env:OP_SALES_USE_SQL_SERVER = "1"
C:\Users\LGF\miniconda3\envs\SDG_env\python.exe app_dash.py --data-dir resultados\descriptivos --forecast-dir resultados\forecast_solidos --host 0.0.0.0 --port 8085
