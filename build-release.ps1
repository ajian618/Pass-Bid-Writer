param([string]$Version = "1.1.2")

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$workbench = Join-Path $root "workbench"
$releaseRoot = Join-Path $root "release"
$packageName = "PassBidWriter-V$Version"
$packageDir = Join-Path $releaseRoot $packageName
$zipPath = Join-Path $releaseRoot "$packageName.zip"

Push-Location $workbench
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Pop-Location
}

py -3.12 -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Python tests failed. Release was stopped." }

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
foreach ($target in @($packageDir, $zipPath)) {
    if (Test-Path -LiteralPath $target) {
        $resolved = (Resolve-Path -LiteralPath $target).Path
        if (-not $resolved.StartsWith($releaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean a target outside the release directory: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
Copy-Item -LiteralPath (Join-Path $root "pass_bid_writing") -Destination $packageDir -Recurse
Copy-Item -LiteralPath (Join-Path $root "requirements.txt") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "AGENTS.md") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "V1_ACCEPTANCE.md") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "setup.ps1") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "start.ps1") -Destination $packageDir
Copy-Item -LiteralPath (Join-Path $root "update.ps1") -Destination $packageDir
New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "workbench") | Out-Null
Copy-Item -LiteralPath (Join-Path $workbench "dist") -Destination (Join-Path $packageDir "workbench") -Recurse

Get-ChildItem -LiteralPath $packageDir -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "V1 release package created: $zipPath" -ForegroundColor Green
