@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
start "" http://127.0.0.1:8765/
".venv\Scripts\python.exe" run_standalone.py --serve
goto :eof
:error
echo.
echo Preparazione non riuscita. Verificare Python 3.11 o successivo e la connessione Internet.
pause
endlocal

