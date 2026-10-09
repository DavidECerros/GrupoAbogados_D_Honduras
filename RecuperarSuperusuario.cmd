@echo off
cd /d "%~dp0"
if exist "runtime\python.exe" (
  "runtime\python.exe" "scripts\recover_superuser.py"
) else (
  ".venv\Scripts\python.exe" "scripts\recover_superuser.py"
)
pause
