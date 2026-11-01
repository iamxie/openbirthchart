# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv-desktop/Scripts/python.exe')) {
    uv venv .venv-desktop --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Could not create desktop environment.' }
}
uv pip sync requirements/desktop.lock --python .venv-desktop/Scripts/python.exe --require-hashes
if ($LASTEXITCODE -ne 0) { throw 'Desktop dependency installation failed.' }
& .venv-desktop/Scripts/python.exe scripts/prepare_runtime_data.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop data preparation failed.' }
Write-Output 'Ready. All pinned runtime data verified. Launch with launch-desktop.ps1.'
