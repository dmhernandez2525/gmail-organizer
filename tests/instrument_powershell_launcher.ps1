[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$LauncherPath
)

$ErrorActionPreference = "Stop"
$parametersJson = $env:GMAIL_ORGANIZER_PS_PARAMETERS_JSON
if ([string]::IsNullOrWhiteSpace($parametersJson)) {
    throw "GMAIL_ORGANIZER_PS_PARAMETERS_JSON is required."
}

$resolvedLauncher = (Resolve-Path -LiteralPath $LauncherPath).Path
. (Join-Path $PSScriptRoot "register_powershell_coverage.ps1")
Register-LauncherCoverage -LauncherPath $resolvedLauncher

$parameterDocument = ConvertFrom-Json -InputObject $parametersJson
$launcherParameters = @{}
foreach ($property in $parameterDocument.PSObject.Properties) {
    $launcherParameters[$property.Name] = $property.Value
}
& $resolvedLauncher @launcherParameters
$launcherExitCode = $LASTEXITCODE
exit $launcherExitCode
