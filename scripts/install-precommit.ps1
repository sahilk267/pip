# Installs git pre-commit hooks using a repo-local PRE_COMMIT_HOME (Windows-friendly).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cache = Join-Path $root ".cache\pre-commit"
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$env:PRE_COMMIT_HOME = $cache
Set-Location $root
pre-commit install
Write-Host "pre-commit installed. PRE_COMMIT_HOME=$cache"
