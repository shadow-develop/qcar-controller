@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup is required.
    call setup.bat
    exit /b %errorlevel%
)

".venv\Scripts\python.exe" qcar_controller.py
if errorlevel 1 pause
