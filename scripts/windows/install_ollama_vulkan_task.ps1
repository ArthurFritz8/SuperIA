param(
  [string]$TaskName = "OllamaVulkanServe11434",
  [string]$HostAddr = "127.0.0.1",
  [int]$Port = 11434
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serveScript = Join-Path $scriptDir "ollama_vulkan_serve.ps1"
if (-not (Test-Path $serveScript)) {
  throw "Missing script: $serveScript"
}

# Best-effort: stop anything already using the target port
try {
  $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -ne $conn) {
    $pid = $conn.OwningProcess
    if ($pid) {
      Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 500
    }
  }
} catch {
  # ignore
}

$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$serveScript`" -HostAddr $HostAddr -Port $Port"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$userId = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited

try {
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Start Ollama with Vulkan (GPU) on ${HostAddr}:$Port" -Force | Out-Null
  Start-ScheduledTask -TaskName $TaskName

  Write-Host "Installed and started scheduled task: $TaskName" -ForegroundColor Green
  Write-Host "SuperIA should point to: OMNI_LLM_BASE_URL=http://$HostAddr`:$Port" -ForegroundColor DarkGray
  Write-Host "Verify with: set OLLAMA_HOST=$HostAddr`:$Port; ollama ps" -ForegroundColor DarkGray
} catch {
  Write-Host "Could not register scheduled task (likely needs admin/policy blocks it): $($_.Exception.Message)" -ForegroundColor Yellow

  $startupInstaller = Join-Path $scriptDir "install_ollama_vulkan_startup.ps1"
  if (Test-Path $startupInstaller) {
    Write-Host "Falling back to Startup folder method (no admin)." -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$startupInstaller"
  } else {
    throw
  }
}

