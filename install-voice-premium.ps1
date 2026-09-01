$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - installation de la voix premium locale' -ForegroundColor Cyan

$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Environnement SKYNET introuvable. Lancez install.ps1 avant.'
}

Write-Host 'Installation de Chatterbox Multilingual...' -ForegroundColor Cyan
& $python -m pip install --upgrade chatterbox-tts sounddevice

$voiceDir = Join-Path (Get-Location) '.skynet\voice'
New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

Write-Host 'Préchargement du modèle multilingue V3. Le premier téléchargement peut être volumineux...' -ForegroundColor Cyan
$prewarm = @'
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

device = "cpu"
print("Téléchargement / validation du modèle Chatterbox Multilingual V3...")
model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
print(f"Modèle prêt. Fréquence audio: {model.sr} Hz")
'@
$tempPy = Join-Path $env:TEMP ('skynet-chatterbox-' + [guid]::NewGuid().ToString('N') + '.py')
Set-Content -LiteralPath $tempPy -Value $prewarm -Encoding UTF8
try {
    & $python $tempPy
}
finally {
    Remove-Item -LiteralPath $tempPy -Force -ErrorAction SilentlyContinue
}

Set-Content -LiteralPath (Join-Path $voiceDir 'chatterbox.enabled') -Value 'enabled' -Encoding ASCII

Write-Host ''
Write-Host 'Voix premium activée.' -ForegroundColor Green
Write-Host 'Moteur: Chatterbox Multilingual V3'
Write-Host 'Langue: français'
Write-Host 'Le moteur choisira le GPU seulement si suffisamment de VRAM est libre; sinon il utilisera le CPU.'
Write-Host ''
Write-Host 'Test: .\.venv\Scripts\skynet-voice.exe test'
