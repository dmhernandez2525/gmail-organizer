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

$plan = New-LaunchPlan `
    -Root (Resolve-Path -LiteralPath $probeProjectRoot).Path `
    -ServerPort $probePort `
    -RestartLimit 0 `
    -StartupTimeout 2
if (-not $plan.Launchable) {
    throw "The cleanup-failure fixture did not produce a launchable plan."
}

$ownedProcess = Start-Process `
    -FilePath $plan.PythonExecutable `
    -ArgumentList $plan.PythonArguments `
    -WorkingDirectory $plan.ProjectRoot `
    -PassThru `
    -NoNewWindow

function Test-IsWindows {
    return $true
}

function Get-Command {
    param(
        [Parameter(Position = 0)]
        [string]$Name,
        [object]$CommandType
    )

    if ($Name -eq "taskkill.exe") {
        return [pscustomobject]@{ Source = $plan.PythonExecutable }
    }
    return Microsoft.PowerShell.Core\Get-Command @PSBoundParameters
}

$cleanupFailedVisibly = $false
try {
    Stop-OwnedProcessTree -Process $ownedProcess
}
catch {
    if ($_.Exception.Message -notmatch 'process-tree cleanup failed') {
        throw
    }
    $cleanupFailedVisibly = $true
}
finally {
    if (-not $ownedProcess.HasExited) {
        Microsoft.PowerShell.Management\Stop-Process -Id $ownedProcess.Id -Force
        $ownedProcess.WaitForExit(5000) | Out-Null
    }
}

if (-not $cleanupFailedVisibly) {
    throw "A failed taskkill operation was not surfaced."
}
if (-not $ownedProcess.HasExited) {
    throw "The parent process survived failed taskkill fallback cleanup."
}
Write-Output "TASKKILL_FAILURE_SURFACED"
