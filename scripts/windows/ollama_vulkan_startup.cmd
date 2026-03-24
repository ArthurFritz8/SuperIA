@echo off
setlocal

set OLLAMA_VULKAN=1
set OLLAMA_HOST=127.0.0.1:11434

set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
if exist "%OLLAMA_EXE%" (
  start "Ollama Vulkan" /min "%OLLAMA_EXE%" serve
) else (
  rem Fallback (if ollama is on PATH)
  start "Ollama Vulkan" /min ollama serve
)

endlocal
