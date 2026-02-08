#!/usr/bin/env pwsh
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
Push-Location $repoRoot

function Invoke-PythonScript {
  param(
    [Parameter(Mandatory = $true)][string]$ScriptPath,
    [string[]]$Arguments = @(),
    [switch]$Quiet
  )

  if (Get-Command python -ErrorAction SilentlyContinue) {
    if ($Quiet) {
      & python $ScriptPath @Arguments *> $null
    }
    else {
      & python $ScriptPath @Arguments
    }
    if ($LASTEXITCODE -ne 0) { throw "python script failed: $ScriptPath" }
    return
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    if ($Quiet) {
      & py -3 $ScriptPath @Arguments *> $null
    }
    else {
      & py -3 $ScriptPath @Arguments
    }
    if ($LASTEXITCODE -ne 0) { throw "python script failed: $ScriptPath" }
    return
  }

  throw 'python runtime not found (python or py -3 required)'
}

try {
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-states-index.ps1 -Path .\.codex\states\_index.yaml
  if ($LASTEXITCODE -ne 0) { throw 'validate-states-index.ps1 failed' }

  Get-ChildItem .\.codex\states\TASK-*.yaml | ForEach-Object {
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "validate-task-state.ps1 failed for $($_.Name)" }
  }

  Invoke-PythonScript -ScriptPath .\scripts\validate-doc-consistency.py
  Invoke-PythonScript -ScriptPath .\scripts\validate-self-update-evidence.py -Arguments @('--help') -Quiet
  Invoke-PythonScript -ScriptPath .\scripts\validate-scenarios-structure.py
  Invoke-PythonScript -ScriptPath .\scripts\validate-rule-examples-coverage.py
  Invoke-PythonScript -ScriptPath .\scripts\detect-role-gaps.py
  Invoke-PythonScript -ScriptPath .\scripts\validate-role-gap-review.py
  Invoke-PythonScript -ScriptPath .\scripts\validate-deprecated-assets.py
  Invoke-PythonScript -ScriptPath .\scripts\validate-chat-declaration.py

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-secrets.ps1
  if ($LASTEXITCODE -ne 0) { throw 'validate-secrets.ps1 failed' }

  Write-Host 'repository validation passed'
  exit 0
}
catch {
  Write-Error $_
  exit 1
}
finally {
  Pop-Location
}
