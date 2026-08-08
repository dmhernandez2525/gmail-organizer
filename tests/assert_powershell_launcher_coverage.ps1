[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$LauncherPath,
    [Parameter(Mandatory)]
    [string]$CoverageFile,
    [ValidateRange(1, 100)]
    [double]$Minimum = 80
)

$ErrorActionPreference = "Stop"

function Measure-Percentage {
    param(
        [int]$Covered,
        [int]$Total
    )

    if ($Total -eq 0) {
        return 0.0
    }
    return [Math]::Round(100.0 * $Covered / $Total, 2)
}

function Test-ConditionalOutcome {
    param(
        [hashtable]$Traces,
        [int]$ConditionLine,
        [int]$BodyLine,
        [bool]$ExpectedBodyHit
    )

    foreach ($trace in $Traces.Values) {
        for ($index = 0; $index -lt $trace.Count; $index += 1) {
            if ($trace[$index] -ne $ConditionLine) {
                continue
            }

            $nextCondition = $trace.Count
            for ($cursor = $index + 1; $cursor -lt $trace.Count; $cursor += 1) {
                if ($trace[$cursor] -eq $ConditionLine) {
                    $nextCondition = $cursor
                    break
                }
            }

            $bodyHit = $false
            for ($cursor = $index + 1; $cursor -lt $nextCondition; $cursor += 1) {
                if ($trace[$cursor] -eq $BodyLine) {
                    $bodyHit = $true
                    break
                }
            }
            if ($bodyHit -eq $ExpectedBodyHit) {
                return $true
            }
        }
    }
    return $false
}

$resolvedLauncher = (Resolve-Path -LiteralPath $LauncherPath).Path
$resolvedCoverage = (Resolve-Path -LiteralPath $CoverageFile).Path
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $resolvedLauncher,
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {
    throw "PowerShell coverage cannot be measured because the launcher has parser errors."
}

$traces = @{}
$hitLines = @{}
foreach ($record in [System.IO.File]::ReadLines($resolvedCoverage)) {
    $parts = $record.Split(",", 2)
    if ($parts.Count -ne 2) {
        throw "The PowerShell coverage trace contains a malformed record."
    }
    $runId = $parts[0]
    $line = 0
    if (-not [int]::TryParse($parts[1], [ref]$line)) {
        throw "The PowerShell coverage trace contains a nonnumeric line."
    }
    if (-not $traces.ContainsKey($runId)) {
        $traces[$runId] = [System.Collections.Generic.List[int]]::new()
    }
    $traces[$runId].Add($line)
    $hitLines[$line] = $true
}
if ($traces.Count -eq 0) {
    throw "The PowerShell coverage trace is empty."
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
$coveredStatementLines = @($statementLines | Where-Object { $hitLines.ContainsKey($_) })

$functions = @(
    $ast.FindAll(
        { param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] },
        $true
    )
)
$functionEntries = @(
    foreach ($function in $functions) {
        $bodyStatements = @($function.Body.EndBlock.Statements)
        if ($bodyStatements.Count -gt 0) {
            $bodyStatements[0].Extent.StartLineNumber
        }
    }
)
$coveredFunctionEntries = @($functionEntries | Where-Object { $hitLines.ContainsKey($_) })

$conditionalTargets = [System.Collections.Generic.List[object]]::new()
$ifStatements = @(
    $ast.FindAll(
        { param($node) $node -is [System.Management.Automation.Language.IfStatementAst] },
        $true
    )
)
foreach ($ifStatement in $ifStatements) {
    foreach ($clause in $ifStatement.Clauses) {
        $bodyStatements = @($clause.Item2.Statements)
        if ($bodyStatements.Count -eq 0) {
            continue
        }
        $conditionLine = $clause.Item1.Extent.StartLineNumber
        $bodyLine = $bodyStatements[0].Extent.StartLineNumber
        $conditionalTargets.Add(
            [pscustomobject]@{ ConditionLine = $conditionLine; BodyLine = $bodyLine; BodyHit = $true }
        )
        $conditionalTargets.Add(
            [pscustomobject]@{ ConditionLine = $conditionLine; BodyLine = $bodyLine; BodyHit = $false }
        )
    }
}
$evaluatedConditionalTargets = @(
    $conditionalTargets | ForEach-Object {
        $covered = Test-ConditionalOutcome `
            -Traces $traces `
            -ConditionLine $_.ConditionLine `
            -BodyLine $_.BodyLine `
            -ExpectedBodyHit $_.BodyHit
        [pscustomobject]@{
            ConditionLine = $_.ConditionLine
            BodyLine = $_.BodyLine
            Outcome = if ($_.BodyHit) { "true" } else { "false" }
            Covered = $covered
        }
    }
)
$coveredConditionalTargets = @($evaluatedConditionalTargets | Where-Object { $_.Covered })

$metrics = @(
    [pscustomobject]@{
        Metric = "Line"
        Covered = $coveredStatementLines.Count
        Total = $statementLines.Count
        Percent = Measure-Percentage $coveredStatementLines.Count $statementLines.Count
    },
    [pscustomobject]@{
        Metric = "Function"
        Covered = $coveredFunctionEntries.Count
        Total = $functionEntries.Count
        Percent = Measure-Percentage $coveredFunctionEntries.Count $functionEntries.Count
    },
    [pscustomobject]@{
        Metric = "Branch"
        Covered = $coveredConditionalTargets.Count
        Total = $conditionalTargets.Count
        Percent = Measure-Percentage $coveredConditionalTargets.Count $conditionalTargets.Count
    }
)

$metrics | ConvertTo-Json -Depth 3
$failures = @($metrics | Where-Object { $_.Percent -lt $Minimum })
if ($failures.Count -gt 0) {
    $missingBranches = @(
        $evaluatedConditionalTargets |
            Where-Object { -not $_.Covered } |
            ForEach-Object { "$($_.ConditionLine):$($_.Outcome)->$($_.BodyLine)" }
    )
    [Console]::Error.WriteLine("Uncovered conditional outcomes: $($missingBranches -join ', ')")
    $names = ($failures | ForEach-Object { "$($_.Metric)=$($_.Percent)%" }) -join ", "
    throw "PowerShell launcher coverage is below $Minimum percent: $names."
}
