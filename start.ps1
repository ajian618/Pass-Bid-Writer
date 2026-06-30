param([int]$Port = 8000, [switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$python = Join-Path $env:LOCALAPPDATA "PassBidWriter\venv\Scripts\python.exe"
$dist = Join-Path $root "workbench\dist\index.html"

if (-not (Test-Path -LiteralPath $python)) {
    throw "The isolated runtime is not installed. Run .\setup.ps1 first."
}
if (-not (Test-Path -LiteralPath $dist)) {
    throw "The compiled frontend is missing. Use a V1 release package or run .\build-release.ps1."
}

$previous = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    & $python -c "import fastapi, uvicorn, docx, openpyxl, fitz" 2>$null
    $probe = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($probe -ne 0) {
    throw "Runtime dependencies are incomplete. Run .\setup.ps1 -Force."
}

Set-Location $root
$url = "http://127.0.0.1:$Port"
if (-not $NoBrowser) {
    $escapedUrl = $url.Replace("'", "''")
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-Command", "Start-Sleep -Seconds 2; Start-Process '$escapedUrl'"
    ) | Out-Null
}
Write-Host "PassBidWriter V1: $url" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop. Daily startup never downloads dependencies."
& $python -m uvicorn pass_bid_writing.api:app --host 127.0.0.1 --port $Port
