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

$previousErrorActionPreference = $ErrorActionPreference
try {
    # Windows PowerShell 5 promotes native stderr to NativeCommandError when
    # ErrorActionPreference is Stop. Suppress only this expected probe failure
    # and decide from Python's exit code instead.
    $ErrorActionPreference = "SilentlyContinue"
    & $python -c "import fastapi, uvicorn, docx, openpyxl" 2>$null
    $dependencyProbeExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($dependencyProbeExitCode -ne 0) {
    Write-Host "Python dependencies are incomplete. Installing requirements..." -ForegroundColor Yellow
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 turns native stderr into NativeCommandError when
        # ErrorActionPreference is Stop. Native package managers legitimately
        # write progress and warnings to stderr, so rely on their exit code.
        $ErrorActionPreference = "Continue"
        if ($uv) {
            & $uv.Source pip install --python $python -r $requirements
        } else {
            & $python -m pip install -r $requirements
        }
        $dependencyInstallExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($dependencyInstallExitCode -ne 0) {
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
