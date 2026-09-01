$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.\.venv\Scripts\skynet-desktop.exe')) {
    Write-Host 'SKYNET is not installed in .venv yet. Running installer...'
    powershell -ExecutionPolicy Bypass -File .\install.ps1
}

& .\.venv\Scripts\skynet-desktop.exe
