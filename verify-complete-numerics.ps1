# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
param(
    [ValidateSet(1, 4, 8, 12)]
    [int]$Workers = 12,
    [string]$Output = '',
    [ValidateSet('all', 'actual', 'zero')]
    [string]$Mode = 'all'
)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv-desktop\Scripts\python.exe'
$taskTool = Join-Path $taskRoot 'scripts\complete_regression.py'
$taskRegistry = Get-Content -LiteralPath (Join-Path $taskRoot 'regression\complete-current.json') -Raw | ConvertFrom-Json
if ($taskRegistry.active_suite -ne 'complete-v2') { throw 'Unknown active complete baseline suite.' }
if (-not $Output) {
    $Output = Join-Path $taskRoot ('results\numerical\complete-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
if (Test-Path -LiteralPath $Output) { throw "Output already exists: $Output" }
New-Item -ItemType Directory -Path $Output | Out-Null
$taskModes = if ($Mode -eq 'all') { @('actual', 'zero') } else { @($Mode) }
$taskExit = 0
foreach ($taskMode in $taskModes) {
    $taskEntry = $taskRegistry.modes.$taskMode.product
    $taskBaseline = Join-Path $taskRoot $taskEntry.path
    $taskCases = Join-Path $taskBaseline 'cases.json'
    if ((Get-FileHash -LiteralPath (Join-Path $taskBaseline 'SHA256SUMS.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.seal_sha256) {
        throw "Active seal hash mismatch: $taskMode"
    }
    if ((Get-FileHash -LiteralPath $taskCases -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskEntry.cases_sha256) {
        throw "Active cases hash mismatch: $taskMode"
    }
    $taskRun = Join-Path $Output ('run-' + $taskMode)
    $taskReport = Join-Path $Output ('exact-' + $taskMode + '.json')
    & $taskPython $taskTool verify $taskBaseline
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $taskPython $taskTool run --cases $taskCases --engine product --workers $Workers --output $taskRun
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $taskPython $taskTool exact --first $taskBaseline --second $taskRun --output $taskReport
    if ($LASTEXITCODE -ne 0) { $taskExit = $LASTEXITCODE }
    Write-Output "Exact comparison ($taskMode): $taskReport"
}
exit $taskExit
