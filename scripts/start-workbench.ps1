param(
    [switch]$SkipBuild,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workbench = Join-Path $root "workbench"
$dist = Join-Path $workbench "dist\index.html"
$requirements = Join-Path $root "requirements.txt"

Set-Location $root

$python = if ($env:PASS_BID_PYTHON) {
    $env:PASS_BID_PYTHON
} else {
    (Get-Command python -ErrorAction Stop).Source
}

& $python -c "import fastapi, uvicorn, docx, openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & $uv.Source pip install --python $python -r $requirements
    } else {
        & $python -m pip install -r $requirements
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency installation failed. Check network access or set PASS_BID_PYTHON."
    }
}

if (-not (Test-Path (Join-Path $root ".env")) -and (Test-Path (Join-Path $root ".env.example"))) {
    Write-Warning ".env is missing. Unconfigured model roles will be shown as unavailable."
}

if (-not $SkipBuild -or -not (Test-Path $dist)) {
    Push-Location $workbench
    try {
        if (-not (Test-Path (Join-Path $workbench "node_modules"))) {
            npm install
        }
        npm run build
    }
    finally {
        Pop-Location
    }
}

Write-Host "Pass-bid production workbench: http://127.0.0.1:$Port" -ForegroundColor Cyan
& $python -m uvicorn pass_bid_writing.api:app --host 127.0.0.1 --port $Port
