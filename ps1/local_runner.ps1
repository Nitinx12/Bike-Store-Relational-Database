#Requires -Version 7.0
<#
.SYNOPSIS
    Runs the complete Bike Store pipeline end-to-end: Mongo -> Postgres ETL, 
    PL/pgSQL Loop Data Quality tests, and the Great Expectations suite.

.DESCRIPTION
    Lives in pipeline\, one level below the project root. Resolves the project 
    root by walking upward looking for a folder containing both scripts\ and utils\.
    
    Uses `uv run` to execute each stage against the managed virtual environment, 
    falling back to .venv\Scripts\python.exe if uv is not on PATH.
    
    Writes a full run log to logs\pipeline\pipeline_<timestamp>.log.

.PARAMETER FullRefresh
    Pass-through to mongo_to_postgres.py --full-refresh (truncate + reload).

.PARAMETER Collection
    Restrict ETL to specific collection(s), e.g., -Collection orders -Collection staffs.

.PARAMETER SkipExtract
    Skip Stage 1 (Mongo -> Postgres ETL).

.PARAMETER SkipPlpgsql
    Skip Stage 2 (PL/pgSQL loop data quality tests).

.PARAMETER SkipGx
    Skip Stage 3 (Great Expectations validation suite).

.PARAMETER GxTables
    Restrict Great Expectations validation to specific table(s), e.g., -GxTables orders -GxTables products.

.PARAMETER ContinueOnError
    Proceed to subsequent pipeline stages even if an earlier stage fails.

.EXAMPLE
    .\local_runner.ps1

.EXAMPLE
    .\local_runner.ps1 -FullRefresh

.EXAMPLE
    .\local_runner.ps1 -SkipExtract -GxTables orders products

.EXAMPLE
    .\local_runner.ps1 -ContinueOnError
#>

[CmdletBinding()]
param(
    [switch]$FullRefresh,
    [string[]]$Collection = @(),
    [switch]$SkipExtract,
    [switch]$SkipPlpgsql,
    [switch]$SkipGx,
    [string[]]$GxTables = @(),
    [switch]$ContinueOnError
)

$ErrorActionPreference = "Stop"

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    Write-Warning "Could not set console output encoding to UTF-8: $_"
}

function Find-ProjectRoot {
    param([Parameter(Mandatory)][string]$StartPath)

    $current = Get-Item -LiteralPath $StartPath
    for ($i = 0; $i -lt 8; $i++) {
        $utilsPath   = Join-Path $current.FullName "utils"
        $scriptsPath = Join-Path $current.FullName "scripts"
        if ((Test-Path -LiteralPath $utilsPath -PathType Container) -and
            (Test-Path -LiteralPath $scriptsPath -PathType Container)) {
            return $current.FullName
        }
        if ($null -eq $current.Parent) { break }
        $current = $current.Parent
    }
    throw "Could not locate the project root walking up from: $StartPath"
}

$PipelineDir = $PSScriptRoot
$ProjectRoot = Find-ProjectRoot -StartPath $PipelineDir
$ScriptsDir  = Join-Path $ProjectRoot "scripts"
$LogsDir     = Join-Path $ProjectRoot "logs\pipeline"

if (-not (Test-Path -LiteralPath $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$RunId   = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogsDir "pipeline_$RunId.log"

function Write-Log {
    param(
        [string]$Message = "",
        [ValidateSet("INFO", "WARN", "ERROR", "SUCCESS")]
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp | $($Level.PadRight(8))| $Message"
    Add-Content -LiteralPath $LogFile -Value $line

    switch ($Level) {
        "ERROR"   { Write-Host $line -ForegroundColor Red }
        "WARN"    { Write-Host $line -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $line -ForegroundColor Green }
        default   { Write-Host $line }
    }
}

$UseUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not $UseUv -and -not (Test-Path -LiteralPath $VenvPython)) {
    throw "Neither 'uv' nor a venv at $VenvPython was found."
}

$script:StageResults = @()

function Invoke-Stage {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$ScriptPath,
        [string[]]$Arguments = @()
    )

    Write-Log "───── STAGE: $Name ─────"
    $runnerDesc = if ($UseUv) { "uv run python" } else { $VenvPython }
    Write-Log "Command: $runnerDesc `"$ScriptPath`" $($Arguments -join ' ')"

    $stageStart = Get-Date
    Push-Location $ProjectRoot
    try {
        if ($UseUv) {
            & uv run python $ScriptPath @Arguments 2>&1 | ForEach-Object {
                $line = $_.ToString()
                Add-Content -LiteralPath $LogFile -Value $line
                Write-Host $line
            }
        }
        else {
            & $VenvPython $ScriptPath @Arguments 2>&1 | ForEach-Object {
                $line = $_.ToString()
                Add-Content -LiteralPath $LogFile -Value $line
                Write-Host $line
            }
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    $duration = (Get-Date) - $stageStart
    $durationStr = "{0:mm}m {0:ss}s" -f $duration

    if ($exitCode -eq 0) {
        Write-Log "STAGE '$Name' completed OK in $durationStr" -Level SUCCESS
    }
    else {
        Write-Log "STAGE '$Name' FAILED (exit $exitCode) after $durationStr" -Level ERROR
    }

    $script:StageResults += [PSCustomObject]@{
        Stage    = $Name
        Status   = if ($exitCode -eq 0) { "OK" } else { "FAILED" }
        ExitCode = $exitCode
        Duration = $durationStr
    }

    return $exitCode
}

Write-Log "════════════════════════════════════════════════════"
Write-Log "Bike Store Full Pipeline — run $RunId"
Write-Log "Project root : $ProjectRoot"
Write-Log "Runner       : $(if ($UseUv) { 'uv run' } else { $VenvPython })"
Write-Log "Log file     : $LogFile"
Write-Log "════════════════════════════════════════════════════"

$pipelineStart = Get-Date
$overallExit = 0

# ── Stage 1: Mongo -> Postgres ETL ──────────────────────────────────────
if (-not $SkipExtract) {
    $etlArgs = @()
    if ($FullRefresh) { $etlArgs += "--full-refresh" }
    foreach ($c in $Collection) { $etlArgs += @("--collection", $c) }

    $etlExit = Invoke-Stage -Name "Mongo -> Postgres ETL" `
        -ScriptPath (Join-Path $ScriptsDir "mongo_to_postgres.py") `
        -Arguments $etlArgs

    if ($etlExit -ne 0) {
        $overallExit = $etlExit
        if (-not $ContinueOnError) {
            Write-Log "ETL failed — aborting pipeline (pass -ContinueOnError to run remaining stages)." -Level ERROR
            exit $overallExit
        }
        Write-Log "ETL failed but -ContinueOnError was set — proceeding..." -Level WARN
    }
} else {
    Write-Log "Stage 1 (ETL) skipped via -SkipExtract" -Level WARN
    $script:StageResults += [PSCustomObject]@{
        Stage = "Mongo -> Postgres ETL"; Status = "SKIPPED"; ExitCode = "-"; Duration = "-"
    }
}

# ── Stage 2: PL/pgSQL Loop Data Quality Tests ───────────────────────────
if (-not $SkipPlpgsql) {
    $plpgsqlExit = Invoke-Stage -Name "PL/pgSQL Loop Tests" `
        -ScriptPath (Join-Path $ScriptsDir "plpgsql_loops_tests.py")

    if ($plpgsqlExit -ne 0) {
        $overallExit = $plpgsqlExit
        if (-not $ContinueOnError) {
            Write-Log "PL/pgSQL tests failed — aborting pipeline." -Level ERROR
            exit $overallExit
        }
        Write-Log "PL/pgSQL tests failed but -ContinueOnError was set — proceeding..." -Level WARN
    }
} else {
    Write-Log "Stage 2 (PL/pgSQL Loops) skipped via -SkipPlpgsql" -Level WARN
    $script:StageResults += [PSCustomObject]@{
        Stage = "PL/pgSQL Loop Tests"; Status = "SKIPPED"; ExitCode = "-"; Duration = "-"
    }
}

# ── Stage 3: Great Expectations Suite ───────────────────────────────────
if (-not $SkipGx) {
    $gxArgs = @()
    foreach ($t in $GxTables) { $gxArgs += $t }

    $gxExit = Invoke-Stage -Name "Great Expectations Suite" `
        -ScriptPath (Join-Path $ScriptsDir "run_gx.py") `
        -Arguments $gxArgs

    if ($gxExit -ne 0) {
        $overallExit = $gxExit
    }
} else {
    Write-Log "Stage 3 (Great Expectations) skipped via -SkipGx" -Level WARN
    $script:StageResults += [PSCustomObject]@{
        Stage = "Great Expectations Suite"; Status = "SKIPPED"; ExitCode = "-"; Duration = "-"
    }
}

# ── Final Summary ────────────────────────────────────────────────────────
$totalDuration = (Get-Date) - $pipelineStart
$totalDurationStr = "{0:mm}m {0:ss}s" -f $totalDuration

Write-Log "════════════════════════════════════════════════════"
Write-Log "PIPELINE SUMMARY — run $RunId"
Write-Log "════════════════════════════════════════════════════"

$tableText = ($script:StageResults | Format-Table -AutoSize | Out-String).TrimEnd()
foreach ($tableLine in ($tableText -split "`r?`n")) {
    Add-Content -LiteralPath $LogFile -Value $tableLine
    if ($tableLine -match "FAILED") {
        Write-Host $tableLine -ForegroundColor Red
    }
    elseif ($tableLine -match "SKIPPED") {
        Write-Host $tableLine -ForegroundColor Yellow
    }
    elseif ($tableLine -match "\bOK\b") {
        Write-Host $tableLine -ForegroundColor Green
    }
    else {
        Write-Host $tableLine
    }
}

Write-Log ""
Write-Log "Total duration : $totalDurationStr"
Write-Log "Log file       : $LogFile"

if ($overallExit -eq 0) {
    Write-Log "RESULT: PIPELINE PASSED" -Level SUCCESS
} else {
    Write-Log "RESULT: PIPELINE FAILED (exit $overallExit)" -Level ERROR
}
Write-Log "════════════════════════════════════════════════════"

exit $overallExit