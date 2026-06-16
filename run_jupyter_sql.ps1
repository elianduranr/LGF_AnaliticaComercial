$ErrorActionPreference = "Stop"
Set-Location "C:\Proyectos_gaitana\lgf_operativo_project"
if (Test-Path ".\configurar_credenciales.local.ps1") {
    . ".\configurar_credenciales.local.ps1"
}
.\carac_clients\Scripts\python.exe -m jupyter lab
