@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run setup.bat first.
    pause
    exit /b 1
)

echo Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto :fail

echo Building QCarController.exe...
".venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name QCarController ^
  --collect-all bleak ^
  --collect-all Crypto ^
  qcar_controller.py

if errorlevel 1 goto :fail

echo.
echo Done.
echo EXE: %CD%\dist\QCarController.exe
pause
exit /b 0

:fail
echo Build failed.
pause
exit /b 1
