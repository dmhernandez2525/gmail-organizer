[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$LauncherPath,
    [Parameter(Mandatory)]
    [string]$ProjectRoot,
    [Parameter(Mandatory)]
    [string]$BrowserMarkerPath,
    [Parameter(Mandatory)]
    [string]$ReadyMarkerPath,
    [Parameter(Mandatory)]
    [int]$Port
)

$ErrorActionPreference = "Stop"
$probeProjectRoot = $ProjectRoot
$probePort = $Port

. (Join-Path $PSScriptRoot "register_powershell_coverage.ps1")
Register-LauncherCoverage -LauncherPath $LauncherPath
. $LauncherPath

function Open-GmailOrganizerBrowser {
    param([string]$Url)

    if (-not (Test-Path -LiteralPath $script:ReadyMarkerPath -PathType Leaf)) {
        throw "The browser was requested before the readiness marker existed."
    }
    [System.IO.File]::WriteAllText($script:BrowserMarkerPath, $Url)
}

$plan = New-LaunchPlan `
    -Root (Resolve-Path -LiteralPath $probeProjectRoot).Path `
    -ServerPort $probePort `
    -RestartLimit 0 `
    -StartupTimeout 4

if (-not $plan.Launchable) {
    throw "The browser readiness fixture did not produce a launchable plan."
}

Start-GmailOrganizer -Plan $plan -OpenBrowser $true
