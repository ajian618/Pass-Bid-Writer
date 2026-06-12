$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$profileName = "pass-bid-writer"
$description = "Zhejiang pass/fail technical bid writer. Uses pass-bid-writing MCP to learn accepted case pairs, extract tender requirements, generate DOCX drafts, and run compliance checks."

Write-Host "Project root: $root"

$hermes = Get-Command hermes -ErrorAction SilentlyContinue
if (-not $hermes) {
  throw "Cannot find 'hermes' in PATH. Open a new PowerShell window after installing Hermes, or add Hermes to PATH."
}
Write-Host "Hermes command: $($hermes.Source)"

$runner = Join-Path $root "scripts\pass-bid-writing-mcp.cmd"
if (-not (Test-Path -LiteralPath $runner)) {
  throw "MCP runner not found: $runner"
}
Write-Host "MCP runner: $runner"

$profileList = & hermes profile list | Out-String
if ($profileList -notmatch "(^|\s)$([Regex]::Escape($profileName))(\s|$)") {
  Write-Host "Creating Hermes profile: $profileName"
  & hermes profile create $profileName --clone --description $description
} else {
  Write-Host "Hermes profile already exists: $profileName"
  & hermes profile describe $profileName --text $description
}

$show = & hermes profile show $profileName | Out-String
$profilePath = $null
foreach ($line in ($show -split "`r?`n")) {
  if ($line -match '^Path:\s+(.+)$') {
    $profilePath = $Matches[1].Trim()
    break
  }
}
if (-not $profilePath -or -not (Test-Path -LiteralPath $profilePath)) {
  throw "Could not resolve profile path for $profileName. Output was:`n$show"
}
Write-Host "Profile path: $profilePath"

$configPath = Join-Path $profilePath "config.yaml"
if (-not (Test-Path -LiteralPath $configPath)) {
  throw "Hermes profile config file not found: $configPath"
}

$backupPath = "$configPath.pass-bid-writing-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
Write-Host "Backup written: $backupPath"

$rawLines = [System.IO.File]::ReadAllLines($configPath, [System.Text.Encoding]::UTF8)
$lines = [System.Collections.Generic.List[string]]::new()
foreach ($line in $rawLines) {
  $lines.Add($line)
}

$escapedRunner = $runner.Replace("'", "''")
$escapedRoot = $root.Replace("'", "''")
$childBlock = @(
  "  pass-bid-writing:",
  "    command: '$escapedRunner'",
  "    enabled: true"
)
$fullBlock = @("mcp_servers:") + $childBlock

$mcpIndex = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match '^mcp_servers:\s*$') {
    $mcpIndex = $i
    break
  }
}

if ($mcpIndex -lt 0) {
  if ($lines.Count -gt 0 -and $lines[$lines.Count - 1].Trim()) {
    $lines.Add("")
  }
  foreach ($line in $fullBlock) {
    $lines.Add($line)
  }
} else {
  $mcpEnd = $lines.Count
  for ($i = $mcpIndex + 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\S') {
      $mcpEnd = $i
      break
    }
  }

  $serverIndex = -1
  for ($i = $mcpIndex + 1; $i -lt $mcpEnd; $i++) {
    if ($lines[$i] -match '^  pass-bid-writing:\s*$') {
      $serverIndex = $i
      break
    }
  }

  if ($serverIndex -lt 0) {
    for ($i = $childBlock.Count - 1; $i -ge 0; $i--) {
      $lines.Insert($mcpEnd, $childBlock[$i])
    }
  } else {
    $serverEnd = $mcpEnd
    for ($i = $serverIndex + 1; $i -lt $mcpEnd; $i++) {
      if ($lines[$i] -match '^  [^ ].*:\s*$') {
        $serverEnd = $i
        break
      }
    }
    $removeCount = $serverEnd - $serverIndex
    $lines.RemoveRange($serverIndex, $removeCount)
    for ($i = $childBlock.Count - 1; $i -ge 0; $i--) {
      $lines.Insert($serverIndex, $childBlock[$i])
    }
  }
}

$mcpIndex = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match '^mcp_servers:\s*$') {
    $mcpIndex = $i
    break
  }
}
if ($mcpIndex -ge 0) {
  $mcpEnd = $lines.Count
  for ($i = $mcpIndex + 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\S') {
      $mcpEnd = $i
      break
    }
  }
  $reviewIndex = -1
  for ($i = $mcpIndex + 1; $i -lt $mcpEnd; $i++) {
    if ($lines[$i] -match '^  bid-review:\s*$') {
      $reviewIndex = $i
      break
    }
  }
  if ($reviewIndex -ge 0) {
    $reviewEnd = $mcpEnd
    for ($i = $reviewIndex + 1; $i -lt $mcpEnd; $i++) {
      if ($lines[$i] -match '^  [^ ].*:\s*$') {
        $reviewEnd = $i
        break
      }
    }
    $lines.RemoveRange($reviewIndex, $reviewEnd - $reviewIndex)
    Write-Host "Removed bid-review MCP from this writing profile to keep workflows separate."
  }
}

$terminalIndex = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match '^terminal:\s*$') {
    $terminalIndex = $i
    break
  }
}

$cwdLine = "  cwd: '$escapedRoot'"
if ($terminalIndex -lt 0) {
  if ($lines.Count -gt 0 -and $lines[$lines.Count - 1].Trim()) {
    $lines.Add("")
  }
  $lines.Add("terminal:")
  $lines.Add($cwdLine)
} else {
  $terminalEnd = $lines.Count
  for ($i = $terminalIndex + 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\S') {
      $terminalEnd = $i
      break
    }
  }

  $cwdIndex = -1
  for ($i = $terminalIndex + 1; $i -lt $terminalEnd; $i++) {
    if ($lines[$i] -match '^  cwd:\s*') {
      $cwdIndex = $i
      break
    }
  }

  if ($cwdIndex -lt 0) {
    $lines.Insert($terminalIndex + 1, $cwdLine)
  } else {
    $lines[$cwdIndex] = $cwdLine
  }
}

$content = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
[System.IO.File]::WriteAllText($configPath, $content, $Utf8NoBom)
Write-Host "pass-bid-writing MCP registration written to profile config."
Write-Host "Hermes terminal.cwd set to: $root"

$soulSource = Join-Path $root "config\hermes\pass-bid-writer-SOUL.md"
$soulTarget = Join-Path $profilePath "SOUL.md"
if (-not (Test-Path -LiteralPath $soulSource)) {
  throw "SOUL source not found: $soulSource"
}
if (Test-Path -LiteralPath $soulTarget) {
  $soulBackup = "$soulTarget.pass-bid-writing-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  Copy-Item -LiteralPath $soulTarget -Destination $soulBackup -Force
  Write-Host "SOUL backup written: $soulBackup"
}
Copy-Item -LiteralPath $soulSource -Destination $soulTarget -Force
Write-Host "SOUL installed: $soulTarget"

& hermes profile use $profileName

Write-Host "Current Hermes profile:"
& hermes profile show $profileName

Write-Host "Current Hermes MCP list:"
& hermes mcp list

Write-Host "Testing pass-bid-writing MCP:"
& hermes mcp test pass-bid-writing
