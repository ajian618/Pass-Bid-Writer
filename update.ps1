param(
    [switch]$SkipPull,
    [switch]$CleanLegacyWorkspace
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
Set-Location $root

function Assert-InWorkspace([string]$PathValue) {
    $full = [System.IO.Path]::GetFullPath($PathValue)
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the workspace: $full"
    }
    return $full
}

if (-not $SkipPull) {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "Git was not found. Use the V1 release ZIP or install Git first."
    }
    $trackedChanges = & $git.Source status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the current Git worktree."
    }
    if ($trackedChanges) {
        Write-Host ""
        Write-Host "Tracked local changes were found. Update stopped without changing files." -ForegroundColor Yellow
        Write-Host "Back up the changed files, then inspect them with:"
        Write-Host "  git status --short"
        Write-Host "  git diff"
        Write-Host "After keeping or discarding those changes, run update.ps1 again."
        exit 2
    }
    & $git.Source fetch origin
    if ($LASTEXITCODE -ne 0) { throw "git fetch origin failed." }
    & $git.Source pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) {
        throw "Fast-forward update failed. No automatic reset was performed."
    }
}

if ($CleanLegacyWorkspace) {
    $legacyTargets = @(
        ".venv",
        "storage",
        "projects",
        "reports",
        "outputs",
        ".agents",
        ".codex",
        "workbench\node_modules",
        "workbench\.npm-cache"
    )
    foreach ($relative in $legacyTargets) {
        $target = Assert-InWorkspace (Join-Path $root $relative)
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
            Write-Host "Removed legacy workspace path: $relative"
        }
    }
    $emptyHermesConfig = Join-Path $root "config\hermes"
    if (Test-Path -LiteralPath $emptyHermesConfig) {
        $target = Assert-InWorkspace $emptyHermesConfig
        if (-not (Get-ChildItem -LiteralPath $target -Force)) {
            Remove-Item -LiteralPath $target -Force
        }
    }
}

$required = @(
    "pass_bid_writing\api.py",
    "workbench\dist\index.html",
    "setup.ps1",
    "start.ps1"
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $relative))) {
        throw "V1 delivery file is missing: $relative"
    }
}

& (Join-Path $root "setup.ps1")
if ($LASTEXITCODE -ne 0) { throw "V1 runtime setup failed." }

$python = Join-Path $env:LOCALAPPDATA "PassBidWriter\venv\Scripts\python.exe"
& $python -c "from pass_bid_writing.api import create_app; app=create_app(); print('V1 import check: OK')"
if ($LASTEXITCODE -ne 0) { throw "V1 import verification failed." }

Write-Host ""
Write-Host "PassBidWriter V1 update completed." -ForegroundColor Green
Write-Host "Old repo-local data was not migrated."
Write-Host "Runtime data: $env:LOCALAPPDATA\PassBidWriter"
Write-Host "Start now with: .\start.ps1"
