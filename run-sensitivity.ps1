# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv-core/Scripts/python.exe'
foreach ($required in @($python,'time-data-sources.lock.json','results/utc/core.json','results/utc/summary.json')) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing $required. Complete README UTC preparation first." }
}
New-Item -ItemType Directory -Force results/sensitivity | Out-Null
$previous = @(Get-ChildItem -LiteralPath results/sensitivity -File)
if ($previous.Count) {
    $archive = Join-Path $PSScriptRoot ('results/sensitivity/history/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Force $archive | Out-Null
    $previous | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $archive }
    foreach ($inputFile in @('sensitivity-cases.json','SENSITIVITY_REPORT.md')) {
        if (Test-Path -LiteralPath $inputFile) { Copy-Item -LiteralPath $inputFile -Destination $archive }
    }
    Write-Output "Previous sensitivity results preserved: $archive"
}
function Invoke-Checked {
    & $python @args
    if ($LASTEXITCODE -ne 0) { throw "Sensitivity stage failed ($LASTEXITCODE): $args" }
}
Invoke-Checked -m unittest discover -s tests -p test_sensitivity.py -v
Invoke-Checked scripts/measure_sensitivity.py
Invoke-Checked scripts/summarize_sensitivity.py
Invoke-Checked scripts/build_sensitivity_report.py
Write-Output 'Completed SENSITIVITY_REPORT.md. This measures input sensitivity, not absolute astronomical accuracy.'
