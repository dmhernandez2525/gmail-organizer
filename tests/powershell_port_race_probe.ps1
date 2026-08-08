[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$LauncherPath,
    [Parameter(Mandatory)]
    [string]$ProjectRoot,
    [Parameter(Mandatory)]
    [int]$Port
)

$ErrorActionPreference = "Stop"
$probeProjectRoot = $ProjectRoot
$probePort = $Port

. (Join-Path $PSScriptRoot "register_powershell_coverage.ps1")
Register-LauncherCoverage -LauncherPath $LauncherPath
. $LauncherPath

Stop-OwnedProcessTree -Process $null
$plan = New-LaunchPlan `
    -Root (Resolve-Path -LiteralPath $probeProjectRoot).Path `
    -ServerPort $probePort `
    -RestartLimit 0 `
    -StartupTimeout 2
if (-not $plan.Launchable) {
    throw "The port-race fixture did not produce a launchable plan."
}

$listener = [System.Net.Sockets.TcpListener]::new(
    [System.Net.IPAddress]::Loopback,
    $probePort
)
$listener.Start()
try {
    Start-GmailOrganizer -Plan $plan -OpenBrowser $false
}
finally {
    $listener.Stop()
}
