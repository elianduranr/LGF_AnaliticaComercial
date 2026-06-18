$env:OP_SALES_SQL_SERVER = "192.168.1.22"
$env:OP_SALES_SQL_DATABASE = "gaitana"
$env:OP_SALES_SQL_DRIVER = "ODBC Driver 18 for SQL Server"
$env:OP_SALES_SQL_USER = "sa"
$env:OP_SALES_SQL_PASSWORD = "G41trn422*$"

$env:ETL_WEBFLOR_SQL_SERVER = "192.168.1.9"
$env:ETL_WEBFLOR_SQL_DATABASE = "WF_Gaitana"
$env:ETL_WEBFLOR_SQL_DRIVER = "ODBC Driver 18 for SQL Server"
$env:ETL_WEBFLOR_SQL_USER = "WebflorRead"
$env:ETL_WEBFLOR_SQL_PASSWORD = "Webflor2020g"

# Python local de esta maquina.
# Si cambias de entorno virtual, cambia solo esta linea.
$env:LGF_PYTHON = "C:\Proyectos_gaitana\lgf_operativo_project\carac_clients\Scripts\python.exe"

# Puerto local de esta maquina.
# Este puerto es para trabajar localmente sin pisar el puerto normal del despliegue.
$env:LGF_DASH_PORT = "8067"
$env:LGF_DASH_HOST = "127.0.0.1"
