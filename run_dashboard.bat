@echo off
setlocal

set "PYTHON=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
start "" /B powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000'"
if exist "%PYTHON%" (
    "%PYTHON%" "%~dp0web_dashboard.py" %*
) else (
    py -3 "%~dp0web_dashboard.py" %*
)
