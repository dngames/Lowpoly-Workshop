@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-Generate.ps1" -GpuIndex 0 %*
pause
