$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$trust = Join-Path $root '.venv\Scripts\skynet-trust.exe'
if (-not (Test-Path $trust)) { throw 'Run install.ps1 first.' }
& $trust rearm
