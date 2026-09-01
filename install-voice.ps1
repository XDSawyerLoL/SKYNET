$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET local neural voice installer' -ForegroundColor Cyan

$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'SKYNET virtual environment not found. Run install.ps1 first.'
}

if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host 'Ensuring eSpeak NG is available for French phonemization...'
    winget install --id eSpeak-NG.eSpeak-NG --exact --accept-package-agreements --accept-source-agreements --silent | Out-Host
} else {
    Write-Warning 'winget not found. Install eSpeak NG manually if French Kokoro phonemization fails.'
}

Write-Host 'Installing Kokoro ONNX runtime...' -ForegroundColor Cyan
& $python -m pip install --upgrade kokoro-onnx soundfile sounddevice 'misaki-fork[en]'

$voiceDir = Join-Path (Get-Location) '.skynet\voice'
New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

$model = Join-Path $voiceDir 'kokoro-v1.0.onnx'
$voices = Join-Path $voiceDir 'voices-v1.0.bin'

if (-not (Test-Path $model)) {
    Write-Host 'Downloading Kokoro neural model (~311 MB)...'
    Invoke-WebRequest -UseBasicParsing `
        -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' `
        -OutFile $model
}

if (-not (Test-Path $voices)) {
    Write-Host 'Downloading Kokoro voices (~27 MB)...'
    Invoke-WebRequest -UseBasicParsing `
        -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' `
        -OutFile $voices
}

Write-Host ''
Write-Host 'Local neural voice installed.' -ForegroundColor Green
Write-Host 'Provider: Kokoro 82M local'
Write-Host 'Default French voice: ff_siwis'
Write-Host 'Restart SKYNET to activate it.'
