function Register-LauncherCoverage {
    param([string]$LauncherPath)

    $coverageFile = $env:GMAIL_ORGANIZER_PS_COVERAGE_FILE
    if ([string]::IsNullOrWhiteSpace($coverageFile)) {
        return
    }

    $coverageRunId = $env:GMAIL_ORGANIZER_PS_COVERAGE_RUN_ID
    if ([string]::IsNullOrWhiteSpace($coverageRunId)) {
        throw "GMAIL_ORGANIZER_PS_COVERAGE_RUN_ID is required."
    }

    $resolvedLauncher = (Resolve-Path -LiteralPath $LauncherPath).Path
    $tokens = $null
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $resolvedLauncher,
        [ref]$tokens,
        [ref]$parseErrors
    )
    if ($parseErrors.Count -gt 0) {
        throw "The launcher could not be instrumented because it has parser errors."
    }

    $statementLines = @(
        $ast.FindAll(
            {
                param($node)
                $node -is [System.Management.Automation.Language.StatementAst] -and
                    $node -isnot [System.Management.Automation.Language.FunctionDefinitionAst]
            },
            $true
        ).Extent.StartLineNumber | Sort-Object -Unique
    )

    foreach ($statementLine in $statementLines) {
        $capturedLine = $statementLine
        $capturedFile = $coverageFile
        $capturedRunId = $coverageRunId
        $action = {
            [System.IO.File]::AppendAllText($capturedFile, "$capturedRunId,$capturedLine`n")
        }.GetNewClosure()
        Set-PSBreakpoint `
            -Script $resolvedLauncher `
            -Line $statementLine `
            -Action $action `
            -ErrorAction SilentlyContinue | Out-Null
    }
}
