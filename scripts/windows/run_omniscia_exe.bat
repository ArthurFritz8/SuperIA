@echo off
setlocal
cd /d "%~dp0\..\.."

if not exist "dist\omniscia.exe" (
  echo ERROR: dist\omniscia.exe not found.
  echo Run scripts\windows\build_exe.bat first.
  if not "%OMNI_NO_PAUSE%"=="1" pause
  exit /b 1
)

dist\omniscia.exe run
echo.
echo Process finished with exit code %ERRORLEVEL%
if not "%OMNI_NO_PAUSE%"=="1" pause
