@echo off
cd /d "%~dp0"
set OP_SALES_USE_SQL_SERVER=1
if "%LGF_DASH_HOST%"=="" set LGF_DASH_HOST=0.0.0.0
if "%LGF_DASH_PORT%"=="" set LGF_DASH_PORT=8085
if "%LGF_PYTHON%"=="" if exist ".\.venv\Scripts\python.exe" set LGF_PYTHON=.\.venv\Scripts\python.exe
if "%LGF_PYTHON%"=="" if exist ".\carac_clients\Scripts\python.exe" set LGF_PYTHON=.\carac_clients\Scripts\python.exe
if "%LGF_PYTHON%"=="" if exist "%USERPROFILE%\miniconda3\envs\SDG_env\python.exe" set LGF_PYTHON=%USERPROFILE%\miniconda3\envs\SDG_env\python.exe
if "%LGF_PYTHON%"=="" set LGF_PYTHON=python
"%LGF_PYTHON%" app_dash.py --data-dir resultados\descriptivos --forecast-dir resultados\forecast_solidos --host %LGF_DASH_HOST% --port %LGF_DASH_PORT% > dash_server_cmd.log 2>&1
