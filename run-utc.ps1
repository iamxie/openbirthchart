# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
# Separate experiment; the first-round results and REPORT.md remain untouched.
# Use powershell -File run-utc.ps1 when the parent shell needs the exact exit code.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$corePython = Join-Path $PSScriptRoot '.venv-core/Scripts/python.exe'
$referencePython = Join-Path $PSScriptRoot '.venv-reference/Scripts/python.exe'
foreach ($required in @($corePython,$referencePython,'time-data-sources.lock.json')) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing $required. Follow README UTC setup." }
}
New-Item -ItemType Directory -Force results/utc | Out-Null
$previous = @(Get-ChildItem -LiteralPath results/utc -File)
if ($previous.Count) {
    $archive = Join-Path $PSScriptRoot ('results/utc/history/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Force $archive | Out-Null
    $previous | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $archive }
    foreach ($inputFile in @('utc-cases.json','UTC_REPORT.md')) {
        if (Test-Path -LiteralPath $inputFile) { Copy-Item -LiteralPath $inputFile -Destination $archive }
    }
    Write-Output "Previous UTC results preserved: $archive"
}
function Invoke-Checked {
    param([string]$Python,[string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "UTC stage failed ($LASTEXITCODE): $Arguments" }
}
Invoke-Checked $corePython @('-m','unittest','discover','-s','tests','-v')
Invoke-Checked $corePython @('scripts/build_utc_cases.py')
Invoke-Checked $corePython @('scripts/utc_worker.py','core')
Invoke-Checked $referencePython @('scripts/utc_worker.py','reference')
& $corePython scripts/compare_utc.py
$comparisonExit=$LASTEXITCODE
if ($comparisonExit -notin @(0,2)) { throw "UTC comparison failed: $comparisonExit" }
Invoke-Checked $corePython @('scripts/build_utc_report.py')
Write-Output "Completed UTC_REPORT.md. Exit $comparisonExit (2 = full-grid numerical gate remains unmet)."
exit $comparisonExit
