$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - installation voix premium féminine locale' -ForegroundColor Cyan

$basePython = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $basePython)) {
    throw 'Environnement SKYNET introuvable. Lancez install.ps1 avant.'
}

$voiceDir = Join-Path (Get-Location) '.skynet\voice'
$voiceVenv = Join-Path $voiceDir 'venv'
$voicePython = Join-Path $voiceVenv 'Scripts\python.exe'
$marker = Join-Path $voiceDir 'chatterbox.enabled'
$reference = Join-Path $voiceDir 'reference.wav'
$validation = Join-Path $voiceDir 'premium-validation.wav'
$worker = Join-Path (Get-Location) 'src\skynet\voice_worker.py'

New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $validation -Force -ErrorAction SilentlyContinue

if (-not (Test-Path $worker)) {
    throw 'voice_worker.py introuvable. Lancez update.ps1 puis recommencez.'
}

Write-Host 'Vérification du moteur féminin de référence...' -ForegroundColor Cyan
$kokoroModel = Join-Path $voiceDir 'kokoro-v1.0.onnx'
$kokoroVoices = Join-Path $voiceDir 'voices-v1.0.bin'
if (-not (Test-Path $kokoroModel) -or -not (Test-Path $kokoroVoices)) {
    Write-Host 'Kokoro féminin absent : installation de la voix locale de base...'
    powershell -ExecutionPolicy Bypass -File .\install-voice.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Impossible d installer le moteur féminin de référence.' }
}

Write-Host 'Installation des composants audio légers dans le coeur SKYNET...'
& $basePython -m pip install --upgrade 'numpy>=2.0.2' kokoro-onnx sounddevice soundfile 'misaki-fork[en]'
if ($LASTEXITCODE -ne 0) { throw 'Echec installation composants audio de base.' }

if (Test-Path $reference) {
    Write-Host 'Référence vocale personnalisée détectée : elle sera conservée.' -ForegroundColor Green
} else {
    Write-Host 'Aucune référence personnalisée : création de l identité vocale féminine SKYNET...' -ForegroundColor Cyan
    $referenceScript = @'
from pathlib import Path
import soundfile as sf
from kokoro_onnx import Kokoro
from misaki import espeak
from misaki.espeak import EspeakG2P

voice_dir = Path(r"__VOICE_DIR__")
model_path = voice_dir / "kokoro-v1.0.onnx"
voices_path = voice_dir / "voices-v1.0.bin"
reference_path = voice_dir / "reference.wav"

_ = espeak.EspeakFallback(british=False)
g2p = EspeakG2P(language="fr-fr")
text = (
    "Bonsoir. Je suis SKYNET. Ma voix est initialisée. "
    "Mémoire persistante en ligne. Gouvernance active. Tous les systèmes sont opérationnels."
)
phonemes, _meta = g2p(text)
if not phonemes:
    raise RuntimeError("phonémisation française impossible")
kokoro = Kokoro(str(model_path), str(voices_path))
samples, sample_rate = kokoro.create(
    phonemes,
    voice="ff_siwis",
    speed=0.94,
    is_phonemes=True,
)
if samples is None or len(samples) == 0:
    raise RuntimeError("Kokoro n a produit aucun audio")
sf.write(reference_path, samples, sample_rate, subtype="PCM_16")
if not reference_path.exists() or reference_path.stat().st_size < 20000:
    raise RuntimeError("référence féminine générée invalide")
print(reference_path)
'@
    $escapedVoiceDir = $voiceDir.Replace('\', '\\')
    $referenceScript = $referenceScript.Replace('__VOICE_DIR__', $escapedVoiceDir)
    $tempRef = Join-Path $env:TEMP ('skynet-female-reference-' + [guid]::NewGuid().ToString('N') + '.py')
    Set-Content -LiteralPath $tempRef -Value $referenceScript -Encoding UTF8
    try {
        & $basePython $tempRef
        if ($LASTEXITCODE -ne 0) { throw 'Echec génération référence féminine SKYNET.' }
    }
    finally {
        Remove-Item -LiteralPath $tempRef -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $reference)) {
    throw 'La référence féminine SKYNET n a pas été créée.'
}

Write-Host 'Création d un environnement vocal premium ISOLE...' -ForegroundColor Cyan
if (Test-Path $voiceVenv) {
    Remove-Item -LiteralPath $voiceVenv -Recurse -Force
}
& $basePython -m venv $voiceVenv
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $voicePython)) {
    throw 'Impossible de créer l environnement vocal isolé.'
}

& $voicePython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'Echec mise à niveau pip vocal.' }

Write-Host 'Installation de Chatterbox Multilingual depuis la version officielle actuelle...' -ForegroundColor Cyan
& $voicePython -m pip install --upgrade 'https://github.com/resemble-ai/chatterbox/archive/refs/heads/master.zip' soundfile
if ($LASTEXITCODE -ne 0) {
    throw 'Echec installation Chatterbox. Le coeur SKYNET reste intact.'
}

Write-Host 'Vérification des dépendances du moteur vocal...'
& $voicePython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw 'Conflit détecté dans l environnement vocal isolé. Activation annulée.'
}

$env:PYTHONUTF8 = '1'
Write-Host 'Préchargement du modèle premium...' -ForegroundColor Cyan
& $voicePython $worker --prewarm
if ($LASTEXITCODE -ne 0) {
    throw 'Le modèle premium n a pas passé le préchargement.'
}

Write-Host 'Validation réelle avec la référence féminine...' -ForegroundColor Cyan
& $voicePython $worker --self-test --reference $reference --output $validation
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $validation)) {
    Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
    throw 'La voix premium féminine n a pas passé le test réel. Activation annulée.'
}
Remove-Item -LiteralPath $validation -Force -ErrorAction SilentlyContinue

Set-Content -LiteralPath $marker -Value 'female-reference-validated' -Encoding ASCII

Write-Host ''
Write-Host 'Voix premium féminine correctement activée.' -ForegroundColor Green
Write-Host 'Moteur : Chatterbox Multilingual + identité féminine SKYNET'
Write-Host 'Langue : français'
Write-Host 'Référence : .skynet\voice\reference.wav'
Write-Host 'Isolation : .skynet\voice\venv'
Write-Host 'Aucune voix masculine ne sera utilisée en secours.'
Write-Host ''
Write-Host 'Test : .\.venv\Scripts\skynet-voice.exe test'
