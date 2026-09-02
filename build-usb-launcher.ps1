$ErrorActionPreference = 'Stop'

$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

Write-Host 'SKYNET 0.14 - compilation du lanceur USB autonome' -ForegroundColor Cyan
& $python -m pip install -e '.[portable]'

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name 'SKYNET-USB' `
    --paths '.\src' `
    --collect-submodules 'skynet' `
    --add-data 'src\skynet\voice_worker.py;skynet' `
    .\usb_main.py

if (-not (Test-Path '.\dist\SKYNET-USB.exe')) {
    throw 'La compilation de SKYNET-USB.exe a échoué.'
}

$file = Get-Item '.\dist\SKYNET-USB.exe'
Write-Host "Lanceur créé : $($file.FullName)" -ForegroundColor Green
Write-Host "Taille : $([math]::Round($file.Length / 1MB, 1)) Mo"
Get-FileHash $file.FullName -Algorithm SHA256
