# run.ps1 - Inicia el servidor de la Agenda de Turnos en PowerShell
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Iniciando Servidor de Agenda de Turnos          " -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
python "$PSScriptRoot\server.py"
