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
    [string[]]$Arguments = @()
  )

  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $ScriptPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "python script failed: $ScriptPath" }
    return
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $ScriptPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "python script failed: $ScriptPath" }
    return
  }

  throw 'python runtime not found (python or py -3 required)'
}

try {
  Invoke-PythonScript -ScriptPath .\scripts\validate-takt-task.py -Arguments @('--path', '.takt/tasks')
  Invoke-PythonScript -ScriptPath .\scripts\validate-takt-evidence.py -Arguments @('--allow-empty-logs')
  Invoke-PythonScript -ScriptPath .\scripts\validate-doc-consistency.py
  Invoke-PythonScript -ScriptPath .\scripts\validate-scenarios-structure.py

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
