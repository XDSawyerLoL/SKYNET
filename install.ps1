$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET v0.1 bootstrap' -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python launcher (py) not found. Install Python 3.11+ first.'
}

if (-not (Test-Path '.venv')) {
    py -3.11 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
}

if (-not (Test-Path 'workspace')) {
    New-Item -ItemType Directory -Path 'workspace' | Out-Null
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host 'Ollama detected.' -ForegroundColor Green
    Write-Host 'Installed models:'
    ollama list
} else {
    Write-Warning 'Ollama was not found in PATH. Install/start Ollama before launching SKYNET.'
}

Write-Host ''
Write-Host 'Installation complete.' -ForegroundColor Green
Write-Host 'Run: .\.venv\Scripts\skynet.exe'
