# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$corePython = Join-Path $PSScriptRoot '.venv-core/Scripts/python.exe'
$referencePython = Join-Path $PSScriptRoot '.venv-reference/Scripts/python.exe'
foreach ($required in @($corePython,$referencePython,'observation-data-sources.lock.json')) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing $required. See README preparation." }
}
New-Item -ItemType Directory -Force results/observations | Out-Null
$previous = @(Get-ChildItem -LiteralPath results/observations -File)
if ($previous.Count) {
    $archive = Join-Path $PSScriptRoot ('results/observations/history/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Force $archive | Out-Null
    $previous | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $archive }
    if (Test-Path OBSERVATIONS_REPORT.md) { Copy-Item OBSERVATIONS_REPORT.md $archive }
}
function Invoke-Checked {
    param([string]$Python, [string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Observation stage failed ($LASTEXITCODE): $Arguments" }
}
Invoke-Checked $corePython @('-m','unittest','discover','-s','tests','-p','test_observations.py','-v')
Invoke-Checked $corePython @('scripts/observation_worker.py','core')
Invoke-Checked $referencePython @('scripts/observation_worker.py','reference')
Invoke-Checked $corePython @('scripts/observation_compare.py')
Invoke-Checked $corePython @('scripts/build_observations_report.py')
Write-Output 'Completed OBSERVATIONS_REPORT.md. Residuals are not absolute engine errors or a milliarcsecond accuracy certification.'
