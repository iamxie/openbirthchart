# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
param(
    [string]$OutputDirectory = '',
    [ValidateSet(1, 4, 8, 12)][int]$Workers = 12,
    [ValidateSet('all', 'actual', 'zero')][string]$Mode = 'all',
    [switch]$Legacy1287
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $PSScriptRoot ('results/numerical/check-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
if ($Legacy1287) {
    Write-Output 'Historical 1287-case comparison against original 0.6.5; this is not the current 1200-case baseline.'
    & .venv-desktop/Scripts/python.exe scripts/numerical_regression.py check --output $OutputDirectory
    if ($LASTEXITCODE -ne 0) { throw "Historical numerical comparison differs ($LASTEXITCODE). Review $OutputDirectory; do not overwrite the archive." }
    Write-Output "Historical comparison: $OutputDirectory/comparison/summary.md"
    return
}
$taskRegistry = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'regression/main-current.json') -Raw | ConvertFrom-Json
if ($taskRegistry.active_suite -ne 'main-v2' -or $taskRegistry.cases_per_dataset -ne 1200) { throw 'Unknown current 1200-case suite.' }
if (Test-Path -LiteralPath $OutputDirectory) { throw "Output already exists: $OutputDirectory" }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$taskModes = if ($Mode -eq 'all') { @('actual', 'zero') } else { @($Mode) }
$taskExit = 0
foreach ($taskMode in $taskModes) {
    $taskEntry = $taskRegistry.modes.$taskMode.product
    $taskBaseline = Join-Path $PSScriptRoot $taskEntry.path
    $taskCases = Join-Path $taskBaseline 'cases.json'
    if ((Get-FileHash -LiteralPath (Join-Path $taskBaseline 'SHA256SUMS.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.seal_sha256) {
        throw "Active seal hash mismatch: $taskMode"
    }
    if ((Get-FileHash -LiteralPath $taskCases -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.cases_sha256) {
        throw "Active cases hash mismatch: $taskMode"
    }
    $taskRun = Join-Path $OutputDirectory ('run-' + $taskMode)
    $taskReport = Join-Path $OutputDirectory ('exact-' + $taskMode + '.json')
    & .venv-desktop/Scripts/python.exe scripts/complete_regression.py verify $taskBaseline
    if ($LASTEXITCODE -ne 0) { throw "Baseline integrity failed: $taskMode" }
    & .venv-desktop/Scripts/python.exe scripts/complete_regression.py run --cases $taskCases --engine product --workers $Workers --output $taskRun
    if ($LASTEXITCODE -ne 0) { throw "Capture failed: $taskMode" }
    & .venv-desktop/Scripts/python.exe scripts/complete_regression.py exact --first $taskBaseline --second $taskRun --output $taskReport
    if ($LASTEXITCODE -ne 0) { $taskExit = $LASTEXITCODE }
    Write-Output "Exact comparison ($taskMode): $taskReport"
}
if ($taskExit -ne 0) { throw "Numerical regression differs. Review $OutputDirectory; do not overwrite the baseline." }
Write-Output "Current 1200-case regression passed: $OutputDirectory"
