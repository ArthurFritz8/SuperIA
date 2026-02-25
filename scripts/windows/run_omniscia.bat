@echo off
setlocal
cd /d "%~dp0\..\.."

REM Prefer local venv python if present
set "PY=%CD%\.venv\Scripts\python.exe"
if exist "%PY%" (
  echo Using venv: %PY%
) else (
  set "PY=python"
  echo Using system python: %PY%
)

echo.
echo Starting Omniscia...
echo (Type 'sair' to exit)
echo.

if exist "%PY%" (
  "%PY%" -m omniscia run
) else (
  python -m omniscia run
)
echo.
echo Process finished with exit code %ERRORLEVEL%
if not "%OMNI_NO_PAUSE%"=="1" pause
