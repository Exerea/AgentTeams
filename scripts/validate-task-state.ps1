#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$Path
)

if (-not $Path) {
  Write-Error 'Path is required. Usage: validate-task-state.ps1 -Path <TASK-xxxxx-slug.yaml>'
  exit 1
}

if (-not (Test-Path -LiteralPath $Path)) {
  Write-Error "task file not found: $Path"
  exit 1
}

$allowedStatuses = @('todo', 'in_progress', 'in_review', 'blocked', 'done')
$requiredTopKeys = @('id', 'title', 'owner', 'assignee', 'status', 'target_stack', 'depends_on', 'adr_refs', 'local_flags', 'warnings', 'handoffs', 'notes', 'updated_at')
$requiredTargetStackKeys = @('language', 'framework', 'infra')
$requiredFlagKeys = @('major_decision_required', 'documentation_sync_required', 'tech_specialist_required', 'qa_review_required', 'research_track_enabled', 'backend_security_required')
$requiredWarningKeys = @('id', 'level', 'code', 'detected_by', 'source_role', 'target_role', 'detected_at', 'summary', 'status', 'resolution_task_ids', 'updated_at')
$allowedWarningLevels = @('warning', 'error')
$allowedWarningStatuses = @('open', 'triaged', 'resolved')
$allowedWarningCodes = @(
  'PROTO_SCHEMA_MISMATCH',
  'PROTO_FIELD_CASE_MISMATCH',
  'PROTO_REQUIRED_FIELD_MISSING',
  'PROTO_UNEXPECTED_FIELD',
  'PROTO_HANDOFF_CONTEXT_MISSING'
)
$qaRoles = @('qa-review-guild/code-critic', 'qa-review-guild/test-architect')
$backendSecurityRole = 'backend/security-expert'
$techRolePrefix = 'tech-specialist-guild/'
$researchRoles = @('innovation-research-guild/trend-researcher', 'innovation-research-guild/poc-agent')

$hasErrors = $false
$name = Split-Path -Leaf $Path
if ($name -notmatch '^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$') {
  Write-Error "invalid task filename: $name"
  $hasErrors = $true
}

$lines = Get-Content -LiteralPath $Path

# Top-level keys
$topKeys = New-Object System.Collections.Generic.List[string]
foreach ($line in $lines) {
  $m = [regex]::Match($line, '^([A-Za-z_][A-Za-z0-9_]*)\s*:')
  if ($m.Success) {
    $k = $m.Groups[1].Value
    if (-not $topKeys.Contains($k)) { $topKeys.Add($k) }
  }
}

$missingTop = $requiredTopKeys | Where-Object { $_ -notin $topKeys }
if ($missingTop.Count -gt 0) {
  Write-Error "missing top-level keys: $($missingTop -join ', ')"
  $hasErrors = $true
}

$extraTop = $topKeys | Where-Object { $_ -notin $requiredTopKeys }
if ($extraTop.Count -gt 0) {
  Write-Error "unexpected top-level keys: $($extraTop -join ', ')"
  $hasErrors = $true
}

$section = ''
$status = ''
$assignee = ''
$notes = ''
$adrRefCount = 0
$targetStack = @{}
$flagValues = @{}
$warningOpenCount = 0

$handoffIndex = 0
$inHandoff = $false
$handoffKeys = New-Object System.Collections.Generic.List[string]
$handoffFromValues = New-Object System.Collections.Generic.List[string]
$handoffToValues = New-Object System.Collections.Generic.List[string]

$warningIndex = 0
$inWarning = $false
$warningKeys = New-Object System.Collections.Generic.List[string]
$warningLevel = ''
$warningStatus = ''
$warningCode = ''

function Validate-Handoff {
  param([int]$Index, [System.Collections.Generic.List[string]]$Keys, [ref]$ErrFlag)
  $required = @('from', 'to', 'at', 'memo')
  $missing = $required | Where-Object { $_ -notin $Keys }
  if ($missing.Count -gt 0) {
    Write-Error "handoffs[$Index] missing keys: $($missing -join ', ')"
    $ErrFlag.Value = $true
  }
}

function Validate-Warning {
  param(
    [int]$Index,
    [System.Collections.Generic.List[string]]$Keys,
    [string]$Level,
    [string]$WarnStatus,
    [string]$Code,
    [ref]$OpenCount,
    [ref]$ErrFlag
  )

  $missing = $requiredWarningKeys | Where-Object { $_ -notin $Keys }
  if ($missing.Count -gt 0) {
    Write-Error "warnings[$Index] missing keys: $($missing -join ', ')"
    $ErrFlag.Value = $true
  }
  if ($Level -and $Level -notin $allowedWarningLevels) {
    Write-Error "warnings[$Index].level invalid: '$Level'"
    $ErrFlag.Value = $true
  }
  if ($WarnStatus -and $WarnStatus -notin $allowedWarningStatuses) {
    Write-Error "warnings[$Index].status invalid: '$WarnStatus'"
    $ErrFlag.Value = $true
  }
  if ($Code -and $Code -notin $allowedWarningCodes) {
    Write-Error "warnings[$Index].code invalid: '$Code'"
    $ErrFlag.Value = $true
  }
  if ($WarnStatus -eq 'open') {
    $OpenCount.Value++
  }
}

foreach ($line in $lines) {
  $mTop = [regex]::Match($line, '^([A-Za-z_][A-Za-z0-9_]*)\s*:')
  if ($mTop.Success) {
    if ($mTop.Groups[1].Value -eq 'status') {
      $mInlineStatus = [regex]::Match($line, '^status\s*:\s*(.+)$')
      if ($mInlineStatus.Success) { $status = $mInlineStatus.Groups[1].Value.Trim() }
    }
    if ($mTop.Groups[1].Value -eq 'assignee') {
      $mInlineAssignee = [regex]::Match($line, '^assignee\s*:\s*(.+)$')
      if ($mInlineAssignee.Success) { $assignee = $mInlineAssignee.Groups[1].Value.Trim() }
    }
    if ($mTop.Groups[1].Value -eq 'notes') {
      $mInlineNotes = [regex]::Match($line, '^notes\s*:\s*(.+)$')
      if ($mInlineNotes.Success) { $notes = $mInlineNotes.Groups[1].Value.Trim() }
    }

    if ($section -eq 'handoffs' -and $inHandoff) {
      Validate-Handoff -Index $handoffIndex -Keys $handoffKeys -ErrFlag ([ref]$hasErrors)
    }
    if ($section -eq 'warnings' -and $inWarning) {
      Validate-Warning -Index $warningIndex -Keys $warningKeys -Level $warningLevel -WarnStatus $warningStatus -Code $warningCode -OpenCount ([ref]$warningOpenCount) -ErrFlag ([ref]$hasErrors)
    }

    $section = $mTop.Groups[1].Value
    $inHandoff = $false
    $handoffKeys = New-Object System.Collections.Generic.List[string]
    $inWarning = $false
    $warningKeys = New-Object System.Collections.Generic.List[string]
    $warningLevel = ''
    $warningStatus = ''
    $warningCode = ''
    continue
  }

  if ($section -eq 'target_stack' -and $line -match '^\s{2}(language|framework|infra)\s*:\s*(.+)\s*$') {
    $targetStack[$Matches[1]] = $Matches[2].Trim()
    continue
  }

  if ($section -eq 'local_flags' -and $line -match '^\s{2}(major_decision_required|documentation_sync_required|tech_specialist_required|qa_review_required|research_track_enabled|backend_security_required)\s*:\s*(.+)\s*$') {
    $k = $Matches[1]
    $v = $Matches[2].Trim().ToLowerInvariant()
    if ($v -notin @('true', 'false')) {
      Write-Error "local_flags.$k must be true or false"
      $hasErrors = $true
    } else {
      $flagValues[$k] = $v
    }
    continue
  }

  if ($section -eq 'adr_refs' -and $line -match '^\s{2}-\s+(.+)$') {
    $adrRefCount++
    continue
  }

  if ($section -eq 'warnings') {
    if ($line -match '^\s{2}-\s') {
      if ($inWarning) {
        Validate-Warning -Index $warningIndex -Keys $warningKeys -Level $warningLevel -WarnStatus $warningStatus -Code $warningCode -OpenCount ([ref]$warningOpenCount) -ErrFlag ([ref]$hasErrors)
      }
      $warningIndex++
      $inWarning = $true
      $warningKeys = New-Object System.Collections.Generic.List[string]
      $warningLevel = ''
      $warningStatus = ''
      $warningCode = ''
      if ($line -match '^\s{2}-\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$') {
        $k = $Matches[1]
        $v = $Matches[2].Trim()
        if (-not $warningKeys.Contains($k)) { $warningKeys.Add($k) }
        if ($k -eq 'level') { $warningLevel = $v }
        if ($k -eq 'status') { $warningStatus = $v }
        if ($k -eq 'code') { $warningCode = $v }
      }
      continue
    }
    if ($inWarning -and $line -match '^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$') {
      $k = $Matches[1]
      $v = $Matches[2].Trim()
      if (-not $warningKeys.Contains($k)) { $warningKeys.Add($k) }
      if ($k -eq 'level') { $warningLevel = $v }
      if ($k -eq 'status') { $warningStatus = $v }
      if ($k -eq 'code') { $warningCode = $v }
    }
    continue
  }

  if ($section -eq 'handoffs') {
    if ($line -match '^\s{2}-\s') {
      if ($inHandoff) {
        Validate-Handoff -Index $handoffIndex -Keys $handoffKeys -ErrFlag ([ref]$hasErrors)
      }
      $handoffIndex++
      $inHandoff = $true
      $handoffKeys = New-Object System.Collections.Generic.List[string]
      if ($line -match '^\s{2}-\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$') {
        $k = $Matches[1]
        $v = $Matches[2].Trim()
        if (-not $handoffKeys.Contains($k)) { $handoffKeys.Add($k) }
        if ($k -eq 'from') { $handoffFromValues.Add($v) }
        if ($k -eq 'to') { $handoffToValues.Add($v) }
      }
      continue
    }
    if ($inHandoff -and $line -match '^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$') {
      $k = $Matches[1]
      $v = $Matches[2].Trim()
      if (-not $handoffKeys.Contains($k)) { $handoffKeys.Add($k) }
      if ($k -eq 'from') { $handoffFromValues.Add($v) }
      if ($k -eq 'to') { $handoffToValues.Add($v) }
    }
    continue
  }
}

if ($section -eq 'handoffs' -and $inHandoff) {
  Validate-Handoff -Index $handoffIndex -Keys $handoffKeys -ErrFlag ([ref]$hasErrors)
}
if ($section -eq 'warnings' -and $inWarning) {
  Validate-Warning -Index $warningIndex -Keys $warningKeys -Level $warningLevel -WarnStatus $warningStatus -Code $warningCode -OpenCount ([ref]$warningOpenCount) -ErrFlag ([ref]$hasErrors)
}

if ($status -and $status -notin $allowedStatuses) {
  Write-Error "status invalid: '$status'"
  $hasErrors = $true
}

foreach ($k in $requiredTargetStackKeys) {
  if (-not $targetStack.ContainsKey($k) -or [string]::IsNullOrWhiteSpace($targetStack[$k])) {
    Write-Error "missing required target_stack key: $k"
    $hasErrors = $true
  }
}

foreach ($k in $requiredFlagKeys) {
  if (-not $flagValues.ContainsKey($k)) {
    Write-Error "missing required local_flags key: $k"
    $hasErrors = $true
  }
}

$allHandoffRoles = @($handoffFromValues + $handoffToValues)
$hasCodeCritic = $allHandoffRoles -contains 'qa-review-guild/code-critic'
$hasTestArchitect = $allHandoffRoles -contains 'qa-review-guild/test-architect'
$hasBackendSecurityEvidence = (($assignee -eq $backendSecurityRole) -or ($allHandoffRoles -contains $backendSecurityRole))
$hasTechSpecialist = ($assignee.StartsWith($techRolePrefix) -or (($allHandoffRoles | Where-Object { $_.StartsWith($techRolePrefix) }).Count -gt 0))
$hasResearchRole = (($researchRoles -contains $assignee) -or (($allHandoffRoles | Where-Object { $_ -in $researchRoles }).Count -gt 0))

if ($status -eq 'done' -and $warningOpenCount -gt 0) {
  Write-Error 'task cannot be done while warnings.status=open exists'
  $hasErrors = $true
}

if ($status -eq 'done' -and $flagValues['qa_review_required'] -eq 'true') {
  if (-not (($qaRoles -contains $assignee) -or ($hasCodeCritic -and $hasTestArchitect))) {
    Write-Error 'qa_review_required=true requires code-critic and test-architect evidence before done'
    $hasErrors = $true
  }
}

if ($status -eq 'done' -and $flagValues['backend_security_required'] -eq 'true' -and -not $hasBackendSecurityEvidence) {
  Write-Error 'backend_security_required=true requires backend/security-expert evidence before done'
  $hasErrors = $true
}

if ($status -eq 'done' -and $flagValues['tech_specialist_required'] -eq 'true' -and -not $hasTechSpecialist) {
  Write-Error 'tech_specialist_required=true requires tech-specialist-guild evidence before done'
  $hasErrors = $true
}

if ($status -eq 'done' -and $flagValues['research_track_enabled'] -eq 'true') {
  if ($notes -notmatch 'poc_result') {
    Write-Error "research_track_enabled=true requires notes to include 'poc_result' before done"
    $hasErrors = $true
  }
  if ($adrRefCount -lt 1) {
    Write-Error 'research_track_enabled=true requires adr_refs before done'
    $hasErrors = $true
  }
  if (-not $hasResearchRole) {
    Write-Error 'research_track_enabled=true requires trend-researcher/poc-agent evidence before done'
    $hasErrors = $true
  }
}

if ($hasErrors) { exit 1 }
Write-Host "task state is valid: $Path"
exit 0
