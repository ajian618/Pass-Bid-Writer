param(
  [ValidateSet("aliyun_qwen", "kimi", "doubao")]
  [string]$Provider = "aliyun_qwen",
  [string]$Model = "",
  [string]$ApiKey = "",
  [string]$BaseUrl = "",
  [switch]$Disable
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"

if (-not $Model) {
  if ($Provider -eq "kimi") {
    $Model = "kimi-k2.6"
  } elseif ($Provider -eq "doubao") {
    $Model = "doubao-seed-1-6-vision"
  } else {
    $Model = "qwen3.7-plus"
  }
}

if (-not $BaseUrl) {
  if ($Provider -eq "kimi") {
    $BaseUrl = "https://api.moonshot.cn/v1"
  } elseif ($Provider -eq "doubao") {
    $BaseUrl = "https://ark.cn-beijing.volces.com/api/v3"
  } else {
    $BaseUrl = "https://dashscope.aliyuncs.com/compatible-mode/v1"
  }
}

if (-not $Disable -and -not $ApiKey) {
  $secure = Read-Host "Enter API key for $Provider" -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    if ($bstr -ne [IntPtr]::Zero) {
      [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
  }
}

$updates = [ordered]@{
  PASS_BID_VISION_ENABLED = $(if ($Disable) { "disabled" } else { "auto" })
  PASS_BID_VISION_PROVIDER = $Provider
  PASS_BID_VISION_MODEL = $Model
  PASS_BID_VISION_BASE_URL = $BaseUrl
}

if (-not $Disable) {
  if ($Provider -eq "kimi") {
    $updates["MOONSHOT_API_KEY"] = $ApiKey
  } elseif ($Provider -eq "doubao") {
    $updates["ARK_API_KEY"] = $ApiKey
  } else {
    $updates["DASHSCOPE_API_KEY"] = $ApiKey
  }
}

$existing = [ordered]@{}
if (Test-Path -LiteralPath $envPath) {
  foreach ($line in [System.IO.File]::ReadAllLines($envPath, [System.Text.Encoding]::UTF8)) {
    if ($line.Trim() -and -not $line.TrimStart().StartsWith("#") -and $line.Contains("=")) {
      $key, $value = $line.Split("=", 2)
      $existing[$key.Trim()] = $value
    }
  }
}

foreach ($key in $updates.Keys) {
  $existing[$key] = $updates[$key]
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# Local pass-bid-writing configuration. Do not commit this file.")
foreach ($key in $existing.Keys) {
  $value = [string]$existing[$key]
  $escaped = $value.Replace('"', '\"')
  $lines.Add("$key=""$escaped""")
}

[System.IO.File]::WriteAllText($envPath, ($lines -join [Environment]::NewLine) + [Environment]::NewLine, $Utf8NoBom)

Write-Host "Vision configuration written: $envPath"
Write-Host "Provider: $Provider"
Write-Host "Model: $Model"
Write-Host "Base URL: $BaseUrl"
if ($Disable) {
  Write-Host "Vision analysis disabled."
} else {
  Write-Host "API key saved locally. This file is ignored by Git."
}
