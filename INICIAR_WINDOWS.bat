@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python iniciar.py
) else (
    py -3 iniciar.py
)
if errorlevel 1 (
    echo Nao foi possivel iniciar. Confira o erro acima e se Python 3.12 ou superior esta instalado.
    pause
)
