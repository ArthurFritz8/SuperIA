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
set "STT=%OMNI_STT_MODE%"
if "%STT%"=="" set "STT=text"
echo (Entrada: %STT%  ^(pode cair pra texto se faltar configuracao^))
echo (Texto: digite sua mensagem e pressione Enter; digite 'sair' para encerrar)
echo (Voz: use OMNI_STT_MODE=vosk ou whisper_openai; para testar: %PY% -m omniscia.app dictate --seconds 6)
echo.

if exist "%PY%" (
  "%PY%" -m omniscia run
) else (
  python -m omniscia run
)
echo.
echo Process finished with exit code %ERRORLEVEL%
if not "%OMNI_NO_PAUSE%"=="1" pause
