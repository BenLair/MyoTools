@echo off
setlocal
cd /d "%~dp0..\.."
set "PYTHON_CMD="
if exist "runtime\python_path.txt" set /p PYTHON_CMD=<"runtime\python_path.txt"
if defined PYTHON_CMD if not exist "%PYTHON_CMD%" set "PYTHON_CMD="
if not defined PYTHON_CMD if exist "%USERPROFILE%\miniforge3\python.exe" set "PYTHON_CMD=%USERPROFILE%\miniforge3\python.exe"
if not defined PYTHON_CMD if exist "%USERPROFILE%\miniconda3\python.exe" set "PYTHON_CMD=%USERPROFILE%\miniconda3\python.exe"
if not defined PYTHON_CMD if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON_CMD=%USERPROFILE%\anaconda3\python.exe"
if not defined PYTHON_CMD (
 echo Conda base Python not found. Nothing was removed.
 pause
 exit /b 1
)
"%PYTHON_CMD%" uninstall.py %*
set "UNINSTALL_EXIT=%ERRORLEVEL%"
pause
exit /b %UNINSTALL_EXIT%
