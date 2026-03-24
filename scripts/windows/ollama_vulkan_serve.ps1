param(
  [string]$HostAddr = "127.0.0.1",
  [int]$Port = 11434
)

$ErrorActionPreference = "Stop"

$env:OLLAMA_VULKAN = "1"
$env:OLLAMA_HOST = "$HostAddr`:$Port"

Write-Host "Starting Ollama with Vulkan (GPU) on $($env:OLLAMA_HOST)" -ForegroundColor Cyan
Write-Host "Tip: set OMNI_LLM_BASE_URL=http://$HostAddr`:$Port in your .env" -ForegroundColor DarkGray

function Get-ListenerPid {
  param(
    [string]$HostAddr,
    [int]$Port
  )

  # Prefer Get-NetTCPConnection when available.
  try {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
      Where-Object { $_.LocalAddress -eq $HostAddr -or $_.LocalAddress -eq "0.0.0.0" -or $_.LocalAddress -eq "::" } |
      Select-Object -First 1
    if ($null -ne $conn -and $conn.OwningProcess) {
      return [int]$conn.OwningProcess
    }
  } catch {
    # ignore and fall back
  }

  # Fallback to netstat parsing.
  try {
    $pattern = ":$Port\s+LISTENING\s+(\d+)$"
    $line = netstat -ano -p tcp | Select-String -Pattern $pattern | Select-Object -First 1
    if ($null -ne $line -and $line.Matches.Count -gt 0) {
      return [int]$line.Matches[0].Groups[1].Value
    }
  } catch {
    # ignore
  }

  return $null
}

$listenerPid = Get-ListenerPid -HostAddr $HostAddr -Port $Port
if ($null -ne $listenerPid) {
  try {
    $proc = Get-Process -Id $listenerPid -ErrorAction Stop
    $pname = [string]$proc.ProcessName
  } catch {
    $proc = $null
    $pname = "(unknown)"
  }

  if ($pname -and $pname.ToLowerInvariant() -eq "ollama") {
    Write-Host "Port $HostAddr`:$Port is already in use by Ollama (pid=$listenerPid). Stopping it..." -ForegroundColor Yellow
    try {
      Stop-Process -Id $listenerPid -Force -ErrorAction Stop
      Start-Sleep -Milliseconds 900
    } catch {
      throw "Failed to stop existing Ollama (pid=$listenerPid). Close Ollama Desktop (tray icon) or kill ollama.exe, then retry."
    }
  } else {
    throw "Port $HostAddr`:$Port is already in use by '$pname' (pid=$listenerPid). Close that process or pick another port, then retry."
  }
}

$ollamaCmd = (Get-Command ollama -ErrorAction SilentlyContinue)
if ($null -ne $ollamaCmd -and $ollamaCmd.Source) {
  $ollamaExe = $ollamaCmd.Source
} else {
  $ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
}

if (-not (Test-Path $ollamaExe)) {
  throw "ollama.exe not found. Expected at: $ollamaExe"
}

& $ollamaExe serve
