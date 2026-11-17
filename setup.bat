@echo off
setlocal
cd /d "%~dp0"

echo.
echo === QCar Controller setup ===
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo Python was not found.
        echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
        echo IMPORTANT: tick "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)

echo Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Setup complete. Starting controller...
echo.
".venv\Scripts\python.exe" qcar_controller.py
exit /b 0

:fail
echo.
echo Setup failed. Copy the error shown above and send it to ChatGPT.
pause
exit /b 1
