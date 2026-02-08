#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [switch]$KeepTempOnFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$templateRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
$atCmd = Join-Path -Path $templateRoot -ChildPath 'at.cmd'

if (-not (Test-Path -LiteralPath $atCmd -PathType Leaf)) {
  throw "missing command launcher: $atCmd"
}

function Assert-Condition {
  param(
    [Parameter(Mandatory = $true)][bool]$Condition,
    [Parameter(Mandatory = $true)][string]$Message
  )
  if (-not $Condition) {
    throw $Message
  }
}

function New-LocalRemoteRepo {
  param(
    [Parameter(Mandatory = $true)][string]$BaseDir,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $seedRepo = Join-Path -Path $BaseDir -ChildPath "${Name}-seed"
  $bareRepo = Join-Path -Path $BaseDir -ChildPath "${Name}.git"
  [System.IO.Directory]::CreateDirectory($seedRepo) | Out-Null

  Push-Location $seedRepo
  try {
    & git init | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git init failed for seed repo' }

    [System.IO.File]::WriteAllText((Join-Path $seedRepo 'README.md'), "# $Name`n", [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText((Join-Path $seedRepo 'AGENTS.md'), "# Existing AGENTS for $Name`n", [System.Text.UTF8Encoding]::new($false))
    & git add . | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git add failed for seed repo' }
    & git -c user.name='at-e2e' -c user.email='at-e2e@example.invalid' commit -m 'seed' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed for seed repo' }
  }
  finally {
    Pop-Location
  }

  & git clone --bare $seedRepo $bareRepo | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'git clone --bare failed' }
  return $bareRepo
}

function New-StandaloneRepo {
  param(
    [Parameter(Mandatory = $true)][string]$BaseDir,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $repoPath = Join-Path -Path $BaseDir -ChildPath $Name
  [System.IO.Directory]::CreateDirectory($repoPath) | Out-Null

  Push-Location $repoPath
  try {
    & git init | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git init failed for $repoPath" }
    [System.IO.File]::WriteAllText((Join-Path $repoPath 'AGENTS.md'), "# Legacy AGENTS ($Name)`n", [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText((Join-Path $repoPath 'README.md'), "# $Name`n", [System.Text.UTF8Encoding]::new($false))
    & git add . | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git add failed for $repoPath" }
    & git -c user.name='at-e2e' -c user.email='at-e2e@example.invalid' commit -m 'seed' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git commit failed for $repoPath" }
  }
  finally {
    Pop-Location
  }

  return $repoPath
}

$timestamp = Get-Date -Format 'yyyyMMddHHmmss'
$tempRoot = Join-Path -Path $env:TEMP -ChildPath "agentteams-e2e-$timestamp-$([System.Guid]::NewGuid().ToString('N').Substring(0,8))"

[System.IO.Directory]::CreateDirectory($tempRoot) | Out-Null
Write-Host "E2E temp root: $tempRoot"

$cleanup = $true

try {
  $remoteRepo = New-LocalRemoteRepo -BaseDir $tempRoot -Name 'sample-app'
  $workspacePrompt = Join-Path -Path $tempRoot -ChildPath 'workspace-prompt'
  $workspace = Join-Path -Path $tempRoot -ChildPath 'workspace'

  Write-Host '[1/6] init without positional repo (stdin input)'
  $remoteRepo | & $atCmd init -w $workspacePrompt --verbose
  if ($LASTEXITCODE -ne 0) { throw 'at init failed for stdin repository input' }
  $targetPromptRepo = Join-Path -Path $workspacePrompt -ChildPath 'sample-app'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetPromptRepo 'AGENTS.md') -PathType Leaf) -Message 'AGENTS.md missing after stdin init'

  Write-Host '[2/6] new clone install'
  & $atCmd init $remoteRepo -w $workspace --verbose
  if ($LASTEXITCODE -ne 0) { throw 'at init failed for clone mode' }

  $targetRepo = Join-Path -Path $workspace -ChildPath 'sample-app'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo 'AGENTS.md') -PathType Leaf) -Message 'AGENTS.md missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo '.codex/AGENTS.md') -PathType Leaf) -Message '.codex/AGENTS.md missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo '.github/workflows/agentteams-validate.yml') -PathType Leaf) -Message 'workflow missing after clone init'

  Write-Host '[3/6] --here with coexist policy'
  $inplaceRepo = New-StandaloneRepo -BaseDir $tempRoot -Name 'inplace-coexist'
  Push-Location $inplaceRepo
  try {
    & $atCmd init --here --agents-policy coexist --verbose
    if ($LASTEXITCODE -ne 0) { throw 'at init --here (coexist) failed' }

    $agentsPath = Join-Path $inplaceRepo 'AGENTS.md'
    $localAgentsPath = Join-Path $inplaceRepo '.codex/AGENTS.local.md'
    $agentsText = [System.IO.File]::ReadAllText($agentsPath, [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($agentsText.Contains('AGENTTEAMS_MANAGED:ENTRY v1')) -Message 'managed marker missing after coexist policy'
    Assert-Condition -Condition (Test-Path -LiteralPath $localAgentsPath -PathType Leaf) -Message '.codex/AGENTS.local.md missing after coexist policy'
  }
  finally {
    Pop-Location
  }

  Write-Host '[4/6] idempotency check'
  Push-Location $inplaceRepo
  try {
    $statusBefore = (& git status --porcelain) -join "`n"
    & $atCmd init --here --agents-policy coexist
    if ($LASTEXITCODE -ne 0) { throw 'second at init --here failed' }
    $statusAfter = (& git status --porcelain) -join "`n"
    Assert-Condition -Condition ($statusBefore -ceq $statusAfter) -Message 'git status changed after second run (idempotency failed)'
  }
  finally {
    Pop-Location
  }

  Write-Host '[5/6] collision safety check'
  $collisionOutput = & $atCmd init $remoteRepo -w $workspace 2>&1
  $collisionExit = $LASTEXITCODE
  Assert-Condition -Condition ($collisionExit -ne 0) -Message 'collision case unexpectedly succeeded'
  Assert-Condition -Condition (($collisionOutput -join "`n").Contains('PATH_LAYOUT_INVALID')) -Message 'collision error code PATH_LAYOUT_INVALID not found'

  Write-Host '[6/6] policy branch checks (keep/replace)'
  $keepRepo = New-StandaloneRepo -BaseDir $tempRoot -Name 'policy-keep'
  Push-Location $keepRepo
  try {
    $legacyKeep = [System.IO.File]::ReadAllText((Join-Path $keepRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    & $atCmd init --here --agents-policy keep
    if ($LASTEXITCODE -ne 0) { throw 'keep policy failed' }
    $afterKeep = [System.IO.File]::ReadAllText((Join-Path $keepRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($legacyKeep -ceq $afterKeep) -Message 'keep policy modified AGENTS.md'
    Assert-Condition -Condition (-not (Test-Path -LiteralPath (Join-Path $keepRepo '.codex/AGENTS.local.md') -PathType Leaf)) -Message 'keep policy should not create .codex/AGENTS.local.md'
  }
  finally {
    Pop-Location
  }

  $replaceRepo = New-StandaloneRepo -BaseDir $tempRoot -Name 'policy-replace'
  Push-Location $replaceRepo
  try {
    $legacyReplace = [System.IO.File]::ReadAllText((Join-Path $replaceRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    & $atCmd init --here --agents-policy replace
    if ($LASTEXITCODE -ne 0) { throw 'replace policy failed' }
    $replaceText = [System.IO.File]::ReadAllText((Join-Path $replaceRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($replaceText.Contains('AGENTTEAMS_MANAGED:ENTRY v1')) -Message 'replace policy did not write managed AGENTS.md'
    $localReplacePath = Join-Path $replaceRepo '.codex/AGENTS.local.md'
    Assert-Condition -Condition (Test-Path -LiteralPath $localReplacePath -PathType Leaf) -Message 'replace policy did not create .codex/AGENTS.local.md'
    $localReplaceText = [System.IO.File]::ReadAllText($localReplacePath, [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($localReplaceText -ceq $legacyReplace) -Message 'replace policy backup content mismatch'
  }
  finally {
    Pop-Location
  }

  Write-Host 'E2E result: PASS'
}
catch {
  $cleanup = -not $KeepTempOnFailure
  Write-Error $_
  throw
}
finally {
  if ($cleanup -and (Test-Path -LiteralPath $tempRoot)) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
    Write-Host "E2E cleanup: removed $tempRoot"
  }
  else {
    Write-Host "E2E cleanup skipped: $tempRoot"
  }
}
