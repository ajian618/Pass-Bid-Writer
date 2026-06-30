from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelEndpoint:
    role: str
    provider: str
    model: str
    base_url: str
    api_key_env: str
    modalities: tuple[str, ...]

    @property
    def configured(self) -> bool:
        return bool(os.environ.get(self.api_key_env, "").strip())


class ModelRouter:
    """Role-based domestic model router with no silent cross-provider voting."""

    def __init__(self) -> None:
        deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if deepseek_base.endswith("/anthropic"):
            deepseek_base = deepseek_base[: -len("/anthropic")]
        self.endpoints = {
            "text_master": ModelEndpoint(
                role="text_master",
                provider="deepseek",
                model=os.environ.get("PASS_BID_TEXT_MODEL", "deepseek-v4-pro"),
                base_url=deepseek_base,
                api_key_env="DEEPSEEK_API_KEY",
                modalities=("text",),
            ),
            "vision_primary": ModelEndpoint(
                role="vision_primary",
                provider="aliyun_qwen",
                model=os.environ.get("PASS_BID_VISION_MODEL", "qwen3.7-plus-2026-05-26"),
                base_url=os.environ.get(
                    "PASS_BID_VISION_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
                api_key_env="DASHSCOPE_API_KEY",
                modalities=("text", "image"),
            ),
            "vision_batch": ModelEndpoint(
                role="vision_batch",
                provider="aliyun_qwen",
                model=os.environ.get("PASS_BID_BATCH_MODEL", "qwen3.6-flash-2026-04-16"),
                base_url=os.environ.get(
                    "PASS_BID_VISION_BASE_URL",
                    "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
                api_key_env="DASHSCOPE_API_KEY",
                modalities=("text", "image"),
            ),
            "vision_review": ModelEndpoint(
                role="vision_review",
                provider="zhipu",
                model=os.environ.get("PASS_BID_REVIEW_VISION_MODEL", "glm-5v-turbo"),
                base_url=os.environ.get(
                    "ZHIPU_BASE_URL",
                    "https://open.bigmodel.cn/api/paas/v4",
                ),
                api_key_env="ZHIPU_API_KEY",
                modalities=("text", "image"),
            ),
        }

    def status(self) -> list[dict[str, Any]]:
        return [
            {
                "role": endpoint.role,
                "provider": endpoint.provider,
                "model": endpoint.model,
                "configured": endpoint.configured,
                "modalities": list(endpoint.modalities),
            }
            for endpoint in self.endpoints.values()
        ]

    def complete_json(
        self,
        *,
        role: str,
        system: str,
        prompt: str,
        images: list[Path] | None = None,
        timeout: int = 180,
        max_tokens: int | None = None,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        endpoint = self.endpoints[role]
        api_key = os.environ.get(endpoint.api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"{endpoint.api_key_env} is not configured for {role}")
        content: Any = prompt
        if images:
            blocks: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for image in images:
                mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
                encoded = base64.b64encode(image.read_bytes()).decode("ascii")
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    }
                )
            content = blocks
        payload: dict[str, Any] = {
            "model": endpoint.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if endpoint.provider == "deepseek":
            if os.environ.get("PASS_BID_DEEPSEEK_THINKING", "false").lower() in {
                "1",
                "true",
                "on",
            }:
                payload["reasoning_effort"] = "high"
                payload["thinking"] = {"type": "enabled"}
            else:
                payload["thinking"] = {"type": "disabled"}
        request = urllib.request.Request(
            endpoint.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        raw: dict[str, Any] | None = None
        last_error = ""
        for attempt in range(max(1, max_attempts)):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                last_error = f"{endpoint.provider} returned HTTP {exc.code}: {detail[:600]}"
                if exc.code not in {408, 409, 429, 500, 502, 503, 504} or attempt + 1 >= max_attempts:
                    raise RuntimeError(last_error) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = f"{endpoint.provider} request failed: {exc}"
                if attempt + 1 >= max_attempts:
                    raise RuntimeError(last_error) from exc
            time.sleep(min(2 ** attempt, 4))
        if raw is None:
            raise RuntimeError(last_error or f"{endpoint.provider} request failed")
        text = raw["choices"][0]["message"].get("content", "")
        if isinstance(text, list):
            text = "".join(str(item.get("text", "")) for item in text if isinstance(item, dict))
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            cleaned = str(text).strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
            finish_reason = raw.get("choices", [{}])[0].get("finish_reason", "unknown")
            excerpt = re.sub(r"\s+", " ", cleaned)[:300]
            raise RuntimeError(
                f"{endpoint.model} returned invalid JSON "
                f"(finish_reason={finish_reason}, chars={len(cleaned)}, excerpt={excerpt!r})"
            ) from exc
