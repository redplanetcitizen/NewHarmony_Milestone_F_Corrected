@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"
start "" http://127.0.0.1:8765/
"%PYTHON_EXE%" -m http.server 8765 --bind 127.0.0.1 --directory companion\dashboard
endlocal

