#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [switch]$KeepTempOnFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$templateRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
$agentteamsCmd = Join-Path -Path $templateRoot -ChildPath 'agentteams.cmd'
$atCmd = Join-Path -Path $templateRoot -ChildPath 'at.cmd'
$chatValidator = Join-Path -Path $templateRoot -ChildPath 'scripts/validate-chat-declaration.py'
$globalKickoff = '殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！'

if (-not (Test-Path -LiteralPath $agentteamsCmd -PathType Leaf)) {
  throw "missing command launcher: $agentteamsCmd"
}

if (-not (Test-Path -LiteralPath $atCmd -PathType Leaf)) {
  throw "missing command launcher: $atCmd"
}

if (-not (Test-Path -LiteralPath $chatValidator -PathType Leaf)) {
  throw "missing chat validator script: $chatValidator"
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

function Invoke-Python {
  param(
    [Parameter(Mandatory = $true)][string]$ScriptPath,
    [string[]]$Arguments = @()
  )

  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $ScriptPath @Arguments
    return $LASTEXITCODE
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $ScriptPath @Arguments
    return $LASTEXITCODE
  }

  throw 'python runtime not found (python or py -3 required)'
}

function Invoke-PythonCapture {
  param(
    [Parameter(Mandatory = $true)][string]$ScriptPath,
    [string[]]$Arguments = @()
  )

  $output = @()
  $exitCode = 1
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    if (Get-Command python -ErrorAction SilentlyContinue) {
      $output = & python $ScriptPath @Arguments 2>&1
      $exitCode = $LASTEXITCODE
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
      $output = & py -3 $ScriptPath @Arguments 2>&1
      $exitCode = $LASTEXITCODE
    }
    else {
      throw 'python runtime not found (python or py -3 required)'
    }
  }
  finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }

  return [PSCustomObject]@{
    ExitCode = $exitCode
    Output = (($output | ForEach-Object { $_.ToString() }) -join "`n")
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

  Write-Host '[1/10] doctor outside git repo'
  $nonRepoPath = Join-Path -Path $tempRoot -ChildPath 'non-repo'
  [System.IO.Directory]::CreateDirectory($nonRepoPath) | Out-Null
  Push-Location $nonRepoPath
  try {
    $doctorOutsideOutput = & $agentteamsCmd doctor 2>&1
    $doctorOutsideExit = $LASTEXITCODE
    $doctorOutsideText = $doctorOutsideOutput -join "`n"
    Assert-Condition -Condition ($doctorOutsideExit -ne 0) -Message 'agentteams doctor outside git repo unexpectedly succeeded'
    Assert-Condition -Condition ($doctorOutsideText.Contains('AGENT_CONTEXT_MISSING')) -Message 'AGENT_CONTEXT_MISSING not found for doctor outside git repo'
    Assert-Condition -Condition ($doctorOutsideText.Contains('Next: agentteams init')) -Message 'doctor outside git repo did not provide Next: agentteams init'
  }
  finally {
    Pop-Location
  }

  Write-Host '[2/10] init without positional repo (stdin input)'
  $remoteRepo | & $agentteamsCmd init -w $workspacePrompt --verbose
  if ($LASTEXITCODE -ne 0) { throw 'agentteams init failed for stdin repository input' }
  $targetPromptRepo = Join-Path -Path $workspacePrompt -ChildPath 'sample-app'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetPromptRepo 'AGENTS.md') -PathType Leaf) -Message 'AGENTS.md missing after stdin init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetPromptRepo 'logs/e2e-ai-log.md') -PathType Leaf) -Message 'logs/e2e-ai-log.md missing after stdin init'

  Write-Host '[3/10] new clone install'
  & $agentteamsCmd init $remoteRepo -w $workspace --verbose
  if ($LASTEXITCODE -ne 0) { throw 'agentteams init failed for clone mode' }

  $targetRepo = Join-Path -Path $workspace -ChildPath 'sample-app'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo 'AGENTS.md') -PathType Leaf) -Message 'AGENTS.md missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo '.codex/AGENTS.md') -PathType Leaf) -Message '.codex/AGENTS.md missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo 'agentteams.cmd') -PathType Leaf) -Message 'agentteams.cmd missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo 'agentteams.ps1') -PathType Leaf) -Message 'agentteams.ps1 missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo '.github/workflows/agentteams-validate.yml') -PathType Leaf) -Message 'workflow missing after clone init'
  Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $targetRepo 'logs/e2e-ai-log.md') -PathType Leaf) -Message 'logs/e2e-ai-log.md missing after clone init'
  $chatLogText = [System.IO.File]::ReadAllText((Join-Path $targetRepo 'logs/e2e-ai-log.md'), [System.Text.Encoding]::UTF8)
  Assert-Condition -Condition ($chatLogText.Contains($globalKickoff)) -Message 'chat log template missing global kickoff declaration'
  Assert-Condition -Condition ($chatLogText.Contains('固定開始宣言 -> 稼働口上 -> DECLARATION')) -Message 'chat log template missing 3-line contract marker'

  Write-Host '[4/10] doctor in installed repo'
  Push-Location $targetRepo
  try {
    $doctorInstalledOutput = & $agentteamsCmd doctor 2>&1
    $doctorInstalledExit = $LASTEXITCODE
    Assert-Condition -Condition ($doctorInstalledExit -eq 0) -Message 'agentteams doctor failed in installed repo'
    $doctorInstalledText = $doctorInstalledOutput -join "`n"
    Assert-Condition -Condition ($doctorInstalledText.Contains('AGENT_CONTEXT_OK')) -Message 'doctor output missing AGENT_CONTEXT_OK'
    Assert-Condition -Condition ($doctorInstalledText.Contains('CODEX_RULES_OK')) -Message 'doctor output missing CODEX_RULES_OK'
  }
  finally {
    Pop-Location
  }

  Write-Host '[5/10] default --here mode with coexist policy'
  $inplaceRepo = New-StandaloneRepo -BaseDir $tempRoot -Name 'inplace-coexist'
  Push-Location $inplaceRepo
  try {
    & $agentteamsCmd init --agents-policy coexist --verbose
    if ($LASTEXITCODE -ne 0) { throw 'agentteams init (default here mode) failed' }

    $agentsPath = Join-Path $inplaceRepo 'AGENTS.md'
    $localAgentsPath = Join-Path $inplaceRepo '.codex/AGENTS.local.md'
    $agentsText = [System.IO.File]::ReadAllText($agentsPath, [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($agentsText.Contains('AGENTTEAMS_MANAGED:ENTRY v1')) -Message 'managed marker missing after coexist policy'
    Assert-Condition -Condition (Test-Path -LiteralPath $localAgentsPath -PathType Leaf) -Message '.codex/AGENTS.local.md missing after coexist policy'
    Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $inplaceRepo 'logs/e2e-ai-log.md') -PathType Leaf) -Message 'logs/e2e-ai-log.md missing after default here mode'
  }
  finally {
    Pop-Location
  }

  Write-Host '[6/10] idempotency + collision + policy branch checks'
  Push-Location $inplaceRepo
  try {
    $statusBefore = (& git status --porcelain) -join "`n"
    & $agentteamsCmd init --agents-policy coexist
    if ($LASTEXITCODE -ne 0) { throw 'second agentteams init failed' }
    $statusAfter = (& git status --porcelain) -join "`n"
    Assert-Condition -Condition ($statusBefore -ceq $statusAfter) -Message 'git status changed after second run (idempotency failed)'
  }
  finally {
    Pop-Location
  }

  $collisionOutput = & $agentteamsCmd init $remoteRepo -w $workspace 2>&1
  $collisionExit = $LASTEXITCODE
  Assert-Condition -Condition ($collisionExit -ne 0) -Message 'collision case unexpectedly succeeded'
  Assert-Condition -Condition (($collisionOutput -join "`n").Contains('PATH_LAYOUT_INVALID')) -Message 'collision error code PATH_LAYOUT_INVALID not found'

  $keepRepo = New-StandaloneRepo -BaseDir $tempRoot -Name 'policy-keep'
  Push-Location $keepRepo
  try {
    $legacyKeep = [System.IO.File]::ReadAllText((Join-Path $keepRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    & $agentteamsCmd init --here --agents-policy keep
    if ($LASTEXITCODE -ne 0) { throw 'keep policy failed' }
    $afterKeep = [System.IO.File]::ReadAllText((Join-Path $keepRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($legacyKeep -ceq $afterKeep) -Message 'keep policy modified AGENTS.md'
    Assert-Condition -Condition (-not (Test-Path -LiteralPath (Join-Path $keepRepo '.codex/AGENTS.local.md') -PathType Leaf)) -Message 'keep policy should not create .codex/AGENTS.local.md'
    Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $keepRepo 'logs/e2e-ai-log.md') -PathType Leaf) -Message 'keep policy should still create logs/e2e-ai-log.md'
  }
  finally {
    Pop-Location
  }

  $replaceRepo = New-StandaloneRepo -BaseDir $tempRoot -Name 'policy-replace'
  Push-Location $replaceRepo
  try {
    $legacyReplace = [System.IO.File]::ReadAllText((Join-Path $replaceRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    & $agentteamsCmd init --here --agents-policy replace
    if ($LASTEXITCODE -ne 0) { throw 'replace policy failed' }
    $replaceText = [System.IO.File]::ReadAllText((Join-Path $replaceRepo 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($replaceText.Contains('AGENTTEAMS_MANAGED:ENTRY v1')) -Message 'replace policy did not write managed AGENTS.md'
    $localReplacePath = Join-Path $replaceRepo '.codex/AGENTS.local.md'
    Assert-Condition -Condition (Test-Path -LiteralPath $localReplacePath -PathType Leaf) -Message 'replace policy did not create .codex/AGENTS.local.md'
    $localReplaceText = [System.IO.File]::ReadAllText($localReplacePath, [System.Text.Encoding]::UTF8)
    Assert-Condition -Condition ($localReplaceText -ceq $legacyReplace) -Message 'replace policy backup content mismatch'
    Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $replaceRepo 'logs/e2e-ai-log.md') -PathType Leaf) -Message 'replace policy should create logs/e2e-ai-log.md'
  }
  finally {
    Pop-Location
  }

  Write-Host '[7/10] nested layout e2e (AgentTeams/<product>)'
  $nestedRoot = Join-Path -Path $tempRoot -ChildPath 'AgentTeams'
  $nestedProduct = Join-Path -Path $nestedRoot -ChildPath 'eye-texture-converter'
  [System.IO.Directory]::CreateDirectory($nestedProduct) | Out-Null
  Push-Location $nestedProduct
  try {
    & git init | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git init failed for nested product repo' }
    [System.IO.File]::WriteAllText((Join-Path $nestedProduct 'README.md'), "# nested`n", [System.Text.UTF8Encoding]::new($false))
    & git add . | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git add failed for nested product repo' }
    & git -c user.name='at-e2e' -c user.email='at-e2e@example.invalid' commit -m 'seed' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed for nested product repo' }

    & $agentteamsCmd init
    if ($LASTEXITCODE -ne 0) { throw 'agentteams init failed in nested layout product repo' }

    Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $nestedProduct 'AGENTS.md') -PathType Leaf) -Message 'nested layout missing AGENTS.md after at init'
    Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $nestedProduct '.codex/AGENTS.md') -PathType Leaf) -Message 'nested layout missing .codex/AGENTS.md after at init'
    Assert-Condition -Condition (Test-Path -LiteralPath (Join-Path $nestedProduct 'logs/e2e-ai-log.md') -PathType Leaf) -Message 'nested layout missing logs/e2e-ai-log.md after at init'
  }
  finally {
    Pop-Location
  }

  Write-Host '[8/10] template root init skip-bootstrap regression'
  Push-Location $templateRoot
  try {
    $templateStatusBefore = (& git status --porcelain) -join "`n"
    & $agentteamsCmd init --verbose
    if ($LASTEXITCODE -ne 0) { throw 'agentteams init failed in template root' }
    $templateStatusAfter = (& git status --porcelain) -join "`n"
    Assert-Condition -Condition ($templateStatusBefore -ceq $templateStatusAfter) -Message 'template root init changed git status'
  }
  finally {
    Pop-Location
  }

  Write-Host '[9/10] at.cmd compatibility check'
  Push-Location $inplaceRepo
  try {
    $compatStatusBefore = (& git status --porcelain) -join "`n"
    & $atCmd init --here --agents-policy coexist
    if ($LASTEXITCODE -ne 0) { throw 'at.cmd compatibility init failed' }
    $compatStatusAfter = (& git status --porcelain) -join "`n"
    Assert-Condition -Condition ($compatStatusBefore -ceq $compatStatusAfter) -Message 'at.cmd compatibility init changed git status'
  }
  finally {
    Pop-Location
  }

  Write-Host '[10/10] chat declaration validator success/failure'
  Push-Location $targetRepo
  try {
    $validateOk = Invoke-PythonCapture -ScriptPath $chatValidator
    Assert-Condition -Condition ($validateOk.ExitCode -eq 0) -Message "chat validator failed unexpectedly: $($validateOk.Output)"

    $koujoTag = ([char[]](0x3010, 0x7A3C, 0x50CD, 0x53E3, 0x4E0A, 0x3011) -join '')

    $badMissingKickoff = Join-Path $targetRepo 'logs/bad-missing-kickoff.md'
    $badMissingKickoffContent = @(
      '# E2E AI Log (v2.8)',
      '',
      '- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化',
      '',
      '## Entries',
      "- 2026-01-01T00:00:00Z $koujoTag protocol bootstrap message",
      '- 2026-01-01T00:00:01Z DECLARATION team=coordinator role=coordinator task=N/A action=bootstrap_verification',
      '- 2026-01-01T00:00:02Z Ran git status -sb'
    ) -join "`n"
    [System.IO.File]::WriteAllText(
      $badMissingKickoff,
      "$badMissingKickoffContent`n",
      [System.Text.UTF8Encoding]::new($false)
    )

    $validateMissingKickoff = Invoke-PythonCapture -ScriptPath $chatValidator -Arguments @('--log', $badMissingKickoff)
    Assert-Condition -Condition ($validateMissingKickoff.ExitCode -ne 0) -Message 'chat validator unexpectedly passed missing kickoff case'
    Assert-Condition -Condition ($validateMissingKickoff.Output.Contains('CHAT_GLOBAL_KICKOFF_MISSING')) -Message 'missing kickoff case did not report CHAT_GLOBAL_KICKOFF_MISSING'

    $badFormatKickoff = Join-Path $targetRepo 'logs/bad-format-kickoff.md'
    $badFormatKickoffContent = @(
      '# E2E AI Log (v2.8)',
      '',
      '- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化',
      '',
      '## Entries',
      '- 2026-01-01T00:00:00Z 殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。--家臣たちが動きます！',
      "- 2026-01-01T00:00:01Z $koujoTag protocol bootstrap message",
      '- 2026-01-01T00:00:02Z DECLARATION team=coordinator role=coordinator task=N/A action=bootstrap_verification'
    ) -join "`n"
    [System.IO.File]::WriteAllText(
      $badFormatKickoff,
      "$badFormatKickoffContent`n",
      [System.Text.UTF8Encoding]::new($false)
    )

    $validateFormatKickoff = Invoke-PythonCapture -ScriptPath $chatValidator -Arguments @('--log', $badFormatKickoff)
    Assert-Condition -Condition ($validateFormatKickoff.ExitCode -ne 0) -Message 'chat validator unexpectedly passed invalid kickoff format case'
    Assert-Condition -Condition ($validateFormatKickoff.Output.Contains('CHAT_GLOBAL_KICKOFF_FORMAT_INVALID')) -Message 'invalid kickoff format case did not report CHAT_GLOBAL_KICKOFF_FORMAT_INVALID'

    $badOrder = Join-Path $targetRepo 'logs/bad-order.md'
    $badOrderContent = @(
      '# E2E AI Log (v2.8)',
      '',
      '- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化',
      '',
      '## Entries',
      "- 2026-01-01T00:00:00Z $globalKickoff",
      '- 2026-01-01T00:00:01Z DECLARATION team=coordinator role=coordinator task=N/A action=bootstrap_verification',
      "- 2026-01-01T00:00:02Z $koujoTag protocol bootstrap message"
    ) -join "`n"
    [System.IO.File]::WriteAllText(
      $badOrder,
      "$badOrderContent`n",
      [System.Text.UTF8Encoding]::new($false)
    )

    $validateOrder = Invoke-PythonCapture -ScriptPath $chatValidator -Arguments @('--log', $badOrder)
    Assert-Condition -Condition ($validateOrder.ExitCode -ne 0) -Message 'chat validator unexpectedly passed order violation case'
    Assert-Condition -Condition ($validateOrder.Output.Contains('CHAT_KOUJO_MISSING')) -Message 'order violation case did not report CHAT_KOUJO_MISSING'
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
