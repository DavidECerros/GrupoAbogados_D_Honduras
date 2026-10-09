@echo off
cd /d "%~dp0"
if exist "runtime\python.exe" (
  "runtime\python.exe" "scripts\run.py"
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "scripts\run.py"
) else (
  echo Ejecute Instalar.ps1 o use el paquete Windows completo.
  pause
)
