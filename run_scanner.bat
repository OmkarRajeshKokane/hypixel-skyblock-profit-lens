@echo off
setlocal

set "PYTHON=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
if exist "%PYTHON%" (
    "%PYTHON%" "%~dp0skyblock_profit_scanner.py" %*
) else (
    py -3 "%~dp0skyblock_profit_scanner.py" %*
)
