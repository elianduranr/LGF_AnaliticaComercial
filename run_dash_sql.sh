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

PYTHON_EXE="${PYTHON_EXE:-C:/Users/LGF/miniconda3/envs/SDG_env/python.exe}"

"$PYTHON_EXE" app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 0.0.0.0 \
  --port 8085
