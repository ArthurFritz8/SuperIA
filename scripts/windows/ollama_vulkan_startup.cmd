@echo off
setlocal

set OLLAMA_VULKAN=1
set OLLAMA_HOST=127.0.0.1:11434

rem Reduce SSD thrash by keeping models loaded longer.
rem (Ollama supports values like "30m", "1h" or seconds.)
set OLLAMA_KEEP_ALIVE=30m

rem Conservative defaults to avoid over-parallelism on a single GPU.
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_MAX_LOADED_MODELS=1

set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
if exist "%OLLAMA_EXE%" (
  start "Ollama Vulkan" /min "%OLLAMA_EXE%" serve
) else (
  rem Fallback (if ollama is on PATH)
  start "Ollama Vulkan" /min ollama serve
)

endlocal
