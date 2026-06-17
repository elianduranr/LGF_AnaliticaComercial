$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Test-Path ".\configurar_credenciales.local.ps1") {
    . ".\configurar_credenciales.local.ps1"
}

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

& $python run_descriptivos.py --output "resultados/descriptivos"
