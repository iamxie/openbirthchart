# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.cache/uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.cache/python'
function Invoke-Uv {
    & uv @args
    if ($LASTEXITCODE -ne 0) { throw "uv failed: $args" }
}
Invoke-Uv venv --python 3.12 .venv-core
Invoke-Uv venv --python 3.11 .venv-reference
foreach ($name in @('core', 'reference')) {
    $python = ".venv-$name/Scripts/python.exe"
    $lock = "requirements/$name.lock"
    if (-not (Test-Path $lock)) {
        Invoke-Uv pip compile "requirements/$name.in" --python $python --generate-hashes --output-file $lock --quiet
    }
    Invoke-Uv pip sync --python $python --require-hashes $lock
}
