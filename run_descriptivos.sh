#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f "configurar_credenciales.local.ps1" ]]; then
  while IFS= read -r line; do
    if [[ "$line" =~ ^\$env:([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$ ]]; then
      export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
    fi
  done < "configurar_credenciales.local.ps1"
fi

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

SOURCE="${LGF_DATA_SOURCE:-sql}"

"$PYTHON_EXE" run_descriptivos.py \
  --source "$SOURCE" \
  --output "resultados/descriptivos" \
  --no-cache

"$PYTHON_EXE" materializar_op_sales_resultados_sql.py \
  --descriptivos-dir "resultados/descriptivos" \
  --forecast-dir "resultados/forecast_solidos"
