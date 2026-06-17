#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f "configurar_credenciales.local.ps1" ]]; then
  echo "No existe configurar_credenciales.local.ps1 en la raiz del proyecto." >&2
  exit 1
fi

while IFS= read -r line; do
  if [[ "$line" =~ ^\$env:([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$ ]]; then
    export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
  fi
done < "configurar_credenciales.local.ps1"

export OP_SALES_USE_SQL_SERVER=1
export PYTHONWARNINGS="ignore:pandas only supports SQLAlchemy connectable:UserWarning"

if [[ -n "${LGF_PYTHON:-}" ]]; then
  PYTHON_EXE="$LGF_PYTHON"
elif [[ -x ".venv/Scripts/python.exe" ]]; then
  PYTHON_EXE=".venv/Scripts/python.exe"
elif [[ -x "carac_clients/Scripts/python.exe" ]]; then
  PYTHON_EXE="carac_clients/Scripts/python.exe"
elif [[ -x "$USERPROFILE/miniconda3/envs/SDG_env/python.exe" ]]; then
  PYTHON_EXE="$USERPROFILE/miniconda3/envs/SDG_env/python.exe"
else
  PYTHON_EXE="python"
fi

DASH_HOST="${LGF_DASH_HOST:-0.0.0.0}"
DASH_PORT="${LGF_DASH_PORT:-8085}"

"$PYTHON_EXE" app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host "$DASH_HOST" \
  --port "$DASH_PORT"
