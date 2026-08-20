#Requires -Version 7.0
<#
.SYNOPSIS
    Runs the Bike Store pipeline end to end: Mongo -> Postgres ETL, then
    Postgres data-quality tests, one after another.

.DESCRIPTION
    Lives in pipeline\, one level below the project root -- same layout as
    scripts\, tests\, and utils\. Resolves the project root by walking
    upward looking for a folder that contains both scripts\ and utils\,
    the same root-detection pattern already used inside mongo_to_postgres.py
    and plpgsql_tests.py, so this script doesn't care where it's invoked
    from or what your current directory is.

    Uses `uv run` to execute each stage so it always runs against the
    project's managed venv. Falls back to .venv\Scripts\python.exe if uv
    isn't on PATH.

    Every run writes a full log to logs\pipeline\pipeline_<timestamp>.log
    (same convention as logs\tests\<n>_<timestamp>.log from the Python
    side) in addition to what's printed to the terminal.

.PARAMETER FullRefresh
    Pass-through to mongo_to_postgres.py --full-refresh (truncate + reload
    every collection instead of incremental).

.PARAMETER Collection
    Restrict the ETL to specific collection(s). Repeatable, e.g.
    -Collection orders -Collection staffs. Pass-through to
    mongo_to_postgres.py --collection <name>.

.PARAMETER SkipExtract
    Skip stage 1 (ETL) and go straight to data-quality tests. Useful when
    you just want to re-run tests against data that's already loaded.

.PARAMETER SkipTests
    Skip stage 2 (data-quality tests) and only run the ETL.

.PARAMETER ShowFailures
    Pass-through to plpgsql_tests.py --show-failures.

.PARAMETER MaxRows
    Pass-through to plpgsql_tests.py --max-rows.

.PARAMETER TestsDir
    Pass-through to plpgsql_tests.py --tests-dir, if you want to point at
    a folder other than the project's default tests\.

.PARAMETER Dsn
    Pass-through to plpgsql_tests.py --dsn, to run tests against a
    one-off connection instead of the shared .env-configured engine.

.PARAMETER ContinueOnError
    By default, if the ETL stage fails the pipeline stops before running
    tests -- no point data-quality-checking a load that didn't finish.
    Pass this switch to run the tests anyway.

.EXAMPLE
    .\run_pipeline.ps1

.EXAMPLE
    .\run_pipeline.ps1 -FullRefresh

.EXAMPLE
    .\run_pipeline.ps1 -Collection orders -Collection staffs

.EXAMPLE
    .\run_pipeline.ps1 -SkipExtract -ShowFailures -MaxRows 10

.EXAMPLE
    .\run_pipeline.ps1 -ContinueOnError
#>

[CmdletBinding()]
param(
    [switch]$FullRefresh,
    [string[]]$Collection = @(),
    [switch]$SkipExtract,
    [switch]$SkipTests,
    [switch]$ShowFailures,
    [int]$MaxRows,
    [string]$TestsDir,
    [string]$Dsn,
    [switch]$ContinueOnError
)

$ErrorActionPreference = "Stop"

# Force UTF-8 stdio in the child Python processes. Once their stdout is
# piped through this script (2>&1 | ForEach-Object below), Python on
# Windows falls back to the system ANSI codepage (cp1252) instead of a
# real console encoding -- and cp1252 can't encode characters like the
# "→" used in Rich panel titles, which crashes the process. Setting these
# forces UTF-8 regardless of whether stdout is a real console or a pipe.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Make the PowerShell console itself interpret bytes written by child
# processes as UTF-8 (not the legacy OEM/ANSI codepage). Without this,
# the arrows/box-drawing characters Rich prints come through as mojibake
# even though PYTHONIOENCODING above is now correct on the Python side.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    Write-Warning "Could not set console output encoding to UTF-8: $_"
}

# ─────────────────────────────────────────────────────────────────────────
# Project root resolution
# Mirrors _find_project_root() in mongo_to_postgres.py / plpgsql_tests.py:
# walk upward from this script's own folder until we find a directory that
# contains both scripts\ and utils\. Works regardless of cwd.
# ─────────────────────────────────────────────────────────────────────────
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
    throw "Could not locate the project root (looked for a folder containing " +
          "both 'utils' and 'scripts') walking up from: $StartPath"
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

# ─────────────────────────────────────────────────────────────────────────
# Logging — timestamped, mirrors the "TS | LEVEL | message" shape used by
# utils/logger.py so pipeline.log and the Python stage logs read the same.
# ─────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────
# Python runner — prefer `uv run` so we always hit the project's managed
# venv; fall back to .venv\Scripts\python.exe if uv isn't on PATH.
# ─────────────────────────────────────────────────────────────────────────
$UseUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not $UseUv -and -not (Test-Path -LiteralPath $VenvPython)) {
    throw "Neither 'uv' (on PATH) nor a venv at $VenvPython was found. " +
          "Install uv (https://docs.astral.sh/uv/) or create the venv first."
}

# Collects one row per stage (run or skipped) for the end-of-run summary table.
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

# ─────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────
Write-Log "════════════════════════════════════════════════════"
Write-Log "Bike Store Pipeline — run $RunId"
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
            Write-Log "ETL failed — skipping data-quality tests (pass -ContinueOnError to run them anyway)." -Level ERROR
            Write-Log "PIPELINE FAILED (exit $overallExit)" -Level ERROR
            exit $overallExit
        }
        Write-Log "ETL failed but -ContinueOnError was set — proceeding to tests anyway." -Level WARN
    }
}
else {
    Write-Log "Stage 1 (ETL) skipped via -SkipExtract" -Level WARN
    $script:StageResults += [PSCustomObject]@{
        Stage = "Mongo -> Postgres ETL"; Status = "SKIPPED"; ExitCode = "-"; Duration = "-"
    }
}

# ── Stage 2: Data-quality tests ─────────────────────────────────────────
if (-not $SkipTests) {
    $testArgs = @()
    if ($ShowFailures) { $testArgs += "--show-failures" }
    if ($PSBoundParameters.ContainsKey("MaxRows"))  { $testArgs += @("--max-rows", $MaxRows) }
    if ($PSBoundParameters.ContainsKey("TestsDir"))  { $testArgs += @("--tests-dir", $TestsDir) }
    if ($PSBoundParameters.ContainsKey("Dsn"))       { $testArgs += @("--dsn", $Dsn) }

    $testExit = Invoke-Stage -Name "Data Quality Tests" `
        -ScriptPath (Join-Path $ScriptsDir "plpgsql_tests.py") `
        -Arguments $testArgs

    if ($testExit -ne 0) { $overallExit = $testExit }
}
else {
    Write-Log "Stage 2 (tests) skipped via -SkipTests" -Level WARN
    $script:StageResults += [PSCustomObject]@{
        Stage = "Data Quality Tests"; Status = "SKIPPED"; ExitCode = "-"; Duration = "-"
    }
}

# ── Final summary ────────────────────────────────────────────────────────
$totalDuration = (Get-Date) - $pipelineStart
$totalDurationStr = "{0:mm}m {0:ss}s" -f $totalDuration

Write-Log "════════════════════════════════════════════════════"
Write-Log "PIPELINE SUMMARY — run $RunId"
Write-Log "════════════════════════════════════════════════════"

# Render the stage table once, then fan it out to console (colour-coded)
# and log file (plain) so both stay in sync.
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
}
else {
    Write-Log "RESULT: PIPELINE FAILED (exit $overallExit)" -Level ERROR
}
Write-Log "════════════════════════════════════════════════════"

exit $overallExit