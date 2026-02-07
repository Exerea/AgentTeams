#!/usr/bin/env pwsh
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
Push-Location $repoRoot

try {
  if (-not (Get-Command gitleaks -ErrorAction SilentlyContinue)) {
    Write-Error 'gitleaks command was not found. Install gitleaks first.'
    exit 1
  }

  & gitleaks detect --source . --no-git --config .gitleaks.toml --redact
  if ($LASTEXITCODE -ne 0) {
    Write-Error 'secret scan failed'
    exit $LASTEXITCODE
  }

  Write-Host 'secret scan is valid'
  exit 0
}
catch {
  Write-Error $_
  exit 1
}
finally {
  Pop-Location
}
