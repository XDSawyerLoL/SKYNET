@echo off
setlocal
cd /d "%~dp0"
echo.
echo SKYNET USB - preparation autonome
set /p DEST=Destination (exemple E:\SKYNET-USB, Entree = dist\SKYNET-USB): 
if "%DEST%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\prepare-usb.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\prepare-usb.ps1" -Destination "%DEST%"
)
if errorlevel 1 (
  echo.
  echo ERREUR pendant la preparation de SKYNET USB.
  pause
  exit /b 1
)
echo.
echo Terminee.
pause
