param(
  [string]$TaskName = "OllamaVulkanServe11434",
  [int]$Port = 11434
)

$ErrorActionPreference = "Stop"

try {
  Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
} catch {
  # ignore
}

try {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {
  # ignore
}

# Best-effort: stop whatever is using the port
try {
  $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -ne $conn) {
    $pid = $conn.OwningProcess
    if ($pid) {
      Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
  }
} catch {
  # ignore
}

Write-Host "Removed scheduled task (if existed): $TaskName" -ForegroundColor Yellow
