#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path -Path $PSScriptRoot -ChildPath 'at.py'
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
  Write-Host "ERROR [PATH_LAYOUT_INVALID] missing script: $scriptPath"
  exit 1
}

if (Get-Command python -ErrorAction SilentlyContinue) {
  & python $scriptPath @args
  exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $scriptPath @args
  exit $LASTEXITCODE
}

Write-Host 'ERROR [PATH_LAYOUT_INVALID] python runtime not found (python or py -3 required).'
Write-Host 'Next: Install python, then retry: agentteams init <git-url>'
Write-Host 'Compat: .\at.cmd init <git-url>'
exit 1
