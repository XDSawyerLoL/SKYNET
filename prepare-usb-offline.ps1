param(
    [string]$Destination = '.\dist\SKYNET-USB'
)

$ErrorActionPreference = 'Stop'
$ModelName = 'Qwen3-4B-Q4_K_M.gguf'
$ModelSha256 = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path
$Payload = Join-Path $Base 'payload'

function Require-File([string]$Path, [string]$Label) {
    if (-not (Test-Path $Path)) { throw "$Label introuvable : $Path" }
}

$Destination = [System.IO.Path]::GetFullPath($Destination)
$Launcher = Join-Path $Base 'SKYNET-USB.exe'
$CpuZip = Join-Path $Payload 'llama-cpu.zip'
$VulkanZip = Join-Path $Payload 'llama-vulkan.zip'
$Parts = @(Get-ChildItem -Path $Payload -Filter "$ModelName.part.*" -File -ErrorAction SilentlyContinue | Sort-Object Name)

Require-File $Launcher 'Lanceur SKYNET'
Require-File $CpuZip 'Moteur CPU'
Require-File $VulkanZip 'Moteur Vulkan'
if ($Parts.Count -lt 2) { throw "Morceaux du modèle absents dans $Payload" }

Write-Host 'SKYNET USB 0.14.1 - préparation HORS LIGNE' -ForegroundColor Cyan
Write-Host "Aucun téléchargement Internet ne sera effectué." -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($name in @('engine\cpu', 'engine\vulkan', 'models', '.skynet', 'workspace', 'THIRD_PARTY_LICENSES')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Destination $name) | Out-Null
}
Copy-Item $Launcher (Join-Path $Destination 'SKYNET-USB.exe') -Force

Write-Host 'Installation du moteur CPU local...'
Expand-Archive -Path $CpuZip -DestinationPath (Join-Path $Destination 'engine\cpu') -Force
Write-Host 'Installation du moteur Vulkan local...'
Expand-Archive -Path $VulkanZip -DestinationPath (Join-Path $Destination 'engine\vulkan') -Force

$ModelPath = Join-Path $Destination ('models\' + $ModelName)
$TempModel = $ModelPath + '.building'
if (Test-Path $TempModel) { Remove-Item $TempModel -Force }

Write-Host ("Reconstruction du modèle local depuis {0} morceaux..." -f $Parts.Count) -ForegroundColor Cyan
$out = [System.IO.File]::Open($TempModel, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
    foreach ($part in $Parts) {
        Write-Host ('  + ' + $part.Name)
        $input = [System.IO.File]::OpenRead($part.FullName)
        try { $input.CopyTo($out) } finally { $input.Dispose() }
    }
} finally { $out.Dispose() }

Write-Host 'Vérification SHA-256 du modèle...'
$hash = (Get-FileHash $TempModel -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $ModelSha256) {
    Remove-Item $TempModel -Force -ErrorAction SilentlyContinue
    throw "Modèle invalide ou morceau manquant. SHA attendu $ModelSha256 ; obtenu $hash"
}
Move-Item $TempModel $ModelPath -Force

$licenses = Join-Path $Payload 'licenses'
if (Test-Path $licenses) { Copy-Item (Join-Path $licenses '*') (Join-Path $Destination 'THIRD_PARTY_LICENSES') -Force }

$readme = @'
SKYNET USB 0.14.1 — HORS LIGNE WINDOWS x64

DÉMARRAGE
1. Double-cliquez sur SKYNET-USB.exe depuis le dossier complet sur la clé.
2. SKYNET tente Vulkan/GPU, puis CPU en secours.
3. Python, Ollama et Internet ne sont pas requis.

Le modèle Qwen3-4B Q4_K_M et les moteurs llama.cpp sont embarqués localement.
La mémoire et le workspace restent sur la clé.
'@
Set-Content -Path (Join-Path $Destination 'LISEZ-MOI-USB.txt') -Value $readme -Encoding UTF8

Write-Host ''
Write-Host 'SKYNET USB HORS LIGNE est prêt.' -ForegroundColor Green
Write-Host "Dossier : $Destination"
