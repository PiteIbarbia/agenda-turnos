@echo off
title Servidor - Agenda de Turnos
echo ========================================================
echo        Iniciando Servidor de Agenda de Turnos
echo ========================================================
echo.
python "%~dp0server.py"
if errorlevel 1 (
    echo.
    echo Ocurrio un error al iniciar el servidor con python.
    pause
)
