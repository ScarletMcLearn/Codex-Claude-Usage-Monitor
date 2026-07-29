@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "POWERSHELL_EXE=pwsh"

where "%POWERSHELL_EXE%" >nul 2>nul
if errorlevel 1 set "POWERSHELL_EXE=powershell"

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-dashboard.ps1" %*
exit /b %ERRORLEVEL%
