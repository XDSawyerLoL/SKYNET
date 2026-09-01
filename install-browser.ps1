$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Run install.ps1 first so .venv exists.'
}

Write-Host 'Installing optional local Playwright browser harness...'
& $python -m pip install playwright
& $python -m playwright install chromium

Write-Host 'Interactive local browser ready. No cloud browser is required.'
