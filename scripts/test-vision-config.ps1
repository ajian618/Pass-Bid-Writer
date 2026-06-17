$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

@'
import json
from pathlib import Path

import fitz

from pass_bid_writing.config import ensure_storage_dirs, get_settings
from pass_bid_writing.vision import extract_layout_profile


settings = get_settings()
ensure_storage_dirs(settings)
pdf_path = settings.vision_dir / "vision-config-smoke-test.pdf"

doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "Pass Bid Writer vision smoke test")
page.insert_text((72, 110), "This generated PDF is used only to verify Bailian/Kimi/Doubao API connectivity.")
doc.save(str(pdf_path))
doc.close()

result = extract_layout_profile(
    source_path=pdf_path,
    settings=settings,
    source_kind="vision_config_smoke_test",
    max_pages=1,
)

summary = {
    "status": result.get("status"),
    "provider": result.get("provider"),
    "model": result.get("model"),
    "endpoint": result.get("endpoint"),
    "message": result.get("message", ""),
    "profile_keys": sorted((result.get("profile") or {}).keys()),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))

if result.get("status") != "ready":
    raise SystemExit("Vision API smoke test did not return status=ready.")
'@ | py -3.12 -
