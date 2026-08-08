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

function Get-PositionKey {
    param(
        [int]$Line,
        [int]$Column
    )
    return "$Line`:$Column"
}

function Get-ExtentKey {
    param([System.Management.Automation.Language.IScriptExtent]$Extent)
    return "$($Extent.StartLineNumber):$($Extent.StartColumnNumber):" +
        "$($Extent.EndLineNumber):$($Extent.EndColumnNumber)"
}

function Test-PointInExtent {
    param(
        [pscustomobject]$Point,
        [System.Management.Automation.Language.IScriptExtent]$Extent
    )

    if ($Point.Line -lt $Extent.StartLineNumber -or $Point.Line -gt $Extent.EndLineNumber) {
        return $false
    }
    if ($Point.Line -eq $Extent.StartLineNumber -and
        $Point.Column -lt $Extent.StartColumnNumber) {
        return $false
    }
    if ($Point.Line -eq $Extent.EndLineNumber -and
        $Point.Column -ge $Extent.EndColumnNumber) {
        return $false
    }
    return $true
}

function Get-FirstTracePointInExtent {
    param(
        [object[]]$TracePoints,
        [System.Management.Automation.Language.IScriptExtent]$Extent
    )

    return @(
        $TracePoints |
            Where-Object { Test-PointInExtent -Point $_ -Extent $Extent } |
            Sort-Object -Property Line, Column
    )[0]
}

function Get-CoverageSignalPoint {
    param(
        [object[]]$TracePoints,
        [object[]]$ObservedPoints,
        [System.Management.Automation.Language.IScriptExtent]$Extent
    )

    $observed = Get-FirstTracePointInExtent -TracePoints $ObservedPoints -Extent $Extent
    if ($observed) {
        return $observed
    }
    return Get-FirstTracePointInExtent -TracePoints $TracePoints -Extent $Extent
}

function Test-DecisionOutcome {
    param(
        [hashtable]$Traces,
        [string]$ConditionKey,
        [System.Management.Automation.Language.IScriptExtent]$BodyExtent,
        [bool]$ExpectedBodyHit
    )

    foreach ($trace in $Traces.Values) {
        for ($index = 0; $index -lt $trace.Count; $index += 1) {
            if ($trace[$index].Key -ne $ConditionKey) {
                continue
            }

            $nextCondition = $trace.Count
            for ($cursor = $index + 1; $cursor -lt $trace.Count; $cursor += 1) {
                if ($trace[$cursor].Key -eq $ConditionKey) {
                    $nextCondition = $cursor
                    break
                }
            }

            $bodyHit = $false
            for ($cursor = $index + 1; $cursor -lt $nextCondition; $cursor += 1) {
                if (Test-PointInExtent -Point $trace[$cursor] -Extent $BodyExtent) {
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
$hitPoints = @{}
foreach ($record in [System.IO.File]::ReadLines($resolvedCoverage)) {
    $parts = $record.Split(",", 3)
    if ($parts.Count -ne 3) {
        throw "The PowerShell coverage trace contains a malformed record."
    }
    $runId = $parts[0]
    $line = 0
    $column = 0
    if (-not [int]::TryParse($parts[1], [ref]$line) -or
        -not [int]::TryParse($parts[2], [ref]$column)) {
        throw "The PowerShell coverage trace contains a nonnumeric source position."
    }
    $point = [pscustomobject]@{
        Line = $line
        Column = $column
        Key = Get-PositionKey -Line $line -Column $column
    }
    if (-not $traces.ContainsKey($runId)) {
        $traces[$runId] = [System.Collections.Generic.List[object]]::new()
    }
    $traces[$runId].Add($point)
    $hitPoints[$point.Key] = $point
}
if ($traces.Count -eq 0) {
    throw "The PowerShell coverage trace is empty."
}

$tracePoints = @(
    $ast.FindAll(
        {
            param($node)
            $node -is [System.Management.Automation.Language.StatementAst] -and
                $node -isnot [System.Management.Automation.Language.FunctionDefinitionAst]
        },
        $true
    ) |
        ForEach-Object {
            [pscustomobject]@{
                Line = $_.Extent.StartLineNumber
                Column = $_.Extent.StartColumnNumber
                Key = Get-PositionKey `
                    -Line $_.Extent.StartLineNumber `
                    -Column $_.Extent.StartColumnNumber
            }
        } |
        Sort-Object -Property Line, Column -Unique
)

$logicalStatements = @{}
$statementBlocks = @(
    $ast.FindAll(
        {
            param($node)
            $node -is [System.Management.Automation.Language.NamedBlockAst] -or
                $node -is [System.Management.Automation.Language.StatementBlockAst]
        },
        $true
    )
)
foreach ($block in $statementBlocks) {
    foreach ($statement in @($block.Statements)) {
        if ($statement -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
            continue
        }
        $statementKey = Get-ExtentKey -Extent $statement.Extent
        if (-not $logicalStatements.ContainsKey($statementKey)) {
            $logicalStatements[$statementKey] = $statement
        }
    }
}

$statementResults = @(
    foreach ($entry in $logicalStatements.GetEnumerator()) {
        $covered = @(
            $hitPoints.Values |
                Where-Object { Test-PointInExtent -Point $_ -Extent $entry.Value.Extent }
        ).Count -gt 0
        [pscustomobject]@{
            Key = $entry.Key
            Line = $entry.Value.Extent.StartLineNumber
            Covered = $covered
        }
    }
)
$coveredStatements = @($statementResults | Where-Object { $_.Covered })
$coveredStatementByKey = @{}
foreach ($statementResult in $statementResults) {
    $coveredStatementByKey[$statementResult.Key] = $statementResult.Covered
}

$statementLines = @($statementResults.Line | Sort-Object -Unique)
$coveredLines = @(
    $coveredStatements.Line | Sort-Object -Unique
)

$functions = @(
    $ast.FindAll(
        { param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] },
        $true
    )
)
$functionResults = @(
    foreach ($function in $functions) {
        $bodyStatements = @($function.Body.EndBlock.Statements)
        if ($bodyStatements.Count -eq 0) {
            continue
        }
        $entryKey = Get-ExtentKey -Extent $bodyStatements[0].Extent
        [pscustomobject]@{
            Name = $function.Name
            Covered = [bool]$coveredStatementByKey[$entryKey]
        }
    }
)
$coveredFunctions = @($functionResults | Where-Object { $_.Covered })

$decisionDefinitions = [System.Collections.Generic.List[object]]::new()
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
        $conditionPoint = Get-CoverageSignalPoint `
            -TracePoints $tracePoints `
            -ObservedPoints @($hitPoints.Values) `
            -Extent $clause.Item1.Extent
        $bodyPoint = Get-FirstTracePointInExtent `
            -TracePoints $tracePoints `
            -Extent $bodyStatements[0].Extent
        if (-not $conditionPoint -or -not $bodyPoint) {
            throw "An if decision did not expose breakpointable condition and body positions."
        }
        $decisionDefinitions.Add(
            [pscustomobject]@{
                Kind = "If"
                Line = $clause.Item1.Extent.StartLineNumber
                ConditionKey = $conditionPoint.Key
                BodyExtent = $bodyStatements[0].Extent
            }
        )
    }
}

$loopStatements = @(
    $ast.FindAll(
        { param($node) $node -is [System.Management.Automation.Language.LoopStatementAst] },
        $true
    )
)
foreach ($loopStatement in $loopStatements) {
    $bodyStatements = @($loopStatement.Body.Statements)
    if (-not $loopStatement.Condition -or $bodyStatements.Count -eq 0) {
        continue
    }
    $conditionPoint = Get-CoverageSignalPoint `
        -TracePoints $tracePoints `
        -ObservedPoints @($hitPoints.Values) `
        -Extent $loopStatement.Condition.Extent
    $bodyPoint = Get-FirstTracePointInExtent `
        -TracePoints $tracePoints `
        -Extent $bodyStatements[0].Extent
    if (-not $conditionPoint -or -not $bodyPoint) {
        throw "A loop decision did not expose breakpointable condition and body positions."
    }
    $decisionDefinitions.Add(
        [pscustomobject]@{
            Kind = $loopStatement.GetType().Name
            Line = $loopStatement.Extent.StartLineNumber
            ConditionKey = $conditionPoint.Key
            BodyExtent = $bodyStatements[0].Extent
        }
    )
}

$branchTargets = @(
    foreach ($decision in $decisionDefinitions) {
        foreach ($bodyHit in @($true, $false)) {
            [pscustomobject]@{
                Kind = $decision.Kind
                Line = $decision.Line
                ConditionKey = $decision.ConditionKey
                BodyExtent = $decision.BodyExtent
                BodyHit = $bodyHit
            }
        }
    }
)
$evaluatedBranchTargets = @(
    foreach ($target in $branchTargets) {
        [pscustomobject]@{
            Kind = $target.Kind
            Line = $target.Line
            Outcome = if ($target.BodyHit) { "body-entered" } else { "body-skipped" }
            Covered = Test-DecisionOutcome `
                -Traces $traces `
                -ConditionKey $target.ConditionKey `
                -BodyExtent $target.BodyExtent `
                -ExpectedBodyHit $target.BodyHit
        }
    }
)
$coveredBranchTargets = @($evaluatedBranchTargets | Where-Object { $_.Covered })

$metrics = @(
    [pscustomobject]@{
        Metric = "Statement"
        Covered = $coveredStatements.Count
        Total = $statementResults.Count
        Percent = Measure-Percentage $coveredStatements.Count $statementResults.Count
        Semantics = "Direct block statements covered when a breakpointable position in their extent ran."
    },
    [pscustomobject]@{
        Metric = "Branch"
        Covered = $coveredBranchTargets.Count
        Total = $branchTargets.Count
        Percent = Measure-Percentage $coveredBranchTargets.Count $branchTargets.Count
        Semantics = "Body-entered and body-skipped outcomes for if clauses and loop statements."
    },
    [pscustomobject]@{
        Metric = "Function"
        Covered = $coveredFunctions.Count
        Total = $functionResults.Count
        Percent = Measure-Percentage $coveredFunctions.Count $functionResults.Count
        Semantics = "Functions whose first direct body statement was covered."
    },
    [pscustomobject]@{
        Metric = "Line"
        Covered = $coveredLines.Count
        Total = $statementLines.Count
        Percent = Measure-Percentage $coveredLines.Count $statementLines.Count
        Semantics = "Unique direct-statement start lines with at least one covered statement."
    }
)

$metrics | ConvertTo-Json -Depth 3
$failures = @($metrics | Where-Object { $_.Percent -lt $Minimum })
if ($failures.Count -gt 0) {
    $missingBranches = @(
        $evaluatedBranchTargets |
            Where-Object { -not $_.Covered } |
            ForEach-Object { "$($_.Kind):$($_.Line):$($_.Outcome)" }
    )
    [Console]::Error.WriteLine("Uncovered decision outcomes: $($missingBranches -join ', ')")
    $names = ($failures | ForEach-Object { "$($_.Metric)=$($_.Percent)%" }) -join ", "
    throw "PowerShell launcher coverage is below $Minimum percent: $names."
}
