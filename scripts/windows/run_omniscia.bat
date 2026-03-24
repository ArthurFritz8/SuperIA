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
if /i "%OMNI_STT_MODE%"=="vosk" (
  echo (Modo voz: fale durante a gravacao; digite 'sair' para encerrar)
) else if /i "%OMNI_STT_MODE%"=="whisper_openai" (
  echo (Modo voz: fale durante a gravacao; digite 'sair' para encerrar)
) else (
  echo (Modo texto: digite sua mensagem e pressione Enter; digite 'sair' para encerrar)
  echo (Dica: para voz, use OMNI_STT_MODE=vosk ou rode: %PY% -m omniscia run --stt-mode vosk)
)
echo.

if exist "%PY%" (
  "%PY%" -m omniscia run
) else (
  python -m omniscia run
)
echo.
echo Process finished with exit code %ERRORLEVEL%
if not "%OMNI_NO_PAUSE%"=="1" pause
