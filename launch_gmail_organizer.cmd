@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0.") do set "GO_ROOT=%%~fI"
set "GO_SCRIPT=%GO_ROOT%\scripts\launch_gmail_organizer.ps1"

if not exist "%GO_SCRIPT%" (
    echo ERROR: The PowerShell launcher was not found at "%GO_SCRIPT%". 1>&2
    set "GO_EXIT=1"
    goto :failure
)

where pwsh.exe >nul 2>&1
if errorlevel 1 (
    where powershell.exe >nul 2>&1
    if errorlevel 1 (
        echo ERROR: PowerShell was not found. Install PowerShell or enable Windows PowerShell. 1>&2
        set "GO_EXIT=1"
        goto :failure
    )
    set "GO_POWERSHELL=powershell.exe"
) else (
    set "GO_POWERSHELL=pwsh.exe"
)

"%GO_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%GO_SCRIPT%" -ProjectRoot "%GO_ROOT%" %*
set "GO_EXIT=%ERRORLEVEL%"

if "%GO_EXIT%"=="0" exit /b 0

:failure
echo.
echo Gmail Organizer did not start. Review the error above. 1>&2
if /I not "%GMAIL_ORGANIZER_NO_PAUSE%"=="1" (
    echo Press any key to close this window. 1>&2
    pause >nul
)
exit /b %GO_EXIT%
