import os
import runpy
import sys
import traceback
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ["OP_SALES_USE_SQL_SERVER"] = "1"
host = os.environ.get("LGF_DASH_HOST", "0.0.0.0")
port = os.environ.get("LGF_DASH_PORT", "8085")
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)
print(f"Cargando dashboard desde SQL Server. Puede tardar 1-2 minutos antes de abrir el puerto {port}.", flush=True)
print(f"Cuando termine la carga, abre http://127.0.0.1:{port} o http://<IP_LAN>:{port}", flush=True)
sys.argv = [
    "app_dash.py",
    "--data-dir",
    "resultados/descriptivos",
    "--forecast-dir",
    "resultados/forecast_solidos",
    "--host",
    host,
    "--port",
    port,
]
try:
    runpy.run_path(str(ROOT / "app_dash.py"), run_name="__main__")
except Exception:
    (ROOT / "dash_launcher_error.log").write_text(traceback.format_exc(), encoding="utf-8")
    raise
