# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$sourcePath = Join-Path $PSScriptRoot 'vendor/libephemeris'
$expectedCommit = '7c77b70717cf8420b85c19d3aaad128060998007'
function Invoke-SourceGit {
    & git -c "safe.directory=$($sourcePath.Replace('\','/'))" -C $sourcePath @args
    if ($LASTEXITCODE -ne 0) { throw "Source Git command failed: $args" }
}
if (-not (Test-Path -LiteralPath $sourcePath)) {
    New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'vendor') | Out-Null
    & git clone --depth 1 --branch v3.2.2 --filter=blob:none --no-checkout https://github.com/g-battaglia/libephemeris.git $sourcePath
    if ($LASTEXITCODE -ne 0) { throw 'Source clone failed' }
    Invoke-SourceGit sparse-checkout set libephemeris scripts docs
    Invoke-SourceGit checkout
}
$actualCommit = Invoke-SourceGit rev-parse HEAD
if ($actualCommit -ne $expectedCommit) { throw "Unexpected source commit: $actualCommit" }
Write-Output "Verified LibEphemeris source: $actualCommit"
