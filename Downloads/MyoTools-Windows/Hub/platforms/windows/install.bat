@echo off
setlocal
cd /d "%~dp0..\..\.."
echo === MyoTools automatic installation (Windows 64-bit) ===
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Hub\platforms\windows\bootstrap_miniforge.ps1"
if errorlevel 1 (
 echo Installation failed. Review errors above.
 pause
 exit /b 1
)
echo Installation complete. MyoTools shortcut is on your desktop.
pause
