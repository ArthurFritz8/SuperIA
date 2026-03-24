param(
  [string]$StartupName = "ollama_vulkan_startup.cmd"
)

$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath('Startup')
$dst = Join-Path $startupDir $StartupName

if (Test-Path $dst) {
  Remove-Item -Path $dst -Force
  Write-Host "Removed Startup entry: $dst" -ForegroundColor Yellow
} else {
  Write-Host "Startup entry not found: $dst" -ForegroundColor DarkGray
}
