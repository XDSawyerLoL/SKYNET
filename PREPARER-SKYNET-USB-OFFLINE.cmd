@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo.
echo SKYNET USB - preparation HORS LIGNE
set /p DEST=Destination (exemple E:\SKYNET-USB, Entree = dist\SKYNET-USB): 
if "%DEST%"=="" set DEST=dist\SKYNET-USB
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare-usb-offline.ps1" -Destination "%DEST%"
if errorlevel 1 (
  echo.
  echo ERREUR pendant la preparation hors ligne de SKYNET USB.
  pause
  exit /b 1
)
echo.
echo Termine. Vous pouvez lancer SKYNET-USB.exe depuis la cle.
pause
