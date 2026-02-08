#!/usr/bin/env pwsh
$argsList = @($args)
$target = $null
$force = $false

for ($i = 0; $i -lt $argsList.Count; $i++) {
  $token = [string]$argsList[$i]
  switch ($token.ToLowerInvariant()) {
    '--target' {
      if ($i + 1 -ge $argsList.Count) {
        Write-Error '--target requires a path value.'
        exit 1
      }
      $target = [string]$argsList[$i + 1]
      $i++
    }
    '-target' {
      if ($i + 1 -ge $argsList.Count) {
        Write-Error '-Target requires a path value.'
        exit 1
      }
      $target = [string]$argsList[$i + 1]
      $i++
    }
    '--force' { $force = $true }
    '-force' { $force = $true }
    default {
      Write-Error "Unknown argument: $token"
      Write-Host 'Usage: bootstrap-agent-teams.ps1 --target <path> [--force]'
      exit 1
    }
  }
}

if (-not $target) {
  Write-Error 'Missing required argument: --target <path>'
  Write-Host 'Usage: bootstrap-agent-teams.ps1 --target <path> [--force]'
  exit 1
}

$templateRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
if ([System.IO.Path]::IsPathRooted($target)) {
  $targetRoot = [System.IO.Path]::GetFullPath($target)
} else {
  $targetRoot = [System.IO.Path]::GetFullPath((Join-Path -Path (Get-Location).Path -ChildPath $target))
}

if (-not (Test-Path -LiteralPath $targetRoot)) {
  New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
}

if ($templateRoot.ToLowerInvariant() -eq $targetRoot.ToLowerInvariant()) {
  Write-Error 'Target path must be different from template root.'
  exit 1
}

$pathsToCopy = @(
  'at',
  'at.cmd',
  'at.ps1',
  'AGENTS.md',
  'README.md',
  '.gitleaks.toml',
  '.github',
  '.codex',
  'docs',
  'shared',
  'scripts'
)

$summary = [ordered]@{
  copied = 0
  skipped = 0
  overwritten = 0
}

function Copy-TemplateEntry {
  param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$DestinationPath,
    [Parameter(Mandatory = $true)][bool]$AllowOverwrite
  )

  $sourceName = Split-Path -Path $SourcePath -Leaf
  if ($sourceName -eq '__pycache__') {
    return
  }

  if (Test-Path -LiteralPath $SourcePath -PathType Container) {
    if (-not (Test-Path -LiteralPath $DestinationPath)) {
      New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    }

    Get-ChildItem -LiteralPath $SourcePath -Force | ForEach-Object {
      $childDestination = Join-Path -Path $DestinationPath -ChildPath $_.Name
      Copy-TemplateEntry -SourcePath $_.FullName -DestinationPath $childDestination -AllowOverwrite $AllowOverwrite
    }
    return
  }

  if ($sourceName.ToLowerInvariant().EndsWith('.pyc')) {
    return
  }

  if (Test-Path -LiteralPath $DestinationPath) {
    if ($AllowOverwrite) {
      Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
      $script:summary.overwritten++
      Write-Host "OVERWRITE $DestinationPath"
    } else {
      $script:summary.skipped++
      Write-Host "SKIP $DestinationPath"
    }
  } else {
    $destinationParent = Split-Path -Parent $DestinationPath
    if ($destinationParent -and -not (Test-Path -LiteralPath $destinationParent)) {
      New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }

    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath
    $script:summary.copied++
    Write-Host "COPY $DestinationPath"
  }
}

foreach ($relativePath in $pathsToCopy) {
  $sourcePath = Join-Path -Path $templateRoot -ChildPath $relativePath
  if (-not (Test-Path -LiteralPath $sourcePath)) {
    Write-Warning "Source path not found: $sourcePath"
    continue
  }

  $destinationPath = Join-Path -Path $targetRoot -ChildPath $relativePath
  Copy-TemplateEntry -SourcePath $sourcePath -DestinationPath $destinationPath -AllowOverwrite $force
}

Write-Host ''
Write-Host "Completed bootstrap to: $targetRoot"
Write-Host "Copied: $($summary.copied)"
Write-Host "Skipped: $($summary.skipped)"
Write-Host "Overwritten: $($summary.overwritten)"
exit 0
