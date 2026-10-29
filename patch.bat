@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist "%~dp0antigravity-patcher.exe" (
    "%~dp0antigravity-patcher.exe" %*
) else (
    python patcher.py %*
)
if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] An error occurred while executing the script.
    pause
    exit /b %ERRORLEVEL%
)

if "%~1"=="" (
    echo.
    pause
)
