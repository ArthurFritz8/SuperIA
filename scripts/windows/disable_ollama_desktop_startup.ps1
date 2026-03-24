$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath('Startup')
$lnk = Join-Path $startupDir 'Ollama.lnk'
$disabled = Join-Path $startupDir 'Ollama.lnk.disabled'

if (Test-Path $lnk) {
  if (Test-Path $disabled) {
    Remove-Item -Force $disabled
  }
  Rename-Item -Path $lnk -NewName 'Ollama.lnk.disabled'
  Write-Host "Disabled Ollama Desktop auto-start: $disabled" -ForegroundColor Yellow
} else {
  Write-Host "Ollama.lnk not found in Startup: $startupDir" -ForegroundColor DarkGray
}
