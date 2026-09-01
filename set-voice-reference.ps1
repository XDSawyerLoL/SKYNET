param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET - installation d une référence vocale personnalisée' -ForegroundColor Cyan

$source = Resolve-Path -LiteralPath $Path -ErrorAction Stop
if ([System.IO.Path]::GetExtension($source.Path).ToLowerInvariant() -ne '.wav') {
    throw 'Le fichier doit être un WAV. Utilisez le WAV préparé pour SKYNET.'
}

$basePython = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $basePython)) {
    throw 'Environnement SKYNET introuvable. Lancez install.ps1 avant.'
}

$voiceDir = Join-Path (Get-Location) '.skynet\voice'
$reference = Join-Path $voiceDir 'reference.wav'
$tempReference = Join-Path $voiceDir 'reference.new.wav'
$backup = Join-Path $voiceDir 'reference.backup.wav'
$marker = Join-Path $voiceDir 'chatterbox.enabled'
$voicePython = Join-Path $voiceDir 'venv\Scripts\python.exe'
$worker = Join-Path (Get-Location) 'src\skynet\voice_worker.py'
$validation = Join-Path $voiceDir 'reference-validation.wav'

New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
Copy-Item -LiteralPath $source.Path -Destination $tempReference -Force

$checkScript = @'
from pathlib import Path
import soundfile as sf

p = Path(r"__REFERENCE__")
info = sf.info(str(p))
duration = info.frames / float(info.samplerate)
if duration < 3.0:
    raise SystemExit("Référence trop courte : %.2f s" % duration)
if duration > 90.0:
    raise SystemExit("Référence trop longue : %.2f s" % duration)
if info.channels < 1 or info.channels > 2:
    raise SystemExit("Nombre de canaux non supporté : %s" % info.channels)
if info.samplerate < 16000:
    raise SystemExit("Fréquence audio trop faible : %s Hz" % info.samplerate)
print("Référence valide : %.2f s, %s Hz, %s canal/canaux" % (duration, info.samplerate, info.channels))
'@
$checkScript = $checkScript.Replace('__REFERENCE__', $tempReference.Replace('\', '\\'))
$tempPy = Join-Path $env:TEMP ('skynet-reference-check-' + [guid]::NewGuid().ToString('N') + '.py')
Set-Content -LiteralPath $tempPy -Value $checkScript -Encoding UTF8
try {
    & $basePython $tempPy
    if ($LASTEXITCODE -ne 0) { throw 'La référence vocale n a pas passé la validation audio.' }
}
finally {
    Remove-Item -LiteralPath $tempPy -Force -ErrorAction SilentlyContinue
}

if (Test-Path $reference) {
    Copy-Item -LiteralPath $reference -Destination $backup -Force
}

# Une référence personnalisée doit être revalidée avant que Chatterbox soit déclaré actif.
Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue

if ((Test-Path $voicePython) -and (Test-Path $worker)) {
    Write-Host 'Validation de la nouvelle identité vocale avec Chatterbox...' -ForegroundColor Cyan
    $env:PYTHONUTF8 = '1'
    & $voicePython $worker --self-test --reference $tempReference --output $validation
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $validation)) {
        Remove-Item -LiteralPath $tempReference -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $validation -Force -ErrorAction SilentlyContinue
        throw 'Chatterbox n a pas validé cette référence. L ancienne voix est conservée dans reference.backup.wav.'
    }
    Remove-Item -LiteralPath $validation -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $tempReference -Destination $reference -Force
    Set-Content -LiteralPath $marker -Value 'female-reference-validated' -Encoding ASCII
    Write-Host ''
    Write-Host 'Nouvelle identité vocale installée et validée.' -ForegroundColor Green
    Write-Host 'Test : .\.venv\Scripts\skynet-voice.exe test'
} else {
    Move-Item -LiteralPath $tempReference -Destination $reference -Force
    Write-Host ''
    Write-Host 'Référence installée.' -ForegroundColor Green
    Write-Host 'Le moteur premium n est pas encore installé ou à jour.'
    Write-Host 'Lancez ensuite : powershell -ExecutionPolicy Bypass -File .\install-voice-premium.ps1' -ForegroundColor Yellow
}
