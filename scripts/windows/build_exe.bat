@echo off
setlocal
cd /d "%~dp0\..\.."

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
echo ERROR: .venv not found. Create it and install deps first.
echo Example:
echo   python -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1
)

echo Installing PyInstaller...
"%PY%" -m pip install --upgrade pyinstaller

echo.
echo Building EXE...
echo Output: dist\omniscia.exe
echo.

"%PY%" -m PyInstaller --noconfirm --clean --onefile --name omniscia omniscia\__main__.py

echo.
echo Done. Run: dist\omniscia.exe run
if not "%OMNI_NO_PAUSE%"=="1" pause
