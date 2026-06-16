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

./carac_clients/Scripts/python.exe app_dash.py \
  --data-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos" \
  --host 127.0.0.1 \
  --port 8050
