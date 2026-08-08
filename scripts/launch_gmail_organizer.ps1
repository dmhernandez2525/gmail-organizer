[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [switch]$ValidateOnly,
    [switch]$NoBrowser,
    [ValidateRange(0, 100)]
    [int]$MaxRestarts = 3,
    [ValidateRange(1, 65535)]
    [int]$Port = 8501,
    [ValidateRange(1, 300)]
    [int]$StartupTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

function Resolve-GmailOrganizerRoot {
    param([string]$Override)

    if ($Override) {
        return (Resolve-Path -LiteralPath $Override).Path
    }

    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-ProjectPython {
    param([string]$Root)

    $venvNames = @("venv", ".venv")
    foreach ($venvName in $venvNames) {
        $venvRoot = Join-Path $Root $venvName
        $candidates = @(
            (Join-Path $venvRoot "Scripts/python.exe"),
            (Join-Path $venvRoot "bin/python")
        )
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return [pscustomobject]@{
                    Executable = (Resolve-Path -LiteralPath $candidate).Path
                    VenvRoot = (Resolve-Path -LiteralPath $venvRoot).Path
                }
            }
        }
    }

    return $null
}

function New-FailedValidation {
    param(
        [string]$Code,
        [string]$Message
    )

    return [pscustomobject]@{
        SchemaVersion = 1
        Launchable = $false
        AppPresent = $false
        PythonExecutable = $null
        PythonVersion = $null
        PythonVersionValid = $false
        VenvRoot = $null
        VenvValid = $false
        DependenciesValid = $false
        UnavailableDependencies = @()
        AnthropicKeyConfigured = $false
        AnthropicKeySource = "unverified"
        ClientSecretValid = $false
        PortAvailable = $false
        Errors = @([pscustomobject]@{ Code = $Code; Message = $Message })
    }
}

function Test-RuntimeValidationContract {
    param([pscustomobject]$Validation)

    $requiredProperties = @(
        "SchemaVersion",
        "Launchable",
        "AppPresent",
        "PythonExecutable",
        "PythonVersion",
        "PythonVersionValid",
        "VenvRoot",
        "VenvValid",
        "DependenciesValid",
        "UnavailableDependencies",
        "AnthropicKeyConfigured",
        "AnthropicKeySource",
        "ClientSecretValid",
        "PortAvailable",
        "Errors"
    )
    foreach ($propertyName in $requiredProperties) {
        if ($Validation.PSObject.Properties.Name -notcontains $propertyName) {
            return $false
        }
    }

    if (($Validation.SchemaVersion -isnot [int] -and
        $Validation.SchemaVersion -isnot [long]) -or
        $Validation.SchemaVersion -ne 1) {
        return $false
    }
    $booleanProperties = @(
        "Launchable",
        "AppPresent",
        "PythonVersionValid",
        "VenvValid",
        "DependenciesValid",
        "AnthropicKeyConfigured",
        "ClientSecretValid",
        "PortAvailable"
    )
    foreach ($propertyName in $booleanProperties) {
        if ($Validation.$propertyName -isnot [bool]) {
            return $false
        }
    }

    if ($Validation.PythonExecutable -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Validation.PythonExecutable)) {
        return $false
    }
    if ($Validation.VenvRoot -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Validation.VenvRoot)) {
        return $false
    }
    if ($Validation.PythonVersion -isnot [string] -or
        $Validation.PythonVersion -notmatch '^\d+\.\d+\.\d+$') {
        return $false
    }
    if ($Validation.AnthropicKeySource -notin @("process_environment", "dotenv", "missing")) {
        return $false
    }

    if ($Validation.UnavailableDependencies -isnot [System.Array]) {
        return $false
    }
    $unavailableDependencies = @($Validation.UnavailableDependencies)
    foreach ($dependency in $unavailableDependencies) {
        if ($dependency -isnot [string] -or [string]::IsNullOrWhiteSpace($dependency)) {
            return $false
        }
    }
    if ([bool]$Validation.DependenciesValid -ne ($unavailableDependencies.Count -eq 0)) {
        return $false
    }

    if ($Validation.Errors -isnot [System.Array]) {
        return $false
    }
    $validationErrors = @($Validation.Errors)
    foreach ($validationError in $validationErrors) {
        if ($validationError.PSObject.Properties.Name -notcontains "Code" -or
            $validationError.PSObject.Properties.Name -notcontains "Message" -or
            $validationError.Code -isnot [string] -or
            [string]::IsNullOrWhiteSpace($validationError.Code) -or
            $validationError.Message -isnot [string] -or
            [string]::IsNullOrWhiteSpace($validationError.Message)) {
            return $false
        }
    }
    if (-not [bool]$Validation.Launchable -and $validationErrors.Count -eq 0) {
        return $false
    }

    $allPrerequisitesValid = (
        [bool]$Validation.AppPresent -and
        [bool]$Validation.PythonVersionValid -and
        [bool]$Validation.VenvValid -and
        [bool]$Validation.DependenciesValid -and
        [bool]$Validation.AnthropicKeyConfigured -and
        [bool]$Validation.ClientSecretValid -and
        [bool]$Validation.PortAvailable -and
        $validationErrors.Count -eq 0
    )
    return [bool]$Validation.Launchable -eq $allPrerequisitesValid
}

function Invoke-RuntimeValidator {
    param(
        [string]$PythonExecutable,
        [string]$ValidatorPath,
        [string]$Root,
        [string]$VenvRoot,
        [int]$ServerPort
    )

    try {
        $rawOutput = @(
            & $PythonExecutable `
                $ValidatorPath `
                "--project-root" $Root `
                "--expected-venv" $VenvRoot `
                "--port" $ServerPort.ToString() 2>&1
        )
        $validatorExitCode = $LASTEXITCODE
    }
    catch {
        return New-FailedValidation `
            -Code "python_execution_failed" `
            -Message "The project venv Python executable could not run the runtime validator."
    }

    $text = ($rawOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($text)) {
        return New-FailedValidation `
            -Code "python_execution_failed" `
            -Message "The project venv Python executable did not return a runtime validation result."
    }
    try {
        $validation = $text | ConvertFrom-Json
    }
    catch {
        return New-FailedValidation `
            -Code "validator_output_invalid" `
            -Message "The runtime validator did not return its expected sanitized JSON result."
    }

    if (-not (Test-RuntimeValidationContract -Validation $validation)) {
        return New-FailedValidation `
            -Code "validator_contract_invalid" `
            -Message "The runtime validator result had missing, invalid, or inconsistent fields."
    }
    if ($validatorExitCode -notin @(0, 1)) {
        return New-FailedValidation `
            -Code "validator_exit_invalid" `
            -Message "The runtime validator returned an unsupported exit code."
    }
    if ($validatorExitCode -eq 0 -and -not [bool]$validation.Launchable) {
        return New-FailedValidation `
            -Code "validator_exit_mismatch" `
            -Message "The runtime validator exit code disagreed with its launchability result."
    }
    if ($validatorExitCode -ne 0 -and [bool]$validation.Launchable) {
        return New-FailedValidation `
            -Code "validator_exit_mismatch" `
            -Message "The runtime validator exit code disagreed with its launchability result."
    }
    return $validation
}

function New-LaunchPlan {
    param(
        [string]$Root,
        [int]$ServerPort,
        [int]$RestartLimit,
        [int]$StartupTimeout
    )

    $appPath = Join-Path $Root "app.py"
    $validatorPath = Join-Path $Root "scripts/validate_gmail_organizer_runtime.py"
    $python = Resolve-ProjectPython -Root $Root

    if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
        $validation = New-FailedValidation `
            -Code "app_missing" `
            -Message "app.py was not found in the selected project root."
    }
    elseif (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        $validation = New-FailedValidation `
            -Code "validator_missing" `
            -Message "The repository runtime validator was not found."
    }
    elseif (-not $python) {
        $validation = New-FailedValidation `
            -Code "project_venv_missing" `
            -Message "A project venv Python executable was not found in venv or .venv."
    }
    else {
        $validation = Invoke-RuntimeValidator `
            -PythonExecutable $python.Executable `
            -ValidatorPath $validatorPath `
            -Root $Root `
            -VenvRoot $python.VenvRoot `
            -ServerPort $ServerPort
    }

    $pythonExecutable = $null
    $venvRoot = $null
    if ($python) {
        $pythonExecutable = $python.Executable
        $venvRoot = $python.VenvRoot
    }
    $arguments = @(
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless",
        "true",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        $ServerPort.ToString()
    )

    return [pscustomobject]@{
        ProjectRoot = $Root
        AppPath = $appPath
        PythonExecutable = $pythonExecutable
        VenvRoot = $venvRoot
        PythonArguments = $arguments
        Url = "http://localhost:$ServerPort"
        Port = $ServerPort
        MaxRestarts = $RestartLimit
        StartupTimeoutSeconds = $StartupTimeout
        Launchable = [bool]$validation.Launchable
        Validation = $validation
    }
}

function Test-TcpPortAvailable {
    param([int]$ServerPort)

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $ServerPort
    )
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Get-ListeningProcessIds {
    param([int]$ServerPort)

    $processIds = [System.Collections.Generic.HashSet[int]]::new()
    if (Test-IsWindows) {
        $netstat = Get-Command netstat.exe -CommandType Application -ErrorAction SilentlyContinue
        if (-not $netstat) {
            return @()
        }

        $netstatOutput = @(& $netstat.Source "-ano" "-p" "TCP" 2>$null)
        if ($LASTEXITCODE -ne 0) {
            return @()
        }
        foreach ($line in $netstatOutput) {
            if ($line -notmatch '^\s*TCP\s+(\S+)\s+\S+\s+LISTENING\s+(\d+)\s*$') {
                continue
            }
            $localEndpoint = $Matches[1]
            $listenerProcessId = [int]$Matches[2]
            if ($localEndpoint -notmatch ':(\d+)$' -or [int]$Matches[1] -ne $ServerPort) {
                continue
            }
            $processIds.Add($listenerProcessId) | Out-Null
        }
    }
    else {
        $lsof = Get-Command lsof -CommandType Application -ErrorAction SilentlyContinue
        if (-not $lsof) {
            return @()
        }

        $lsofOutput = @(
            & $lsof.Source "-nP" "-a" "-iTCP:$ServerPort" "-sTCP:LISTEN" "-t" 2>$null
        )
        foreach ($line in $lsofOutput) {
            $listenerProcessId = 0
            if ([int]::TryParse($line.ToString().Trim(), [ref]$listenerProcessId)) {
                $processIds.Add($listenerProcessId) | Out-Null
            }
        }
    }

    return @($processIds | ForEach-Object { [int]$_ })
}

function Test-TcpPortOwnedByProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$ServerPort
    )

    if (-not $Process -or $Process.HasExited) {
        return $false
    }
    $listenerProcessIds = @(Get-ListeningProcessIds -ServerPort $ServerPort)
    return $listenerProcessIds -contains $Process.Id
}

function Test-GmailOrganizerHealth {
    param([int]$ServerPort)

    $response = $null
    $reader = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create(
            "http://127.0.0.1:$ServerPort/_stcore/health"
        )
        $request.Method = "GET"
        $request.Timeout = 500
        $request.ReadWriteTimeout = 500
        $request.Proxy = $null
        $response = $request.GetResponse()
        if ([int]$response.StatusCode -ne 200) {
            return $false
        }
        $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
        return $reader.ReadToEnd().Trim() -eq "ok"
    }
    catch {
        return $false
    }
    finally {
        if ($reader) {
            $reader.Dispose()
        }
        if ($response) {
            $response.Dispose()
        }
    }
}

function Wait-GmailOrganizerReady {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$ServerPort,
        [int]$TimeoutSeconds
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            return [pscustomobject]@{ Ready = $false; ProcessExited = $true }
        }
        $portOwned = Test-TcpPortOwnedByProcess -Process $Process -ServerPort $ServerPort
        if ($portOwned -and
            (Test-GmailOrganizerHealth -ServerPort $ServerPort) -and
            (Test-TcpPortOwnedByProcess -Process $Process -ServerPort $ServerPort)) {
            return [pscustomobject]@{ Ready = $true; ProcessExited = $false }
        }
        Start-Sleep -Milliseconds 200
    }
    return [pscustomobject]@{ Ready = $false; ProcessExited = $false }
}

function Test-IsWindows {
    return [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
}

function Stop-OwnedProcessTree {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process -or $Process.HasExited) {
        return
    }

    $taskkillFailed = $false
    if (Test-IsWindows) {
        $taskkill = Get-Command taskkill.exe -CommandType Application -ErrorAction SilentlyContinue
        if ($taskkill) {
            & $taskkill.Source "/PID" $Process.Id.ToString() "/T" "/F" 2>$null | Out-Null
            $taskkillFailed = $LASTEXITCODE -ne 0
            if ($taskkillFailed -and -not $Process.HasExited) {
                try {
                    Stop-Process -Id $Process.Id -Force
                }
                catch {
                    # Termination is verified below and reported with one stable error.
                }
            }
        }
        else {
            $taskkillFailed = $true
            Stop-Process -Id $Process.Id -Force
        }
    }
    else {
        Stop-Process -Id $Process.Id -Force
    }

    $stopped = $false
    try {
        $stopped = $Process.WaitForExit(5000)
    }
    catch {
        # The owned process may already have exited between the checks above.
        $stopped = $Process.HasExited
    }

    if (-not $stopped -or -not $Process.HasExited) {
        throw "Owned process $($Process.Id) did not stop within five seconds."
    }
    if ($taskkillFailed) {
        throw "Windows process-tree cleanup failed for owned process $($Process.Id)."
    }
}

function Open-GmailOrganizerBrowser {
    param([string]$Url)

    Start-Process -FilePath $Url
}

function Start-GmailOrganizer {
    param(
        [pscustomobject]$Plan,
        [bool]$OpenBrowser
    )

    $attempt = 0
    $browserOpened = -not $OpenBrowser

    while ($true) {
        if (-not (Test-TcpPortAvailable -ServerPort $Plan.Port)) {
            throw "Local port $($Plan.Port) became unavailable before Streamlit startup."
        }

        $process = $null
        $exitCode = $null
        try {
            $process = Start-Process `
                -FilePath $Plan.PythonExecutable `
                -ArgumentList $Plan.PythonArguments `
                -WorkingDirectory $Plan.ProjectRoot `
                -PassThru `
                -NoNewWindow

            $readiness = Wait-GmailOrganizerReady `
                -Process $process `
                -ServerPort $Plan.Port `
                -TimeoutSeconds $Plan.StartupTimeoutSeconds

            if ($readiness.Ready) {
                if (-not $browserOpened) {
                    Open-GmailOrganizerBrowser -Url $Plan.Url
                    $browserOpened = $true
                }

                Write-Host "Gmail Organizer is ready at $($Plan.Url)."
                Write-Host "Press Ctrl+C to stop the server."
                $process.WaitForExit()
                $exitCode = $process.ExitCode
            }
            elseif ($readiness.ProcessExited) {
                $process.WaitForExit()
                $exitCode = $process.ExitCode
                if ($exitCode -eq 0) {
                    $exitCode = 125
                }
            }
            else {
                $exitCode = 124
                Write-Warning "Streamlit did not become ready within $($Plan.StartupTimeoutSeconds) seconds."
            }
        }
        finally {
            if ($process -and -not $process.HasExited) {
                Stop-OwnedProcessTree -Process $process
            }
        }

        if ($exitCode -eq 0) {
            return
        }

        if ($attempt -ge $Plan.MaxRestarts) {
            throw "Streamlit stopped with code $exitCode after $attempt restart attempts."
        }

        $attempt += 1
        Write-Warning "Streamlit stopped with code $exitCode. Restarting, attempt $attempt of $($Plan.MaxRestarts)."
        Start-Sleep -Seconds 2
    }
}

function Write-ValidationErrors {
    param([pscustomobject]$Plan)

    foreach ($validationError in @($Plan.Validation.Errors)) {
        [Console]::Error.WriteLine(
            "VALIDATION ERROR [$($validationError.Code)]: $($validationError.Message)"
        )
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    try {
        $resolvedRoot = Resolve-GmailOrganizerRoot -Override $ProjectRoot
        $launchPlan = New-LaunchPlan `
            -Root $resolvedRoot `
            -ServerPort $Port `
            -RestartLimit $MaxRestarts `
            -StartupTimeout $StartupTimeoutSeconds

        if ($ValidateOnly) {
            $launchPlan | ConvertTo-Json -Depth 6
            if (-not $launchPlan.Launchable) {
                Write-ValidationErrors -Plan $launchPlan
                exit 1
            }
            exit 0
        }

        if (-not $launchPlan.Launchable) {
            Write-ValidationErrors -Plan $launchPlan
            throw "Launch validation failed. Correct every reported prerequisite before retrying."
        }

        Start-GmailOrganizer -Plan $launchPlan -OpenBrowser (-not $NoBrowser)
    }
    catch {
        Write-Error $_.Exception.Message
        exit 1
    }
}
