param(
  [string]$HostAddr = "127.0.0.1",
  [int]$Port = 11434
)

$ErrorActionPreference = "Stop"

$env:OLLAMA_VULKAN = "1"
$env:OLLAMA_HOST = "$HostAddr`:$Port"

Write-Host "Starting Ollama with Vulkan (GPU) on $($env:OLLAMA_HOST)" -ForegroundColor Cyan
Write-Host "Tip: set OMNI_LLM_BASE_URL=http://$HostAddr`:$Port in your .env" -ForegroundColor DarkGray

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
