$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - reparation environnement principal' -ForegroundColor Cyan
Write-Host 'Fermez SKYNET avant de continuer.' -ForegroundColor Yellow

$venv = Join-Path (Get-Location) '.venv'
if (Test-Path $venv) {
    Write-Host 'Suppression de l ancien environnement Python contamine...'
    Remove-Item -LiteralPath $venv -Recurse -Force
}

Write-Host 'Reinstallation du coeur SKYNET...'
powershell -ExecutionPolicy Bypass -File .\install.ps1
if ($LASTEXITCODE -ne 0) { throw 'Echec reinstallation du coeur SKYNET.' }

Write-Host 'Reinstallation du moteur vocal rapide / secours...'
powershell -ExecutionPolicy Bypass -File .\install-voice.ps1
if ($LASTEXITCODE -ne 0) { throw 'Echec reinstallation de la voix de secours.' }

Write-Host 'Verification finale des dependances du coeur...'
& .\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) {
    throw 'Des conflits persistent dans le coeur SKYNET.'
}

Write-Host ''
Write-Host 'Environnement principal repare.' -ForegroundColor Green
Write-Host 'Les dossiers .skynet et workspace n ont pas ete modifies.'
Write-Host 'Vous pouvez maintenant relancer install-voice-premium.ps1.'
