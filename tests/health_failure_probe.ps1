[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$LauncherPath,
    [Parameter(Mandatory)]
    [int]$Port
)

$ErrorActionPreference = "Stop"
$probePort = $Port

. (Join-Path $PSScriptRoot "register_powershell_coverage.ps1")
Register-LauncherCoverage -LauncherPath $LauncherPath
. $LauncherPath

if (Test-GmailOrganizerHealth -ServerPort $probePort) {
    throw "A missing health endpoint was accepted."
}
Write-Output "UNHEALTHY_ENDPOINT_REJECTED"
