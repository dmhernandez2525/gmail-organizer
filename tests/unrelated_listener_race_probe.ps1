[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$LauncherPath,
    [Parameter(Mandatory)]
    [string]$ProjectRoot,
    [Parameter(Mandatory)]
    [string]$BrowserMarkerPath,
    [Parameter(Mandatory)]
    [string]$ListenerReadyPath,
    [Parameter(Mandatory)]
    [int]$Port
)

$ErrorActionPreference = "Stop"
$probeProjectRoot = $ProjectRoot
$probePort = $Port

. (Join-Path $PSScriptRoot "register_powershell_coverage.ps1")
Register-LauncherCoverage -LauncherPath $LauncherPath
. $LauncherPath

$plan = New-LaunchPlan `
    -Root (Resolve-Path -LiteralPath $probeProjectRoot).Path `
    -ServerPort $probePort `
    -RestartLimit 0 `
    -StartupTimeout 1
if (-not $plan.Launchable) {
    throw "The unrelated-listener fixture did not produce a launchable plan."
}

$script:unrelatedListener = $null

function Test-TcpPortAvailable {
    param([int]$ServerPort)

    $env:UNRELATED_LISTENER_PORT = $ServerPort.ToString()
    $env:UNRELATED_LISTENER_READY_FILE = $script:ListenerReadyPath
    $script:unrelatedListener = Start-Process `
        -FilePath $plan.PythonExecutable `
        -ArgumentList @("unrelated_listener.py") `
        -WorkingDirectory $plan.ProjectRoot `
        -PassThru `
        -NoNewWindow

    $deadline = [DateTime]::UtcNow.AddSeconds(3)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($script:unrelatedListener.HasExited) {
            throw "The unrelated listener exited before acquiring the port."
        }
        if (Test-Path -LiteralPath $script:ListenerReadyPath -PathType Leaf) {
            return $true
        }
        Start-Sleep -Milliseconds 50
    }
    throw "The unrelated listener did not acquire the port."
}

function Open-GmailOrganizerBrowser {
    param([string]$Url)
    [System.IO.File]::WriteAllText($script:BrowserMarkerPath, $Url)
}

$expectedFailure = $false
try {
    Start-GmailOrganizer -Plan $plan -OpenBrowser $true
}
catch {
    if ($_.Exception.Message -notmatch 'code 124') {
        throw
    }
    $expectedFailure = $true
}
finally {
    if ($script:unrelatedListener -and -not $script:unrelatedListener.HasExited) {
        Stop-Process -Id $script:unrelatedListener.Id -Force
        $script:unrelatedListener.WaitForExit(5000) | Out-Null
    }
}

if (-not $expectedFailure) {
    throw "The unrelated listener was accepted as Gmail Organizer readiness."
}
if (Test-Path -LiteralPath $BrowserMarkerPath) {
    throw "The browser action ran for an unrelated listener."
}
Write-Output "UNRELATED_LISTENER_REJECTED"
