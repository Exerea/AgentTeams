#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$Message = 'chore(agentteams): self-update by coordinator',
  [string]$Remote = 'origin',
  [string]$Branch = '',
  [switch]$SkipValidate,
  [switch]$NoPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
Push-Location $repoRoot

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)][string[]]$Args,
    [switch]$AllowFailure
  )

  & git @Args
  $exitCode = $LASTEXITCODE
  if (-not $AllowFailure -and $exitCode -ne 0) {
    throw "git command failed: git $($Args -join ' ')"
  }
  return $exitCode
}

try {
  Invoke-Git -Args @('rev-parse', '--is-inside-work-tree') | Out-Null

  if ([string]::IsNullOrWhiteSpace($Branch)) {
    $Branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'failed to detect current branch' }
  }

  if ($Branch -eq 'HEAD') {
    throw 'detached HEAD is not allowed for self-update. checkout a branch first.'
  }

  Invoke-Git -Args @('remote', 'get-url', $Remote) | Out-Null

  if (-not $SkipValidate) {
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
    if ($LASTEXITCODE -ne 0) {
      throw 'validate-repo.ps1 failed; aborting self-update.'
    }
  }

  Invoke-Git -Args @('add', '-A') | Out-Null

  Invoke-Git -Args @('diff', '--cached', '--quiet') -AllowFailure | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host 'No staged changes detected. Nothing to commit.'
    exit 0
  }

  Invoke-Git -Args @('commit', '-m', $Message) | Out-Null
  Write-Host "Committed with message: $Message"

  if ($NoPush) {
    Write-Host 'NoPush specified. Commit created locally only.'
    exit 0
  }

  Invoke-Git -Args @('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}') -AllowFailure | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Invoke-Git -Args @('push', '-u', $Remote, $Branch) | Out-Null
  }
  else {
    Invoke-Git -Args @('push', $Remote, $Branch) | Out-Null
  }

  Write-Host "Pushed to $Remote/$Branch"
  exit 0
}
catch {
  Write-Error $_
  exit 1
}
finally {
  Pop-Location
}
