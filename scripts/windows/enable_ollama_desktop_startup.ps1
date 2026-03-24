$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath('Startup')
$disabled = Join-Path $startupDir 'Ollama.lnk.disabled'
$lnk = Join-Path $startupDir 'Ollama.lnk'

if (Test-Path $disabled) {
  if (Test-Path $lnk) {
    Remove-Item -Force $lnk
  }
  Rename-Item -Path $disabled -NewName 'Ollama.lnk'
  Write-Host "Enabled Ollama Desktop auto-start: $lnk" -ForegroundColor Green
} else {
  Write-Host "Ollama.lnk.disabled not found in Startup: $startupDir" -ForegroundColor DarkGray
}
