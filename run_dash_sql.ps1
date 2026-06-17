$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Test-Path ".\configurar_credenciales.local.ps1") {
    . ".\configurar_credenciales.local.ps1"
}
$env:OP_SALES_USE_SQL_SERVER = "1"

$python = $env:LGF_PYTHON
if (-not $python) {
    if (Test-Path ".\.venv\Scripts\python.exe") {
        $python = ".\.venv\Scripts\python.exe"
    } elseif (Test-Path ".\carac_clients\Scripts\python.exe") {
        $python = ".\carac_clients\Scripts\python.exe"
    } elseif (Test-Path "$env:USERPROFILE\miniconda3\envs\SDG_env\python.exe") {
        $python = "$env:USERPROFILE\miniconda3\envs\SDG_env\python.exe"
    } else {
        $python = "python"
    }
}

$hostName = if ($env:LGF_DASH_HOST) { $env:LGF_DASH_HOST } else { "0.0.0.0" }
$port = if ($env:LGF_DASH_PORT) { $env:LGF_DASH_PORT } else { "8085" }

& $python app_dash.py --data-dir resultados\descriptivos --forecast-dir resultados\forecast_solidos --host $hostName --port $port
