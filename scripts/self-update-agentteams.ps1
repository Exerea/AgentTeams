#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Message = 'chore(agentteams): self-update by coordinator'
$Remote = 'origin'
$Branch = ''
$TaskFile = ''
$NoPush = $false

function Show-Usage {
  Write-Host 'Usage: self-update-agentteams.ps1 -TaskFile <path> [-Message <msg>] [-Remote <name>] [-Branch <name>] [-NoPush]'
}

function Fail {
  param(
    [Parameter(Mandatory = $true)][string]$Code,
    [Parameter(Mandatory = $true)][string]$MessageText,
    [string]$NextCommand = ''
  )

  Write-Host "ERROR [$Code] $MessageText"
  if (-not [string]::IsNullOrWhiteSpace($NextCommand)) {
    Write-Host "Next: $NextCommand"
  }
  exit 1
}

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

function Invoke-Python {
  param(
    [Parameter(Mandatory = $true)][string[]]$Args
  )

  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python @Args | Out-Host
    return [int]$LASTEXITCODE
  }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @Args | Out-Host
    return [int]$LASTEXITCODE
  }
  Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText 'python runtime not found (python or py -3 required)'
  return 1
}

if ($args.Count -eq 0) {
  Show-Usage
}

$idx = 0
while ($idx -lt $args.Count) {
  $token = $args[$idx]
  switch ($token) {
    '-TaskFile' { 
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_REQUIRED' -MessageText '-TaskFile requires a value' -NextCommand 'powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-xxxxx-your-task.yaml -NoPush'
      }
      $TaskFile = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '--task-file' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_REQUIRED' -MessageText '--task-file requires a value' -NextCommand 'powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-xxxxx-your-task.yaml -NoPush'
      }
      $TaskFile = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '-Message' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '-Message requires a value'
      }
      $Message = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '--message' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '--message requires a value'
      }
      $Message = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '-Remote' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '-Remote requires a value'
      }
      $Remote = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '--remote' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '--remote requires a value'
      }
      $Remote = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '-Branch' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '-Branch requires a value'
      }
      $Branch = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '--branch' {
      if ($idx + 1 -ge $args.Count) {
        Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '--branch requires a value'
      }
      $Branch = [string]$args[$idx + 1]
      $idx += 2
      continue
    }
    '-NoPush' {
      $NoPush = $true
      $idx += 1
      continue
    }
    '--no-push' {
      $NoPush = $true
      $idx += 1
      continue
    }
    '-SkipValidate' {
      Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '-SkipValidate is removed. self-update always runs validation.' -NextCommand 'powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-xxxxx-your-task.yaml -NoPush'
    }
    '--skip-validate' {
      Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText '--skip-validate is removed. self-update always runs validation.' -NextCommand 'powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-xxxxx-your-task.yaml -NoPush'
    }
    '-h' {
      Show-Usage
      exit 0
    }
    '--help' {
      Show-Usage
      exit 0
    }
    default {
      Show-Usage
      Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText "unknown argument: $token"
    }
  }
}

if ([string]::IsNullOrWhiteSpace($TaskFile)) {
  Show-Usage
  Fail -Code 'SELF_UPDATE_TASK_REQUIRED' -MessageText '-TaskFile is required' -NextCommand 'powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-xxxxx-your-task.yaml -NoPush'
}

if (-not (Test-Path -LiteralPath $TaskFile -PathType Leaf)) {
  Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText "task file not found: $TaskFile"
}

$taskFileLeaf = Split-Path -Leaf $TaskFile
if ($taskFileLeaf -notmatch '^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$') {
  Fail -Code 'SELF_UPDATE_TASK_PATH_INVALID' -MessageText "task file name must follow TASK-xxxxx-slug.yaml: $taskFileLeaf"
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
Push-Location $repoRoot

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

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
  if ($LASTEXITCODE -ne 0) {
    throw 'validate-repo.ps1 failed; aborting self-update.'
  }

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path $TaskFile
  if ($LASTEXITCODE -ne 0) {
    throw "validate-task-state.ps1 failed for task: $TaskFile"
  }

  Invoke-Git -Args @('add', '-A') | Out-Null

  Invoke-Git -Args @('diff', '--cached', '--quiet') -AllowFailure | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host 'No staged changes detected. Nothing to commit.'
    exit 0
  }

  $evidenceExit = Invoke-Python -Args @('.\scripts\validate-self-update-evidence.py', '--task-file', $TaskFile, '--log', 'logs/e2e-ai-log.md')
  if ($evidenceExit -ne 0) {
    throw 'validate-self-update-evidence.py failed; aborting self-update.'
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
