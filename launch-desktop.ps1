# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
$ErrorActionPreference = 'Stop'
$desktopPython = Join-Path $PSScriptRoot '.venv-desktop/Scripts/pythonw.exe'
if (-not (Test-Path -LiteralPath $desktopPython)) { throw 'Run setup-desktop.ps1 first, or use the portable build.' }
Start-Process -FilePath $desktopPython -ArgumentList ('"' + (Join-Path $PSScriptRoot 'desktop_app.py') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
