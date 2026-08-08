[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [switch]$ValidateOnly,
    [switch]$NoBrowser,
    [ValidateRange(0, 100)]
    [int]$MaxRestarts = 3,
    [ValidateRange(1, 65535)]
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

function Resolve-GmailOrganizerRoot {
    param([string]$Override)

    if ($Override) {
        return (Resolve-Path -LiteralPath $Override).Path
    }

    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-StreamlitCommand {
    param([string]$Root)

    $candidates = @(
        (Join-Path $Root "venv/Scripts/streamlit.exe"),
        (Join-Path $Root "venv/Scripts/streamlit.cmd"),
        (Join-Path $Root "venv/bin/streamlit")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    $systemCommand = Get-Command streamlit -ErrorAction SilentlyContinue
    if ($systemCommand) {
        return $systemCommand.Source
    }

    throw "Streamlit was not found in venv or on PATH. Create the project virtual environment before launching."
}

function Test-AnthropicKeyConfigured {
    param([string]$EnvPath)

    foreach ($line in [System.IO.File]::ReadLines($EnvPath)) {
        $match = [regex]::Match($line, '^\s*ANTHROPIC_API_KEY\s*=\s*(?<value>.*)$')
        if (-not $match.Success) {
            continue
        }

        $value = $match.Groups['value'].Value.Trim()
        if ([string]::IsNullOrWhiteSpace($value) -or $value.StartsWith('#')) {
            continue
        }

        if ($value.StartsWith('"')) {
            $quoted = [regex]::Match($value, '^"(?<inner>[^\"]*)"\s*(?:#.*)?$')
            if ($quoted.Success -and -not [string]::IsNullOrWhiteSpace($quoted.Groups['inner'].Value)) {
                return $true
            }
            continue
        }

        if ($value.StartsWith("'")) {
            $quoted = [regex]::Match($value, "^'(?<inner>[^']*)'\s*(?:#.*)?$")
            if ($quoted.Success -and -not [string]::IsNullOrWhiteSpace($quoted.Groups['inner'].Value)) {
                return $true
            }
            continue
        }

        $unquoted = [regex]::Replace($value, '\s+#.*$', '').Trim()
        if (-not [string]::IsNullOrWhiteSpace($unquoted)) {
            return $true
        }
    }

    return $false
}

function New-LaunchPlan {
    param(
        [string]$Root,
        [int]$ServerPort,
        [int]$RestartLimit
    )

    $appPath = Join-Path $Root "app.py"
    $envPath = Join-Path $Root ".env"
    $clientSecretPath = Join-Path $Root "client_secret.json"

    if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
        throw "app.py was not found in the selected project root."
    }
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw ".env was not found. Copy .env.example to .env before launching."
    }

    $streamlitCommand = Resolve-StreamlitCommand -Root $Root
    $arguments = @(
        "run",
        "app.py",
        "--server.headless",
        "true",
        "--server.port",
        $ServerPort.ToString()
    )

    return [pscustomobject]@{
        ProjectRoot = $Root
        AppPath = $appPath
        EnvPath = $envPath
        ClientSecretPresent = Test-Path -LiteralPath $clientSecretPath -PathType Leaf
        AnthropicKeyConfigured = Test-AnthropicKeyConfigured -EnvPath $envPath
        StreamlitCommand = $streamlitCommand
        StreamlitArguments = $arguments
        Url = "http://localhost:$ServerPort"
        MaxRestarts = $RestartLimit
        Launchable = $true
    }
}

function Start-GmailOrganizer {
    param(
        [pscustomobject]$Plan,
        [bool]$OpenBrowser
    )

    $attempt = 0
    $browserOpened = -not $OpenBrowser

    while ($true) {
        $process = $null
        try {
            $process = Start-Process `
                -FilePath $Plan.StreamlitCommand `
                -ArgumentList $Plan.StreamlitArguments `
                -WorkingDirectory $Plan.ProjectRoot `
                -PassThru `
                -NoNewWindow

            Start-Sleep -Seconds 2
            if ($process.HasExited) {
                throw "Streamlit exited during startup with code $($process.ExitCode)."
            }

            if (-not $browserOpened) {
                Start-Process $Plan.Url
                $browserOpened = $true
            }

            Write-Host "Gmail Organizer is running at $($Plan.Url)."
            Write-Host "Press Ctrl+C to stop the server."
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        }
        finally {
            if ($process -and -not $process.HasExited) {
                Stop-Process -Id $process.Id
                $process.WaitForExit()
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

try {
    $resolvedRoot = Resolve-GmailOrganizerRoot -Override $ProjectRoot
    $launchPlan = New-LaunchPlan -Root $resolvedRoot -ServerPort $Port -RestartLimit $MaxRestarts

    if (-not $launchPlan.ClientSecretPresent) {
        $message = "client_secret.json was not found. Google OAuth setup is required before adding an account."
        if ($ValidateOnly) {
            [Console]::Error.WriteLine("WARNING: $message")
        }
        else {
            Write-Warning $message
        }
    }
    if (-not $launchPlan.AnthropicKeyConfigured) {
        $message = "ANTHROPIC_API_KEY is not configured. Select Claude Code in the app or add the key to .env."
        if ($ValidateOnly) {
            [Console]::Error.WriteLine("WARNING: $message")
        }
        else {
            Write-Warning $message
        }
    }

    if ($ValidateOnly) {
        $launchPlan | ConvertTo-Json -Depth 3
        exit 0
    }

    Start-GmailOrganizer -Plan $launchPlan -OpenBrowser (-not $NoBrowser)
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
