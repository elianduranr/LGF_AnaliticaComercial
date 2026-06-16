$ErrorActionPreference = "Stop"
Set-Location "C:\Proyectos_gaitana\lgf_operativo_project"
if (Test-Path ".\configurar_credenciales.local.ps1") {
    . ".\configurar_credenciales.local.ps1"
}
.\carac_clients\Scripts\python.exe cargar_op_sales_sql.py @args
