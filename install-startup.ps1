$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    throw "SKYNET virtual environment not found. Run install.ps1 first."
}

$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'SKYNET Supervisor.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '-m skynet.supervisor_cli'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'SKYNET local autonomy supervisor'
$shortcut.Save()

Write-Host "SKYNET supervisor startup shortcut created: $shortcutPath"
Write-Host "This is opt-in and can be removed with remove-startup.ps1."
