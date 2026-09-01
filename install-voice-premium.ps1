$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - installation voix premium locale' -ForegroundColor Cyan

$basePython = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $basePython)) {
    throw 'Environnement SKYNET introuvable. Lancez install.ps1 avant.'
}

$voiceDir = Join-Path (Get-Location) '.skynet\voice'
$voiceVenv = Join-Path $voiceDir 'venv'
$voicePython = Join-Path $voiceVenv 'Scripts\python.exe'
$marker = Join-Path $voiceDir 'chatterbox.enabled'
$worker = Join-Path (Get-Location) 'src\skynet\voice_worker.py'

New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue

if (-not (Test-Path $worker)) {
    throw 'voice_worker.py introuvable. Lancez update.ps1 puis recommencez.'
}

Write-Host 'Installation des composants audio legers dans le coeur SKYNET...'
& $basePython -m pip install --upgrade sounddevice soundfile
if ($LASTEXITCODE -ne 0) { throw 'Echec installation composants audio de base.' }

Write-Host 'Creation d un environnement vocal ISOLE...' -ForegroundColor Cyan
if (Test-Path $voiceVenv) {
    Remove-Item -LiteralPath $voiceVenv -Recurse -Force
}
& $basePython -m venv $voiceVenv
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $voicePython)) {
    throw 'Impossible de creer l environnement vocal isole.'
}

& $voicePython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'Echec mise a niveau pip vocal.' }

Write-Host 'Installation de Chatterbox Multilingual depuis la version officielle actuelle...' -ForegroundColor Cyan
& $voicePython -m pip install --upgrade 'https://github.com/resemble-ai/chatterbox/archive/refs/heads/master.zip' soundfile
if ($LASTEXITCODE -ne 0) {
    throw 'Echec installation Chatterbox. Le coeur SKYNET reste intact.'
}

Write-Host 'Verification des dependances du moteur vocal...'
& $voicePython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw 'Conflit detecte dans l environnement vocal isole. Activation annulee.'
}

Write-Host 'Prechargement et validation REELLE du modele premium...' -ForegroundColor Cyan
$env:PYTHONUTF8 = '1'
& $voicePython $worker --prewarm
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
    throw 'Le modele premium n a pas passe le prechargement. Il NE sera pas marque comme actif.'
}

Set-Content -LiteralPath $marker -Value 'enabled' -Encoding ASCII

Write-Host ''
Write-Host 'Voix premium correctement activee.' -ForegroundColor Green
Write-Host 'Moteur : Chatterbox Multilingual V3 (si supporte par la version officielle)'
Write-Host 'Langue : francais'
Write-Host 'Isolation : .skynet\voice\venv'
Write-Host 'Le modele reste charge pendant la session SKYNET pour reduire la latence.'
Write-Host ''
Write-Host 'Test : .\.venv\Scripts\skynet-voice.exe test'
