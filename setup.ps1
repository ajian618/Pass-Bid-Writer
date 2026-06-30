param([switch]$Force)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$dataRoot = Join-Path $env:LOCALAPPDATA "PassBidWriter"
$venv = Join-Path $dataRoot "venv"
$python = Join-Path $venv "Scripts\python.exe"

$launcher = Get-Command py -ErrorAction SilentlyContinue
if (-not $launcher) {
    throw "Python Launcher was not found. Install 64-bit Python 3.12 first."
}
$launcherPath = $launcher.Source
$version = & $launcherPath "-3.12" "-c" "import sys; print(str(sys.version_info.major) + '.' + str(sys.version_info.minor))"
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne "3.12") {
    throw "Python 3.12 was not found. Install it and run setup.ps1 again."
}

New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
if ($Force -and (Test-Path -LiteralPath $venv)) {
    $resolved = (Resolve-Path -LiteralPath $venv).Path
    if (-not $resolved.StartsWith($dataRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a venv outside the application data root: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
if (-not (Test-Path -LiteralPath $python)) {
    & $launcherPath "-3.12" "-m" "venv" $venv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the isolated Python environment." }
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $python -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies." }
& $python -c "import fastapi, uvicorn, docx, openpyxl, fitz, PIL; print('Python dependencies: OK')"
if ($LASTEXITCODE -ne 0) { throw "Dependency verification failed." }

if (-not (Test-Path -LiteralPath (Join-Path $root "workbench\dist\index.html"))) {
    Write-Warning "Compiled frontend is missing. In a development checkout, run build-release.ps1."
}

Write-Host ""
Write-Host "PassBidWriter V1 setup completed." -ForegroundColor Green
Write-Host "Data directory: $dataRoot"
Write-Host "Daily start command: .\start.ps1"
