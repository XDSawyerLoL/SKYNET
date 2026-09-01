$ErrorActionPreference = 'Stop'

$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'SKYNET virtual environment not found. Run install.ps1 first.'
}

Write-Host 'SKYNET voice diagnostics' -ForegroundColor Cyan
Write-Host ''
& $python -m skynet.voice_cli status
Write-Host ''
& $python -m skynet.voice_cli test
