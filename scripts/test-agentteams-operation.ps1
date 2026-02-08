#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$ProductRepoUrl = 'https://github.com/Exerea/eye-texture-converter.git',
  [switch]$UseFixtureRepo,
  [int]$MinTeams = 3,
  [int]$MinRoles = 5,
  [switch]$KeepTempOnFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$templateRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
$agentteamsCmd = Join-Path -Path $templateRoot -ChildPath 'agentteams.cmd'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

if (-not (Test-Path -LiteralPath $agentteamsCmd -PathType Leaf)) {
  throw "missing command launcher: $agentteamsCmd"
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

function Get-UtcIso {
  return [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
}

function Get-RepoNameFromUrl {
  param([Parameter(Mandatory = $true)][string]$RepoUrl)
  $trimmed = $RepoUrl.Trim().TrimEnd('/', '\')
  if (-not $trimmed) { return '' }
  $leaf = ($trimmed -replace '\\', '/') -split '/' | Select-Object -Last 1
  if ($leaf.EndsWith('.git')) {
    return $leaf.Substring(0, $leaf.Length - 4)
  }
  return $leaf
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

function Invoke-TaskValidatorCapture {
  param(
    [Parameter(Mandatory = $true)][string]$TaskValidatorPath,
    [Parameter(Mandatory = $true)][string]$TaskPath
  )

  $output = @()
  $exitCode = 1
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $TaskValidatorPath -Path $TaskPath 2>&1
    $exitCode = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }

  return [PSCustomObject]@{
    ExitCode = $exitCode
    Output = (($output | ForEach-Object { $_.ToString() }) -join "`n")
  }
}

function Invoke-AgentTeamsCapture {
  param(
    [Parameter(Mandatory = $true)][string[]]$Arguments
  )

  $output = @()
  $exitCode = 1
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $output = & $agentteamsCmd @Arguments 2>&1
    $exitCode = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }

  return [PSCustomObject]@{
    ExitCode = $exitCode
    Output = (($output | ForEach-Object { $_.ToString() }) -join "`n")
  }
}

function Write-Utf8File {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Content
  )

  [System.IO.Directory]::CreateDirectory((Split-Path -Path $Path -Parent)) | Out-Null
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function New-FixtureRemoteRepo {
  param(
    [Parameter(Mandatory = $true)][string]$BaseDir
  )

  $seedRepo = Join-Path -Path $BaseDir -ChildPath 'operation-fixture-seed'
  $bareRepo = Join-Path -Path $BaseDir -ChildPath 'operation-fixture.git'
  [System.IO.Directory]::CreateDirectory($seedRepo) | Out-Null

  Push-Location $seedRepo
  try {
    & git init | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git init failed for fixture seed repo' }

    Write-Utf8File -Path (Join-Path $seedRepo 'README.md') -Content "# operation fixture`n"
    Write-Utf8File -Path (Join-Path $seedRepo 'docs/adr/0001-operation-smoke.md') -Content "# ADR 0001`n"

    & git add . | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git add failed for fixture seed repo' }
    & git -c user.name='at-op-e2e' -c user.email='at-op-e2e@example.invalid' commit -m 'seed fixture' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed for fixture seed repo' }
  }
  finally {
    Pop-Location
  }

  & git clone --bare $seedRepo $bareRepo | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'git clone --bare failed for fixture repo' }
  return $bareRepo
}

function Build-SmokeTaskYaml {
  param(
    [Parameter(Mandatory = $true)][string]$TaskId,
    [Parameter(Mandatory = $true)][string]$Timestamp
  )

  return @"
id: $TaskId
title: operation smoke evidence
owner: coordinator
assignee: qa-review-guild/code-critic
status: in_review
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
depends_on: []
adr_refs: []
local_flags:
  major_decision_required: false
  documentation_sync_required: false
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: false
  ux_review_required: false
warnings: []
handoffs:
  - from: coordinator/coordinator
    to: frontend/ui-designer
    at: $Timestamp
    memo: DECLARATION team=coordinator role=coordinator task=$TaskId action=handoff_to_ui_designer | smoke kickoff
  - from: frontend/ui-designer
    to: frontend/ux-specialist
    at: $Timestamp
    memo: DECLARATION team=frontend role=ui-designer task=$TaskId action=handoff_to_ux_specialist | ux review requested
  - from: frontend/ux-specialist
    to: backend/api-architect
    at: $Timestamp
    memo: DECLARATION team=frontend role=ux-specialist task=$TaskId action=handoff_to_backend_api | api sync requested
  - from: backend/api-architect
    to: documentation-guild/tech-writer
    at: $Timestamp
    memo: DECLARATION team=backend role=api-architect task=$TaskId action=handoff_to_tech_writer | docs sync requested
  - from: documentation-guild/tech-writer
    to: qa-review-guild/code-critic
    at: $Timestamp
    memo: DECLARATION team=documentation-guild role=tech-writer task=$TaskId action=handoff_to_code_critic | qa review requested
notes: operation smoke evidence prepared
updated_at: $Timestamp
"@
}

function Build-LowDistributionTaskYaml {
  param(
    [Parameter(Mandatory = $true)][string]$TaskId,
    [Parameter(Mandatory = $true)][string]$Timestamp
  )

  return @"
id: $TaskId
title: operation low distribution
owner: coordinator
assignee: backend/api-architect
status: in_review
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
depends_on: []
adr_refs: []
local_flags:
  major_decision_required: false
  documentation_sync_required: false
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: false
  ux_review_required: false
warnings: []
handoffs:
  - from: coordinator/coordinator
    to: backend/api-architect
    at: $Timestamp
    memo: DECLARATION team=coordinator role=coordinator task=$TaskId action=handoff_to_backend_api | smoke
  - from: backend/api-architect
    to: qa-review-guild/code-critic
    at: $Timestamp
    memo: DECLARATION team=backend role=api-architect task=$TaskId action=handoff_to_code_critic | smoke
notes: low distribution sample
updated_at: $Timestamp
"@
}

function Build-BadDeclarationTaskYaml {
  param(
    [Parameter(Mandatory = $true)][string]$TaskId,
    [Parameter(Mandatory = $true)][string]$Timestamp
  )

  return @"
id: $TaskId
title: operation bad declaration
owner: coordinator
assignee: qa-review-guild/code-critic
status: in_review
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
depends_on: []
adr_refs: []
local_flags:
  major_decision_required: false
  documentation_sync_required: false
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: false
  ux_review_required: false
warnings: []
handoffs:
  - from: coordinator/coordinator
    to: frontend/ui-designer
    at: $Timestamp
    memo: handoff to ui designer
  - from: frontend/ui-designer
    to: qa-review-guild/code-critic
    at: $Timestamp
    memo: DECLARATION team=frontend role=ui-designer task=$TaskId action=handoff_to_code_critic | smoke
notes: invalid declaration sample
updated_at: $Timestamp
"@
}

if ($MinTeams -lt 1) { throw '-MinTeams must be >= 1' }
if ($MinRoles -lt 1) { throw '-MinRoles must be >= 1' }

$timestamp = Get-Date -Format 'yyyyMMddHHmmss'
$tempRoot = Join-Path -Path $env:TEMP -ChildPath "agentteams-operation-e2e-$timestamp-$([System.Guid]::NewGuid().ToString('N').Substring(0,8))"
[System.IO.Directory]::CreateDirectory($tempRoot) | Out-Null

Write-Host "Operation E2E temp root: $tempRoot"

$cleanup = $true
try {
  $repoSource = $ProductRepoUrl
  if ($UseFixtureRepo) {
    Write-Host '[setup] creating fixture remote repo'
    $repoSource = New-FixtureRemoteRepo -BaseDir $tempRoot
  }

  $workspace = Join-Path -Path $tempRoot -ChildPath 'workspace'
  [System.IO.Directory]::CreateDirectory($workspace) | Out-Null

  Write-Host '[1/5] init target repository'
  & $agentteamsCmd init $repoSource -w $workspace --verbose
  if ($LASTEXITCODE -ne 0) { throw "agentteams init failed: $repoSource" }

  $repoName = Get-RepoNameFromUrl -RepoUrl $repoSource
  Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($repoName)) -Message 'failed to resolve repository name'

  $targetRepo = Join-Path -Path $workspace -ChildPath $repoName
  Assert-Condition -Condition (Test-Path -LiteralPath $targetRepo -PathType Container) -Message "target repo missing: $targetRepo"

  $chatValidator = Join-Path -Path $targetRepo -ChildPath 'scripts/validate-chat-declaration.py'
  $guardUsageValidator = Join-Path -Path $targetRepo -ChildPath 'scripts/validate-chat-guard-usage.py'
  $operationValidator = Join-Path -Path $targetRepo -ChildPath 'scripts/validate-operation-evidence.py'
  $taskValidator = Join-Path -Path $targetRepo -ChildPath 'scripts/validate-task-state.ps1'

  Assert-Condition -Condition (Test-Path -LiteralPath $chatValidator -PathType Leaf) -Message "missing chat validator: $chatValidator"
  Assert-Condition -Condition (Test-Path -LiteralPath $guardUsageValidator -PathType Leaf) -Message "missing guard usage validator: $guardUsageValidator"
  Assert-Condition -Condition (Test-Path -LiteralPath $operationValidator -PathType Leaf) -Message "missing operation validator: $operationValidator"
  Assert-Condition -Condition (Test-Path -LiteralPath $taskValidator -PathType Leaf) -Message "missing task validator: $taskValidator"

  Push-Location $targetRepo
  try {
    Write-Host '[2/5] create smoke task and chat evidence'
    $now = Get-UtcIso
    $taskFileRel = '.codex/states/TASK-00999-operation-smoke.yaml'
    $taskFile = Join-Path -Path $targetRepo -ChildPath $taskFileRel
    Write-Utf8File -Path $taskFile -Content (Build-SmokeTaskYaml -TaskId 'T-999' -Timestamp $now)

    $logPath = Join-Path -Path $targetRepo -ChildPath 'logs/e2e-ai-log.md'
    Assert-Condition -Condition (Test-Path -LiteralPath $logPath -PathType Leaf) -Message "missing log: $logPath"
    $messageDir = Join-Path -Path $targetRepo -ChildPath '.codex/tmp'
    [System.IO.Directory]::CreateDirectory($messageDir) | Out-Null

    $taskStartMessage = Join-Path -Path $messageDir -ChildPath 'guard-task-start.txt'
    Write-Utf8File -Path $taskStartMessage -Content @'
殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！
【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「operation smoke evidence」を務めます。運用スモークテストを開始します。
DECLARATION team=coordinator role=coordinator task=T-999 action=operation_smoke_start
'@
    $taskStartSend = Invoke-AgentTeamsCapture -Arguments @(
      'guard-chat',
      '--event', 'task_start',
      '--team', 'coordinator',
      '--role', 'coordinator',
      '--task', 'T-999',
      '--task-title', 'operation smoke evidence',
      '--message-file', $taskStartMessage,
      '--task-file', $taskFileRel,
      '--log', 'logs/e2e-ai-log.md'
    )
    Assert-Condition -Condition ($taskStartSend.ExitCode -eq 0) -Message "guard-chat task_start failed`n$($taskStartSend.Output)"

    $readRulesMessage = Join-Path -Path $messageDir -ChildPath 'guard-read-rules.txt'
    Write-Utf8File -Path $readRulesMessage -Content @'
【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「AGENTS正本確認」を務めます。正本読取を記録します。
DECLARATION team=coordinator role=coordinator task=T-999 action=read_canonical_rules
実行 Get-Content -Path .codex/AGENTS.md -Encoding utf8
'@
    $readRulesSend = Invoke-AgentTeamsCapture -Arguments @(
      'guard-chat',
      '--event', 'gate',
      '--team', 'coordinator',
      '--role', 'coordinator',
      '--task', 'T-999',
      '--task-title', 'AGENTS正本確認',
      '--message-file', $readRulesMessage,
      '--task-file', $taskFileRel,
      '--log', 'logs/e2e-ai-log.md'
    )
    Assert-Condition -Condition ($readRulesSend.ExitCode -eq 0) -Message "guard-chat read rules failed`n$($readRulesSend.Output)"

    $readAdrMessage = Join-Path -Path $messageDir -ChildPath 'guard-read-adr.txt'
    Write-Utf8File -Path $readAdrMessage -Content @'
【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「ADR読取確認」を務めます。ADR読取を記録します。
DECLARATION team=coordinator role=coordinator task=T-999 action=read_adr_context
実行 Get-ChildItem -Path docs/adr/ -File
'@
    $readAdrSend = Invoke-AgentTeamsCapture -Arguments @(
      'guard-chat',
      '--event', 'gate',
      '--team', 'coordinator',
      '--role', 'coordinator',
      '--task', 'T-999',
      '--task-title', 'ADR読取確認',
      '--message-file', $readAdrMessage,
      '--task-file', $taskFileRel,
      '--log', 'logs/e2e-ai-log.md'
    )
    Assert-Condition -Condition ($readAdrSend.ExitCode -eq 0) -Message "guard-chat read adr failed`n$($readAdrSend.Output)"

    Write-Host '[3/5] positive validation checks'
    $chatOk = Invoke-PythonCapture -ScriptPath $chatValidator -Arguments @('--log', 'logs/e2e-ai-log.md')
    Assert-Condition -Condition ($chatOk.ExitCode -eq 0) -Message "validate-chat-declaration failed`n$($chatOk.Output)"

    $guardOk = Invoke-PythonCapture -ScriptPath $guardUsageValidator -Arguments @('--log', 'logs/e2e-ai-log.md')
    Assert-Condition -Condition ($guardOk.ExitCode -eq 0) -Message "validate-chat-guard-usage failed`n$($guardOk.Output)"

    $taskOk = Invoke-TaskValidatorCapture -TaskValidatorPath $taskValidator -TaskPath $taskFile
    Assert-Condition -Condition ($taskOk.ExitCode -eq 0) -Message "validate-task-state failed`n$($taskOk.Output)"

    $operationOk = Invoke-PythonCapture -ScriptPath $operationValidator -Arguments @(
      '--task-file', $taskFileRel,
      '--log', 'logs/e2e-ai-log.md',
      '--min-teams', "$MinTeams",
      '--min-roles', "$MinRoles"
    )
    Assert-Condition -Condition ($operationOk.ExitCode -eq 0) -Message "validate-operation-evidence failed`n$($operationOk.Output)"

    Write-Host '[4/5] negative validation checks'
    $badChatLog = Join-Path -Path $targetRepo -ChildPath 'logs/bad-chat-declaration.md'
    $badChatContent = @(
      '# E2E AI Log (v2.8)',
      '',
      '- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化',
      '',
      '## Entries',
      '- 2026-01-01T00:00:00Z 殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！',
      '- 2026-01-01T00:00:01Z DECLARATION team=coordinator role=coordinator task=T-999 action=bootstrap_verification',
      '- 2026-01-01T00:00:02Z 【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「順序違反テスト」を務めます。順序違反を確認します。'
    ) -join "`n"
    Write-Utf8File -Path $badChatLog -Content "$badChatContent`n"

    $badChatResult = Invoke-PythonCapture -ScriptPath $chatValidator -Arguments @('--log', $badChatLog)
    Assert-Condition -Condition ($badChatResult.ExitCode -ne 0) -Message 'bad chat log unexpectedly passed'
    Assert-Condition -Condition ($badChatResult.Output.Contains('CHAT_KOUJO_MISSING')) -Message 'bad chat log did not report CHAT_KOUJO_MISSING'

    $badGuardLog = Join-Path -Path $targetRepo -ChildPath 'logs/bad-guard-usage.md'
    $badGuardContent = @(
      '# E2E AI Log (v2.8)',
      '',
      '- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化',
      '',
      '## Entries',
      '- 2026-02-08T00:00:00Z 殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！',
      '- 2026-02-08T00:00:01Z 【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「ガード欠落テスト」を務めます。送信経路を点検します。',
      '- 2026-02-08T00:00:02Z DECLARATION team=coordinator role=coordinator task=T-999 action=guard_bypass_test'
    ) -join "`n"
    Write-Utf8File -Path $badGuardLog -Content "$badGuardContent`n"

    $badGuardResult = Invoke-PythonCapture -ScriptPath $guardUsageValidator -Arguments @('--log', $badGuardLog)
    Assert-Condition -Condition ($badGuardResult.ExitCode -ne 0) -Message 'bad guard usage log unexpectedly passed'
    Assert-Condition -Condition ($badGuardResult.Output.Contains('CHAT_GUARD_USAGE_MISSING')) -Message 'bad guard usage log did not report CHAT_GUARD_USAGE_MISSING'

    $invalidGuardMessage = Join-Path -Path $messageDir -ChildPath 'guard-invalid-task-start.txt'
    Write-Utf8File -Path $invalidGuardMessage -Content @'
【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「不正task_start」を務めます。順序違反です。
DECLARATION team=coordinator role=coordinator task=T-999 action=invalid_task_start
'@
    $fixedTemplatePath = Join-Path -Path $messageDir -ChildPath 'guard-fixed-template.txt'
    if (Test-Path -LiteralPath $fixedTemplatePath) {
      Remove-Item -LiteralPath $fixedTemplatePath -Force
    }
    $guardBlocked = Invoke-AgentTeamsCapture -Arguments @(
      'guard-chat',
      '--event', 'task_start',
      '--team', 'coordinator',
      '--role', 'coordinator',
      '--task', 'T-999',
      '--task-title', '不正task_start',
      '--message-file', $invalidGuardMessage,
      '--task-file', $taskFileRel,
      '--log', 'logs/e2e-ai-log.md',
      '--emit-fixed-file', $fixedTemplatePath
    )
    Assert-Condition -Condition ($guardBlocked.ExitCode -ne 0) -Message 'invalid guard-chat message unexpectedly passed'
    $guardErrorFound = $guardBlocked.Output.Contains('CHAT_ENTRY_FORMAT_INVALID') -or $guardBlocked.Output.Contains('CHAT_GLOBAL_KICKOFF_MISSING')
    Assert-Condition -Condition $guardErrorFound -Message 'invalid guard-chat did not report expected task_start declaration failure'
    Assert-Condition -Condition (Test-Path -LiteralPath $fixedTemplatePath -PathType Leaf) -Message 'guard-chat did not emit fixed template file'

    $badReadLog = Join-Path -Path $targetRepo -ChildPath 'logs/bad-read-evidence.md'
    $badReadContent = @(
      '# E2E AI Log (v2.8)',
      '',
      '- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化',
      '',
      '## Entries',
      '- 2026-01-01T00:00:00Z 殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！',
      '- 2026-01-01T00:00:01Z 【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「読取証跡不足テスト」を務めます。読取証跡を点検します。',
      '- 2026-01-01T00:00:02Z DECLARATION team=coordinator role=coordinator task=T-999 action=read_canonical_rules',
      '- 2026-01-01T00:00:03Z 実行 Get-Content -Path .codex/AGENTS.md -Encoding utf8'
    ) -join "`n"
    Write-Utf8File -Path $badReadLog -Content "$badReadContent`n"

    $badReadResult = Invoke-PythonCapture -ScriptPath $operationValidator -Arguments @(
      '--task-file', $taskFileRel,
      '--log', $badReadLog,
      '--min-teams', "$MinTeams",
      '--min-roles', "$MinRoles"
    )
    Assert-Condition -Condition ($badReadResult.ExitCode -ne 0) -Message 'bad read evidence log unexpectedly passed'
    Assert-Condition -Condition ($badReadResult.Output.Contains('READ_EVIDENCE_MISSING')) -Message 'bad read evidence log did not report READ_EVIDENCE_MISSING'

    $badDistributionRel = '.codex/states/TASK-00998-operation-low-distribution.yaml'
    $badDistributionPath = Join-Path -Path $targetRepo -ChildPath $badDistributionRel
    Write-Utf8File -Path $badDistributionPath -Content (Build-LowDistributionTaskYaml -TaskId 'T-998' -Timestamp (Get-UtcIso))

    $badDistributionResult = Invoke-PythonCapture -ScriptPath $operationValidator -Arguments @(
      '--task-file', $badDistributionRel,
      '--log', 'logs/e2e-ai-log.md',
      '--min-teams', '3',
      '--min-roles', '5'
    )
    Assert-Condition -Condition ($badDistributionResult.ExitCode -ne 0) -Message 'bad distribution task unexpectedly passed'
    $distributionErrorFound = $badDistributionResult.Output.Contains('TEAM_DISTRIBUTION_INSUFFICIENT') -or $badDistributionResult.Output.Contains('ROLE_DISTRIBUTION_INSUFFICIENT')
    Assert-Condition -Condition $distributionErrorFound -Message 'bad distribution task did not report distribution failure'

    $badDeclRel = '.codex/states/TASK-00997-operation-bad-declaration.yaml'
    $badDeclPath = Join-Path -Path $targetRepo -ChildPath $badDeclRel
    Write-Utf8File -Path $badDeclPath -Content (Build-BadDeclarationTaskYaml -TaskId 'T-997' -Timestamp (Get-UtcIso))

    $badDeclResult = Invoke-TaskValidatorCapture -TaskValidatorPath $taskValidator -TaskPath $badDeclPath
    Assert-Condition -Condition ($badDeclResult.ExitCode -ne 0) -Message 'bad declaration task unexpectedly passed validate-task-state'
    Assert-Condition -Condition ($badDeclResult.Output.Contains('handoff memo must start with valid DECLARATION format')) -Message 'bad declaration task did not report DECLARATION format failure'

    Write-Host '[5/5] operation smoke checks completed'
  }
  finally {
    Pop-Location
  }

  Write-Host 'Operation E2E result: PASS'
}
catch {
  $cleanup = -not $KeepTempOnFailure
  Write-Error $_
  throw
}
finally {
  if ($cleanup -and (Test-Path -LiteralPath $tempRoot)) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
    Write-Host "Operation E2E cleanup: removed $tempRoot"
  }
  else {
    Write-Host "Operation E2E cleanup skipped: $tempRoot"
  }
}

