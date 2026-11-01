# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
param(
    [string]$ReviewedReference = '',
    [string]$NumericalOutput = ''
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$version = & .venv-desktop/Scripts/python.exe -c "import sys;sys.path.insert(0,'scripts');from desktop.model import APP_VERSION;print(APP_VERSION)"
if ($LASTEXITCODE -ne 0) { throw 'Could not read application version.' }
$desktopExe = Join-Path $PSScriptRoot "dist/OpenBirthChart-$version/OpenBirthChart.exe"
if (Get-Process OpenBirthChart -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $desktopExe }) {
    throw "Close the running $version application before rebuilding this version. Older versions may remain open."
}
& .venv-desktop/Scripts/python.exe scripts/build_help.py
if ($LASTEXITCODE -ne 0) { throw 'Help article build failed.' }
& .venv-desktop/Scripts/python.exe scripts/build_translations.py
if ($LASTEXITCODE -ne 0) { throw 'Translation validation failed.' }
& .venv-desktop/Scripts/python.exe -m unittest discover -s tests -p 'test_desktop*.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Desktop tests failed.' }
& .venv-desktop/Scripts/python.exe -m unittest discover -s tests -p 'test_house_number2.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Spatial house tests failed.' }
if ($ReviewedReference) {
    if (-not $NumericalOutput) {
        $NumericalOutput = Join-Path $PSScriptRoot ('results/numerical/package-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    }
    & .venv-desktop/Scripts/python.exe scripts/verify_release_numerics.py --reference $ReviewedReference --output $NumericalOutput
    if ($LASTEXITCODE -ne 0) { throw 'Exact comparison with the reviewed source results failed.' }
} else {
    & "$PSScriptRoot/verify-numerics.ps1"
}
& .venv-desktop/Scripts/python.exe -m PyInstaller --noconfirm EphemerisDesktop.spec
if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
& .venv-desktop/Scripts/python.exe scripts/finish_desktop_package.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop source/license inventory failed.' }
$checkOutput = Join-Path $PSScriptRoot ('results/desktop/build-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$check = Start-Process -FilePath $desktopExe -ArgumentList @('--smoke-output',('"' + $checkOutput + '"')) -WindowStyle Hidden -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Packaged app failed. See $checkOutput/error.log" }
Write-Output "Built dist/OpenBirthChart-$version/OpenBirthChart.exe. Distribute the entire folder."
