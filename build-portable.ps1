$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - construction portable Windows' -ForegroundColor Cyan

$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Environnement SKYNET introuvable. Lancez install.ps1 avant.'
}

Write-Host 'Installation des dépendances de packaging...'
& $python -m pip install --upgrade -e '.[portable]'
if ($LASTEXITCODE -ne 0) { throw 'Echec installation PyInstaller.' }

Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue

Write-Host 'Construction de SKYNET-Portable.exe...' -ForegroundColor Cyan
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name 'SKYNET-Portable' `
    --paths '.\src' `
    --collect-submodules 'skynet' `
    --add-data 'src\skynet\voice_worker.py;skynet' `
    .\portable_main.py
if ($LASTEXITCODE -ne 0) { throw 'Echec construction du portable.' }

$exe = '.\dist\SKYNET-Portable.exe'
if (-not (Test-Path $exe)) { throw 'PyInstaller n a pas produit SKYNET-Portable.exe.' }

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ''
Write-Host "Portable prêt : $exe ($sizeMb Mo)" -ForegroundColor Green
Write-Host 'Copiez ce fichier sur une clé USB et lancez-le sur Windows 10/11 x64.'
Write-Host 'Les données persistantes seront créées à côté de l EXE : .skynet et workspace.'
Write-Host 'Pour les réponses IA, Ollama doit être accessible sur le PC cible.'
