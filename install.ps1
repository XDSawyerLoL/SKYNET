$ErrorActionPreference = 'Stop'

Write-Host 'SKYNET bootstrap' -ForegroundColor Cyan

function Test-PythonRuntime {
    param(
        [string]$Command,
        [string[]]$PrefixArgs = @()
    )
    try {
        & $Command @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PythonRuntime {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($selector in @('-3.13', '-3.12', '-3.11', '-3')) {
            if (Test-PythonRuntime -Command 'py' -PrefixArgs @($selector)) {
                return @{ Command = 'py'; Args = @($selector) }
            }
        }
    }

    foreach ($candidate in @('python', 'python3')) {
        if ((Get-Command $candidate -ErrorAction SilentlyContinue) -and (Test-PythonRuntime -Command $candidate)) {
            return @{ Command = $candidate; Args = @() }
        }
    }

    return $null
}

$python = Resolve-PythonRuntime

if (-not $python) {
    Write-Warning 'Python 3.11+ was not found. SKYNET will try to install Python 3.11 with winget.'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw @'
Python 3.11+ is required and winget is unavailable.
Install Python 3.11 or newer from python.org, make sure the Python Launcher/PATH option is enabled, then run install.ps1 again.
'@
    }

    & winget install --exact --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw 'Python installation through winget failed. Install Python 3.11+ manually, then run install.ps1 again.'
    }

    # Refresh the process PATH after an installer modifies the user/machine PATH.
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"

    $python = Resolve-PythonRuntime
    if (-not $python) {
        throw 'Python was installed but is not visible to this PowerShell process yet. Close PowerShell, reopen it in the SKYNET folder, and run install.ps1 again.'
    }
}

$pythonVersion = & $python.Command @($python.Args) -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Host "Python $pythonVersion detected." -ForegroundColor Green

if (Test-Path '.venv\Scripts\python.exe') {
    try {
        & .\.venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
        if ($LASTEXITCODE -ne 0) { throw 'bad venv' }
    } catch {
        Write-Warning 'Existing .venv is invalid or incompatible. Recreating it.'
        Remove-Item -Recurse -Force '.venv'
    }
} elseif (Test-Path '.venv') {
    Write-Warning 'Incomplete .venv detected. Recreating it.'
    Remove-Item -Recurse -Force '.venv'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating local Python environment...' -ForegroundColor Cyan
    & $python.Command @($python.Args) -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path '.venv\Scripts\python.exe')) {
        throw 'Could not create the SKYNET virtual environment.'
    }
}

Write-Host 'Installing SKYNET locally...' -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
}

if (-not (Test-Path 'workspace')) {
    New-Item -ItemType Directory -Path 'workspace' | Out-Null
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host 'Ollama detected.' -ForegroundColor Green
    Write-Host 'Installed models:'
    ollama list
} else {
    Write-Warning 'Ollama was not found in PATH. Install/start Ollama before using local inference.'
}

Write-Host ''
Write-Host 'SKYNET installation complete.' -ForegroundColor Green
Write-Host 'Launch premium UI:' -ForegroundColor Cyan
Write-Host '  powershell -ExecutionPolicy Bypass -File .\launch.ps1'
Write-Host 'or:'
Write-Host '  .\.venv\Scripts\skynet-desktop.exe'
