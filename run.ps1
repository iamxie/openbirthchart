# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
# Offline validation. Exit 2 means a numerical acceptance gate failed, not an aborted run.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$corePython = Join-Path $PSScriptRoot '.venv-core/Scripts/python.exe'
$referencePython = Join-Path $PSScriptRoot '.venv-reference/Scripts/python.exe'
foreach ($required in @($corePython, $referencePython, 'cases.json', 'data-sources.lock.json', 'vendor/libephemeris/scripts/check_algorithm_provenance.py')) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing $required. Follow README setup first." }
}
New-Item -ItemType Directory -Force results | Out-Null
$previous = @(Get-ChildItem -LiteralPath results -File)
if ($previous.Count) {
    $archive = Join-Path $PSScriptRoot ('results/history/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Force $archive | Out-Null
    $previous | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $archive }
    Write-Output "Previous raw results preserved: $archive"
}
function Invoke-Checked {
    param([string]$Python, [string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Validation stage failed ($LASTEXITCODE): $Arguments" }
}
Invoke-Checked $corePython @('-m','unittest','discover','-s','tests','-p','test_validation.py','-v')
Invoke-Checked $corePython @('scripts/audit_dependencies.py')
& $corePython vendor/libephemeris/scripts/check_algorithm_provenance.py *> results/upstream-provenance-structure.txt
if ($LASTEXITCODE -ne 0) { throw 'Upstream provenance structure check failed' }
Invoke-Checked $corePython @('scripts/worker.py','core','--output','results/core.json')
Invoke-Checked $referencePython @('scripts/worker.py','reference','--output','results/reference.json')
& $corePython scripts/compare.py
$comparisonExit = $LASTEXITCODE
if ($comparisonExit -notin @(0,2)) { throw "Comparison failed to execute: $comparisonExit" }
Invoke-Checked $corePython @('scripts/check_core_contracts.py')
Invoke-Checked $referencePython @('scripts/diagnose.py','reference')
Invoke-Checked $corePython @('scripts/diagnose.py','core')
Invoke-Checked $corePython @('scripts/summarize_diagnostics.py')
Invoke-Checked $corePython @('scripts/build_report.py')
Write-Output "Completed. See REPORT.md. Exit $comparisonExit (0=all gates passed; 2=numerical gate failed)."
exit $comparisonExit
