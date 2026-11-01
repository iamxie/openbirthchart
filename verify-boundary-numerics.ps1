# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
param(
    [string]$OutputDirectory = '',
    [ValidateSet(1, 4, 8, 12)][int]$Workers = 12,
    [ValidateSet('all', 'actual', 'zero')][string]$Mode = 'all'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $PSScriptRoot ('results/numerical/boundary-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
$taskRegistry = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'regression/boundary-current.json') -Raw | ConvertFrom-Json
if ($taskRegistry.active_suite -ne 'boundary-v2' -or $taskRegistry.cases_per_dataset -ne 87) { throw 'Unknown boundary suite.' }
if (Test-Path -LiteralPath $OutputDirectory) { throw "Output already exists: $OutputDirectory" }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$taskModes = if ($Mode -eq 'all') { @('actual', 'zero') } else { @($Mode) }
$taskExit = 0
foreach ($taskMode in $taskModes) {
    $taskEntry = $taskRegistry.modes.$taskMode.product
    $taskBaseline = Join-Path $PSScriptRoot $taskEntry.path
    $taskCases = Join-Path $taskBaseline 'cases.json'
    if ((Get-FileHash -LiteralPath (Join-Path $taskBaseline 'SHA256SUMS.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.seal_sha256) { throw "Seal hash mismatch: $taskMode" }
    if ((Get-FileHash -LiteralPath $taskCases -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.cases_sha256) { throw "Cases hash mismatch: $taskMode" }
    & .venv-desktop/Scripts/python.exe scripts/complete_regression.py verify $taskBaseline
    if ($LASTEXITCODE -ne 0) { throw "Baseline integrity failed: $taskMode" }
    $taskRun = Join-Path $OutputDirectory ('run-' + $taskMode)
    $taskReport = Join-Path $OutputDirectory ('exact-' + $taskMode + '.json')
    & .venv-desktop/Scripts/python.exe scripts/complete_regression.py run --cases $taskCases --engine product --workers $Workers --output $taskRun
    if ($LASTEXITCODE -ne 0) { throw "Capture failed: $taskMode" }
    & .venv-desktop/Scripts/python.exe scripts/complete_regression.py exact --first $taskBaseline --second $taskRun --output $taskReport
    if ($LASTEXITCODE -ne 0) { $taskExit = $LASTEXITCODE }
    Write-Output "Exact boundary comparison ($taskMode): $taskReport"
}
if ($taskExit -ne 0) { throw "Boundary regression differs. Review $OutputDirectory; keep the baseline intact." }
Write-Output "Current 87-case boundary regression passed: $OutputDirectory"
