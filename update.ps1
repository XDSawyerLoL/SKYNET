$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET updater' -ForegroundColor Cyan

$root = (Get-Location).Path
$tempRoot = Join-Path $env:TEMP ('skynet-update-' + [guid]::NewGuid().ToString('N'))
$zipPath = Join-Path $tempRoot 'main.zip'
$extractPath = Join-Path $tempRoot 'extract'

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    Write-Host 'Downloading latest SKYNET main...' -ForegroundColor Cyan
    Invoke-WebRequest -UseBasicParsing `
        -Uri 'https://github.com/XDSawyerLoL/SKYNET/archive/refs/heads/main.zip' `
        -OutFile $zipPath

    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
    $source = Join-Path $extractPath 'SKYNET-main'
    if (-not (Test-Path $source)) {
        throw 'Downloaded archive structure is invalid.'
    }

    $preserve = @('.env', '.skynet', 'workspace', '.venv')
    Write-Host 'Updating application files while preserving local state...' -ForegroundColor Cyan

    Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
        if ($preserve -contains $_.Name) { return }
        $destination = Join-Path $root $_.Name
        if ($_.PSIsContainer) {
            if (Test-Path $destination) {
                Remove-Item -LiteralPath $destination -Recurse -Force
            }
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }
    }

    if (-not (Test-Path '.\.venv\Scripts\python.exe')) {
        Write-Host 'Virtual environment missing. Running installer...' -ForegroundColor Yellow
        powershell -ExecutionPolicy Bypass -File .\install.ps1
    } else {
        Write-Host 'Refreshing Python package and dependencies...' -ForegroundColor Cyan
        & .\.venv\Scripts\python.exe -m pip install -e .
    }

    Write-Host ''
    Write-Host 'SKYNET is up to date.' -ForegroundColor Green
    Write-Host 'Launch: powershell -ExecutionPolicy Bypass -File .\launch.ps1'
    if (Test-Path '.\install-voice.ps1') {
        Write-Host 'Optional neural voice: powershell -ExecutionPolicy Bypass -File .\install-voice.ps1'
    }
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
