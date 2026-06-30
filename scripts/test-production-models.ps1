$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

@'
import json
from pass_bid_writing.config import get_settings
from pass_bid_writing.model_router import ModelRouter

get_settings()
models = ModelRouter().status()
print(json.dumps(models, ensure_ascii=False, indent=2))

text = next(item for item in models if item["role"] == "text_master")
if not text["configured"]:
    raise SystemExit("DEEPSEEK_API_KEY is not configured.")

vision = [item for item in models if item["role"] in {"vision_primary", "vision_batch"}]
if not all(item["configured"] for item in vision):
    print("WARNING: Qwen visual roles are not configured; visual sources will become explicit human-review items.")

review = next(item for item in models if item["role"] == "vision_review")
if not review["configured"]:
    print("INFO: GLM review is optional and will only be used for flagged visual conflicts.")
'@ | py -3.12 -
