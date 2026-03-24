$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$uninstallVulkanStartup = Join-Path $scriptDir "uninstall_ollama_vulkan_startup.ps1"
$enableDesktop = Join-Path $scriptDir "enable_ollama_desktop_startup.ps1"

if (Test-Path $uninstallVulkanStartup) {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$uninstallVulkanStartup" | Out-Host
}

if (Test-Path $enableDesktop) {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$enableDesktop" | Out-Host
}

Write-Host "Rollback done: removed Vulkan Startup + re-enabled Ollama Desktop Startup (if present)." -ForegroundColor Yellow
