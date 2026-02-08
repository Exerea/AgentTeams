#!/usr/bin/env pwsh

$scriptPath = Join-Path -Path $PSScriptRoot -ChildPath 'scripts/at.ps1'
if ($args.Count -eq 0) {
  & $scriptPath
  exit $LASTEXITCODE
}

$forwardArgs = @($args | Where-Object { $_ -ne $null })
& $scriptPath @forwardArgs
exit $LASTEXITCODE
