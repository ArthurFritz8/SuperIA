@echo off
setlocal

REM Setup "everything" for Omniscia on Windows.
REM - Installs all optional extras + dev tools
REM - Installs Playwright browsers
REM - Runs doctor + tests

cd /d "%~dp0\..\.."

echo [1/5] Activating venv (if exists)...
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
) else (
  echo .venv not found. Create one with: python -m venv .venv
)

echo [2/5] Upgrading pip...
python -m pip install -U pip

echo [3/5] Installing all extras + dev...
python -m pip install -e ".[all]"

echo [4/5] Installing Playwright browsers...
python -m playwright install

echo [5/5] Running doctor + tests...
python -m omniscia.app doctor
python -m pytest

echo Done.
endlocal
