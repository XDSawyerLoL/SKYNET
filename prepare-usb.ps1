param(
    [string]$Destination = '.\dist\SKYNET-USB'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$LlamaTag = 'b10621'
$CpuUrl = "https://github.com/ggml-org/llama.cpp/releases/download/$LlamaTag/llama-$LlamaTag-bin-win-cpu-x64.zip"
$VulkanUrl = "https://github.com/ggml-org/llama.cpp/releases/download/$LlamaTag/llama-$LlamaTag-bin-win-vulkan-x64.zip"
$ModelUrl = 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true'
$ModelSha256 = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'

function Download-File([string]$Url, [string]$OutFile) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --fail --retry 4 --retry-delay 3 --progress-bar -o $OutFile $Url
        if ($LASTEXITCODE -ne 0) { throw "Téléchargement impossible : $Url" }
    } else {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $OutFile
    }
}

$Destination = [System.IO.Path]::GetFullPath($Destination)
$temp = Join-Path $env:TEMP ('skynet-usb-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $temp | Out-Null

try {
    Write-Host 'SKYNET 0.14 - préparation de la clé USB autonome' -ForegroundColor Cyan

    $launcherSource = $null
    if (Test-Path '.\SKYNET-USB.exe') {
        $launcherSource = (Resolve-Path '.\SKYNET-USB.exe').Path
    } elseif (Test-Path '.\dist\SKYNET-USB.exe') {
        $launcherSource = (Resolve-Path '.\dist\SKYNET-USB.exe').Path
    } elseif (Test-Path '.\build-usb-launcher.ps1') {
        powershell -ExecutionPolicy Bypass -File .\build-usb-launcher.ps1
        $launcherSource = (Resolve-Path '.\dist\SKYNET-USB.exe').Path
    } else {
        throw 'SKYNET-USB.exe est introuvable. Retéléchargez le builder USB.'
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($name in @('engine\cpu', 'engine\vulkan', 'models', '.skynet', 'workspace', 'THIRD_PARTY_LICENSES')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $Destination $name) | Out-Null
    }
    $launcherDestination = Join-Path $Destination 'SKYNET-USB.exe'
    if ([System.IO.Path]::GetFullPath($launcherSource) -ne [System.IO.Path]::GetFullPath($launcherDestination)) {
        Copy-Item $launcherSource $launcherDestination -Force
    }

    $cpuZip = Join-Path $temp 'llama-cpu.zip'
    $vulkanZip = Join-Path $temp 'llama-vulkan.zip'
    Write-Host 'Téléchargement du moteur llama.cpp CPU (~18 Mo)...' -ForegroundColor Cyan
    Download-File $CpuUrl $cpuZip
    Expand-Archive -Path $cpuZip -DestinationPath (Join-Path $Destination 'engine\cpu') -Force

    Write-Host 'Téléchargement du moteur llama.cpp Vulkan (~34 Mo)...' -ForegroundColor Cyan
    Download-File $VulkanUrl $vulkanZip
    Expand-Archive -Path $vulkanZip -DestinationPath (Join-Path $Destination 'engine\vulkan') -Force

    $modelPath = Join-Path $Destination 'models\Qwen3-4B-Q4_K_M.gguf'
    $modelValid = $false
    if (Test-Path $modelPath) {
        Write-Host 'Vérification du modèle déjà présent...'
        $existingHash = (Get-FileHash $modelPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $modelValid = $existingHash -eq $ModelSha256
        if (-not $modelValid) { Remove-Item $modelPath -Force }
    }
    if (-not $modelValid) {
        Write-Host 'Téléchargement de Qwen3-4B Q4_K_M (~2,5 Go)...' -ForegroundColor Cyan
        Download-File $ModelUrl $modelPath
        Write-Host 'Vérification cryptographique du modèle...'
        $hash = (Get-FileHash $modelPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $ModelSha256) {
            throw "SHA-256 du modèle invalide. Attendu $ModelSha256, obtenu $hash"
        }
    }

    Download-File "https://raw.githubusercontent.com/ggml-org/llama.cpp/$LlamaTag/LICENSE" (Join-Path $Destination 'THIRD_PARTY_LICENSES\llama.cpp-MIT.txt')
    Download-File 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/raw/main/LICENSE' (Join-Path $Destination 'THIRD_PARTY_LICENSES\Qwen3-Apache-2.0.txt')

    $readme = @'
SKYNET USB 0.14 — AUTONOME WINDOWS x64

DÉMARRAGE
1. Conservez tout ce dossier sur une clé USB 3.x ou, idéalement, un SSD USB.
2. Double-cliquez sur SKYNET-USB.exe.
3. SKYNET tente d'abord l'accélération Vulkan (NVIDIA / AMD / Intel selon pilotes), puis repasse automatiquement en CPU si nécessaire.
4. Le premier chargement du modèle peut prendre plusieurs dizaines de secondes selon la vitesse de la clé et du PC.

AUCUNE INSTALLATION REQUISE
- Python n'est pas requis.
- Ollama n'est pas requis.
- Le modèle Qwen3-4B Q4_K_M est dans models\.
- llama.cpp est dans engine\.
- Mémoire, sessions et workspace restent dans ce dossier USB.

CONFIGURATION CONSEILLÉE
- Windows 10/11 x64.
- 16 Go de RAM recommandés. 8 Go peuvent fonctionner selon la machine mais ne sont pas garantis.
- USB 3.x minimum recommandé.

SÉCURITÉ
L'exécutable n'est pas signé par un certificat commercial. Windows SmartScreen peut donc demander une confirmation.
Le serveur d'inférence n'écoute que sur 127.0.0.1 et n'est pas exposé au réseau.

COMPOSANTS TIERS
Qwen3-4B-GGUF : Apache-2.0.
llama.cpp : MIT.
Voir THIRD_PARTY_LICENSES\.
'@
    Set-Content -Path (Join-Path $Destination 'LISEZ-MOI-USB.txt') -Value $readme -Encoding UTF8

    Write-Host ''
    Write-Host 'SKYNET USB autonome est prêt.' -ForegroundColor Green
    Write-Host "Dossier : $Destination"
    Write-Host 'Copiez le dossier entier sur la clé, pas uniquement le .exe.' -ForegroundColor Yellow
}
finally {
    if (Test-Path $temp) { Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue }
}
