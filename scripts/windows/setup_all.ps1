# Setup "everything" for Omniscia on Windows.
# - Installs all optional extras + dev tools
# - Installs Playwright browsers
# - Runs doctor + tests

$ErrorActionPreference = 'Stop'

Set-Location (Resolve-Path "$PSScriptRoot\..\..")

Write-Host "[1/5] Activating venv (if exists)..."
if (Test-Path ".venv\Scripts\Activate.ps1") {
  . .venv\Scripts\Activate.ps1
} else {
  Write-Host ".venv not found. Create one with: python -m venv .venv"
}

Write-Host "[2/5] Upgrading pip..."
python -m pip install -U pip

Write-Host "[3/5] Installing all extras + dev..."
python -m pip install -e ".[all]"

Write-Host "[4/5] Installing Playwright browsers..."
python -m playwright install

Write-Host "[5/5] Running doctor + tests..."
python -m omniscia.app doctor
python -m pytest

Write-Host "Done."
