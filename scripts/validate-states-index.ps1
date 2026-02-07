#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$Path = '.codex/states/_index.yaml'
)

$requiredTopLevelKeys = @('version', 'project', 'tasks', 'updated_at')
$allowedStatuses = @('todo', 'in_progress', 'in_review', 'blocked', 'done')
$requiredTaskKeys = @('id', 'title', 'status', 'assignee', 'file', 'updated_at')
$hasErrors = $false

if (-not (Test-Path -LiteralPath $Path)) {
  Write-Error "index file not found: $Path"
  exit 1
}

$lines = Get-Content -LiteralPath $Path
$topLevelKeys = New-Object System.Collections.Generic.List[string]
foreach ($line in $lines) {
  $m = [regex]::Match($line, '^([A-Za-z_][A-Za-z0-9_]*)\s*:')
  if ($m.Success) {
    $k = $m.Groups[1].Value
    if (-not $topLevelKeys.Contains($k)) { $topLevelKeys.Add($k) }
  }
}

$missingTop = $requiredTopLevelKeys | Where-Object { $_ -notin $topLevelKeys }
if ($missingTop.Count -gt 0) {
  Write-Error "missing top-level keys: $($missingTop -join ', ')"
  $hasErrors = $true
}

$extraTop = $topLevelKeys | Where-Object { $_ -notin $requiredTopLevelKeys }
if ($extraTop.Count -gt 0) {
  Write-Error "unexpected top-level keys: $($extraTop -join ', ')"
  $hasErrors = $true
}

$section = ''
$projectKeys = New-Object System.Collections.Generic.List[string]
$inTask = $false
$taskIndex = 0
$taskKeys = New-Object System.Collections.Generic.List[string]
$currentStatus = ''
$currentFile = ''
$baseDir = Split-Path -Parent (Resolve-Path $Path)

function Validate-TaskRecord {
  param(
    [int]$Index,
    [System.Collections.Generic.List[string]]$Keys,
    [string]$Status,
    [string]$FileName,
    [string]$BaseDir,
    [ref]$ErrFlag
  )

  $missing = $requiredTaskKeys | Where-Object { $_ -notin $Keys }
  if ($missing.Count -gt 0) {
    Write-Error "tasks[$Index] missing keys: $($missing -join ', ')"
    $ErrFlag.Value = $true
  }

  if ($Status -and $Status -notin $allowedStatuses) {
    Write-Error "tasks[$Index].status invalid: '$Status'"
    $ErrFlag.Value = $true
  }

  if ($FileName) {
    if ($FileName -notmatch '^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$') {
      Write-Error "tasks[$Index].file invalid naming: '$FileName'"
      $ErrFlag.Value = $true
    } else {
      $resolved = Join-Path $BaseDir $FileName
      if (-not (Test-Path -LiteralPath $resolved)) {
        Write-Error "tasks[$Index].file not found: '$FileName'"
        $ErrFlag.Value = $true
      }
    }
  }
}

foreach ($line in $lines) {
  $mTop = [regex]::Match($line, '^([A-Za-z_][A-Za-z0-9_]*)\s*:')
  if ($mTop.Success) {
    if ($section -eq 'tasks' -and $inTask) {
      Validate-TaskRecord -Index $taskIndex -Keys $taskKeys -Status $currentStatus -FileName $currentFile -BaseDir $baseDir -ErrFlag ([ref]$hasErrors)
    }
    $section = $mTop.Groups[1].Value
    $inTask = $false
    $taskKeys = New-Object System.Collections.Generic.List[string]
    $currentStatus = ''
    $currentFile = ''
    continue
  }

  if ($section -eq 'project') {
    $mProject = [regex]::Match($line, '^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:')
    if ($mProject.Success) {
      $projectKey = $mProject.Groups[1].Value
      if (-not $projectKeys.Contains($projectKey)) { $projectKeys.Add($projectKey) }
    }
    continue
  }

  if ($section -ne 'tasks') { continue }

  if ($line -match '^\s{2}-\s') {
    if ($inTask) {
      Validate-TaskRecord -Index $taskIndex -Keys $taskKeys -Status $currentStatus -FileName $currentFile -BaseDir $baseDir -ErrFlag ([ref]$hasErrors)
    }

    $taskIndex++
    $inTask = $true
    $taskKeys = New-Object System.Collections.Generic.List[string]
    $currentStatus = ''
    $currentFile = ''

    if ($line -match '^\s{2}-\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)?$') {
      $k = $Matches[1]
      if (-not $taskKeys.Contains($k)) { $taskKeys.Add($k) }
      if ($k -eq 'status') { $currentStatus = $Matches[2].Trim() }
      if ($k -eq 'file') { $currentFile = $Matches[2].Trim() }
    }
    continue
  }

  if ($inTask -and $line -match '^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)?$') {
    $k = $Matches[1]
    $v = $Matches[2].Trim()
    if (-not $taskKeys.Contains($k)) { $taskKeys.Add($k) }
    if ($k -eq 'status') { $currentStatus = $v }
    if ($k -eq 'file') { $currentFile = $v }
  }
}

if ($section -eq 'tasks' -and $inTask) {
  Validate-TaskRecord -Index $taskIndex -Keys $taskKeys -Status $currentStatus -FileName $currentFile -BaseDir $baseDir -ErrFlag ([ref]$hasErrors)
}

$requiredProjectKeys = @('name', 'repository', 'default_branch')
$missingProject = $requiredProjectKeys | Where-Object { $_ -notin $projectKeys }
if ($missingProject.Count -gt 0) {
  Write-Error "project missing keys: $($missingProject -join ', ')"
  $hasErrors = $true
}

if ($hasErrors) { exit 1 }
Write-Host "states index is valid: $Path"
exit 0
