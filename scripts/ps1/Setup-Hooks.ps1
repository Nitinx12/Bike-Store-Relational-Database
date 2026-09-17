#Requires -Version 7.0
<#
.SYNOPSIS
    Install .githooks as the repo's hook source (Windows/PowerShell)
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HooksDir = Join-Path $RepoRoot ".githooks"

if (-not (Test-Path -LiteralPath $HooksDir -PathType Container)) {
    throw ".githooks/ not found at $HooksDir"
}

& git -C $RepoRoot config core.hooksPath .githooks
Write-Host "[PASS] git hooks installed: core.hooksPath=.githooks" -ForegroundColor Green
Write-Host "  Hooks: $((Get-ChildItem $HooksDir -File | Select-Object -ExpandProperty Name) -join ' ')"
Write-Host "  Test:  git commit --allow-empty -m 'chore: test hooks'"
