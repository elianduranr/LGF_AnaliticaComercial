$ErrorActionPreference = "Stop"
Set-Location "C:\Proyectos_gaitana\lgf_operativo_project"
if (Test-Path ".\configurar_credenciales.local.ps1") {
    . ".\configurar_credenciales.local.ps1"
}

Write-Host ("OP_SALES_CONN_STR definido: " + [bool]$env:OP_SALES_CONN_STR)
Write-Host ("OP_SALES_SQL_DRIVER: " + $env:OP_SALES_SQL_DRIVER)
Write-Host ("OP_SALES_SQL_SERVER: " + $env:OP_SALES_SQL_SERVER)
Write-Host ("OP_SALES_SQL_DATABASE: " + $env:OP_SALES_SQL_DATABASE)
Write-Host ("OP_SALES_SQL_USER definido: " + [bool]$env:OP_SALES_SQL_USER)
Write-Host ("OP_SALES_SQL_PASSWORD definido: " + [bool]$env:OP_SALES_SQL_PASSWORD)

$code = @'
import re
from src.lgf_operativo.op_sales_sql import connection_string_from_env, get_connection

conn_str = connection_string_from_env()
masked = re.sub(r"(UID=)[^;]*", r"\1***", conn_str, flags=re.I)
masked = re.sub(r"(PWD=)[^;]*", r"\1***", masked, flags=re.I)
print("CONN_STR:", masked)

with get_connection() as con:
    cursor = con.cursor()
    cursor.execute("SELECT TOP 1 fecha FROM op_sales.fact_sales_line ORDER BY fecha DESC")
    row = cursor.fetchone()
    print("OP_SALES OK:", row[0] if row else "sin filas")
'@
$code | .\carac_clients\Scripts\python.exe -
