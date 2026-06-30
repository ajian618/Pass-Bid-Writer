param([int]$Port = 8000, [switch]$NoBrowser)

Write-Warning "This compatibility entry point is deprecated. Use start.ps1 at the repository root."
& (Join-Path (Split-Path -Parent $PSScriptRoot) "start.ps1") -Port $Port -NoBrowser:$NoBrowser
