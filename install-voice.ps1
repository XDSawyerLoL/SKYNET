$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - installation de la voix neuronale locale' -ForegroundColor Cyan

$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Environnement SKYNET introuvable. Lancez install.ps1 avant.'
}

if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host 'Vérification de eSpeak NG pour la phonémisation française...'
    winget install --id eSpeak-NG.eSpeak-NG --exact --accept-package-agreements --accept-source-agreements --silent | Out-Host
} else {
    Write-Warning 'winget est introuvable. Installez eSpeak NG manuellement si la phonémisation française échoue.'
}

Write-Host 'Installation du runtime Kokoro ONNX...' -ForegroundColor Cyan
& $python -m pip install --upgrade kokoro-onnx soundfile sounddevice 'misaki-fork[en]'

$voiceDir = Join-Path (Get-Location) '.skynet\voice'
New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

$model = Join-Path $voiceDir 'kokoro-v1.0.onnx'
$voices = Join-Path $voiceDir 'voices-v1.0.bin'

if (-not (Test-Path $model)) {
    Write-Host 'Téléchargement du modèle Kokoro (~311 Mo)...'
    Invoke-WebRequest -UseBasicParsing `
        -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' `
        -OutFile $model
}

if (-not (Test-Path $voices)) {
    Write-Host 'Téléchargement des voix Kokoro (~27 Mo)...'
    Invoke-WebRequest -UseBasicParsing `
        -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' `
        -OutFile $voices
}

Write-Host ''
Write-Host 'Voix locale rapide installée.' -ForegroundColor Green
Write-Host 'Moteur : Kokoro 82M local'
Write-Host 'Voix française : ff_siwis'
Write-Host ''
Write-Host 'Pour une voix beaucoup plus naturelle :'
Write-Host 'powershell -ExecutionPolicy Bypass -File .\install-voice-premium.ps1' -ForegroundColor Yellow
Write-Host ''
Write-Host 'Redémarrez SKYNET pour activer la voix.'
