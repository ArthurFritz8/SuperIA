param(
  [string]$StartupName = "ollama_vulkan_startup.cmd"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $scriptDir $StartupName
if (-not (Test-Path $src)) {
  throw "Missing file: $src"
}

$startupDir = [Environment]::GetFolderPath('Startup')
$dst = Join-Path $startupDir $StartupName

Copy-Item -Path $src -Destination $dst -Force

Write-Host "Installed Startup entry: $dst" -ForegroundColor Green
Write-Host "This will start Ollama Vulkan (GPU) on every login (127.0.0.1:11434)." -ForegroundColor DarkGray
Write-Host "SuperIA should use: OMNI_LLM_BASE_URL=http://127.0.0.1:11434" -ForegroundColor DarkGray

# Start now (optional convenience)
try {
  Start-Process -FilePath $dst -WindowStyle Minimized
  Write-Host "Started now." -ForegroundColor DarkGray
} catch {
  Write-Host "Installed OK, but could not auto-start now: $($_.Exception.Message)" -ForegroundColor Yellow
}
