import os
import runpy
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ["OP_SALES_USE_SQL_SERVER"] = "1"
sys.argv = [
    "app_dash.py",
    "--data-dir",
    "resultados/descriptivos",
    "--forecast-dir",
    "resultados/forecast_solidos",
    "--host",
    "127.0.0.1",
    "--port",
    "8050",
]
try:
    runpy.run_path(str(ROOT / "app_dash.py"), run_name="__main__")
except Exception:
    (ROOT / "dash_launcher_error.log").write_text(traceback.format_exc(), encoding="utf-8")
    raise
