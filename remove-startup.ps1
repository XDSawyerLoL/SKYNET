$ErrorActionPreference = 'Stop'
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'SKYNET Supervisor.lnk'
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Removed: $shortcutPath"
} else {
    Write-Host "SKYNET startup shortcut is not installed."
}
