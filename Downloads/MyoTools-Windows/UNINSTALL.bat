@echo off
call "%~dp0Hub\platforms\windows\uninstall.bat" %*
exit /b %ERRORLEVEL%
