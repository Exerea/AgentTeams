#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$GitleaksVersion = '8.24.2'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..'))
Push-Location $repoRoot

function Resolve-GitleaksPath {
  param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$Version
  )

  $cmd = Get-Command gitleaks -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  $localDir = Join-Path -Path $RepoRoot -ChildPath '.tools\gitleaks'
  $localExe = Join-Path -Path $localDir -ChildPath 'gitleaks.exe'
  if (Test-Path -LiteralPath $localExe) {
    return $localExe
  }

  $archRaw = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToUpperInvariant()
  $archMap = @{
    'X64'   = 'x64'
    'AMD64' = 'x64'
    'ARM64' = 'arm64'
  }
  if (-not $archMap.ContainsKey($archRaw)) {
    throw "unsupported architecture for gitleaks bootstrap: $archRaw"
  }
  $arch = $archMap[$archRaw]

  $asset = "gitleaks_${Version}_windows_${arch}.zip"
  $downloadUrl = "https://github.com/gitleaks/gitleaks/releases/download/v${Version}/${asset}"

  New-Item -ItemType Directory -Path $localDir -Force | Out-Null

  $tmpRoot = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath ("gitleaks-bootstrap-" + [System.Guid]::NewGuid().ToString('N'))
  $zipPath = Join-Path -Path $tmpRoot -ChildPath $asset
  $extractDir = Join-Path -Path $tmpRoot -ChildPath 'extract'

  try {
    New-Item -ItemType Directory -Path $tmpRoot -Force | Out-Null
    Write-Host "gitleaks command not found. Downloading v$Version ($arch) ..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

    $downloadedExe = Join-Path -Path $extractDir -ChildPath 'gitleaks.exe'
    if (-not (Test-Path -LiteralPath $downloadedExe)) {
      throw "gitleaks.exe was not found in downloaded archive: $asset"
    }

    Copy-Item -LiteralPath $downloadedExe -Destination $localExe -Force
    return $localExe
  }
  finally {
    if (Test-Path -LiteralPath $tmpRoot) {
      Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}

try {
  $gitleaksPath = Resolve-GitleaksPath -RepoRoot $repoRoot -Version $GitleaksVersion
  & $gitleaksPath detect --source . --no-git --config .gitleaks.toml --redact
  if ($LASTEXITCODE -ne 0) {
    Write-Error 'secret scan failed'
    exit $LASTEXITCODE
  }

  Write-Host 'secret scan is valid'
  exit 0
}
catch {
  Write-Error $_
  exit 1
}
finally {
  Pop-Location
}
