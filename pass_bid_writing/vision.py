from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import Settings
from .documents import export_docx_to_pdf


RENDERABLE_SUFFIXES = {".pdf", ".doc", ".docx"}


def extract_layout_profile(
    *,
    source_path: Path,
    settings: Settings,
    source_kind: str = "reference",
    max_pages: int = 4,
) -> dict[str, Any]:
    render = render_document_pages(source_path, settings=settings, max_pages=max_pages)
    return _analyze_images(
        settings=settings,
        render=render,
        source_path=source_path,
        analysis_type="layout_profile",
        source_kind=source_kind,
    )


def visual_check_document(
    *,
    target_path: Path,
    settings: Settings,
    reference_layout: dict[str, Any] | None = None,
    max_pages: int = 5,
) -> dict[str, Any]:
    render = render_document_pages(target_path, settings=settings, max_pages=max_pages)
    return _analyze_images(
        settings=settings,
        render=render,
        source_path=target_path,
        analysis_type="visual_check",
        source_kind="generated_draft",
        reference_layout=reference_layout,
    )


def render_document_pages(
    source_path: Path,
    *,
    settings: Settings,
    max_pages: int = 4,
    scale: float = 1.5,
) -> dict[str, Any]:
    source_path = source_path.expanduser().resolve()
    render_root = settings.render_dir / _safe_stem(source_path)
    render_root.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()
    pdf_path = source_path
    conversion: dict[str, Any] = {}
    if suffix in {".doc", ".docx"}:
        pdf_path = render_root / f"{source_path.stem}.pdf"
        conversion = export_docx_to_pdf(source_path, pdf_path)
        if conversion.get("status") != "ready":
            return {
                "status": "blocked",
                "source_path": str(source_path),
                "pdf_path": str(pdf_path),
                "conversion": conversion,
                "pages": [],
                "message": "DOCX could not be converted to PDF for visual analysis.",
            }
    elif suffix != ".pdf":
        return {
            "status": "unsupported",
            "source_path": str(source_path),
            "pages": [],
            "message": f"Visual rendering supports PDF/DOCX, got {source_path.suffix}.",
        }

    try:
        import fitz  # type: ignore
    except Exception as exc:
        return {
            "status": "blocked",
            "source_path": str(source_path),
            "pdf_path": str(pdf_path),
            "conversion": conversion,
            "pages": [],
            "message": f"PyMuPDF is required for visual rendering: {exc}",
        }

    try:
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        page_indexes = _sample_page_indexes(page_count, max_pages)
        pages: list[dict[str, Any]] = []
        for page_index in page_indexes:
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image_path = render_root / f"page-{page_index + 1:03d}.png"
            pix.save(str(image_path))
            pages.append(
                {
                    "page": page_index + 1,
                    "image_path": str(image_path),
                    "width": pix.width,
                    "height": pix.height,
                }
            )
        doc.close()
        return {
            "status": "ready",
            "source_path": str(source_path),
            "pdf_path": str(pdf_path),
            "conversion": conversion,
            "page_count": page_count,
            "sampled_pages": [item["page"] for item in pages],
            "pages": pages,
        }
    except Exception as exc:
        return {
            "status": "blocked",
            "source_path": str(source_path),
            "pdf_path": str(pdf_path),
            "conversion": conversion,
            "pages": [],
            "message": f"Failed to render PDF pages: {exc}",
        }


def _analyze_images(
    *,
    settings: Settings,
    render: dict[str, Any],
    source_path: Path,
    analysis_type: str,
    source_kind: str,
    reference_layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = settings.vision_provider
    model = settings.vision_model
    endpoint = _endpoint_for_provider(provider)
    base = {
        "source_path": str(source_path),
        "source_kind": source_kind,
        "analysis_type": analysis_type,
        "provider": provider,
        "model": model,
        "endpoint": endpoint,
        "render": render,
    }
    if render.get("status") != "ready":
        return {
            **base,
            "status": render.get("status", "blocked"),
            "profile": _local_layout_fallback(render, analysis_type=analysis_type),
            "message": render.get("message", "Document rendering was not ready."),
        }
    if settings.vision_enabled in {"0", "false", "off", "disabled", "none"}:
        return {
            **base,
            "status": "disabled",
            "profile": _local_layout_fallback(render, analysis_type=analysis_type),
            "message": "Vision analysis is disabled by PASS_BID_VISION_ENABLED.",
        }
    api_key = _api_key_for_provider(provider)
    if not api_key:
        return {
            **base,
            "status": "not_configured",
            "profile": _local_layout_fallback(render, analysis_type=analysis_type),
            "message": _missing_key_message(provider),
        }

    try:
        payload = _call_openai_compatible_vision(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
            render=render,
            analysis_type=analysis_type,
            reference_layout=reference_layout,
        )
        profile = _extract_json_object(payload)
        return {
            **base,
            "status": "ready",
            "profile": profile,
            "raw_response": payload,
        }
    except Exception as exc:
        return {
            **base,
            "status": "error",
            "profile": _local_layout_fallback(render, analysis_type=analysis_type),
            "message": str(exc),
        }


def _call_openai_compatible_vision(
    *,
    provider: str,
    model: str,
    api_key: str,
    endpoint: str,
    render: dict[str, Any],
    analysis_type: str,
    reference_layout: dict[str, Any] | None,
) -> dict[str, Any]:
    prompt = _prompt_for_analysis(analysis_type, reference_layout)
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for page in render.get("pages", [])[:6]:
        image_path = Path(str(page.get("image_path", "")))
        if not image_path.exists():
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(image_path)},
            }
        )
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": content},
        ],
        "temperature": 0.1,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
    }
    return _post_openai_compatible(endpoint=endpoint, api_key=api_key, body=body)


def _post_openai_compatible(
    *,
    endpoint: str,
    api_key: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(os.environ.get("PASS_BID_VISION_TIMEOUT", "90"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="ignore")
        if (
            exc.code in {400, 422}
            and "response_format" in body
            and "response_format" in body_text
        ):
            retry_body = dict(body)
            retry_body.pop("response_format", None)
            return _post_openai_compatible(endpoint=endpoint, api_key=api_key, body=retry_body)
        raise RuntimeError(f"Vision API HTTP {exc.code}: {body_text}") from exc


def _extract_json_object(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices:
        return {"raw_response": response, "parse_status": "no_choices"}
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        content = "\n".join(str(item.get("text", item)) for item in content)
    if isinstance(content, dict):
        return content
    text = str(content).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"raw_content": text, "parse_status": "not_json"}


def _prompt_for_analysis(
    analysis_type: str,
    reference_layout: dict[str, Any] | None,
) -> str:
    if analysis_type == "visual_check":
        reference_text = json.dumps(reference_layout or {}, ensure_ascii=False)[:3000]
        return (
            "你是技术标 Word/PDF 版式分析助手，只输出可解析的 JSON。"
            "请检查这些技术标导出 PDF 页面截图的正式观感。"
            "输出 JSON，字段包括 status, cover, toc, headers_footers, page_numbers, "
            "heading_hierarchy, tables, visual_findings, human_confirm_items。"
            "重点检查封面、目录、页眉页脚、页码、标题孤行、表格跨页、空白过大。"
            f"可参考的版式 profile: {reference_text}"
        )
    return (
        "你是技术标 Word/PDF 版式分析助手，只输出可解析的 JSON。"
        "请分析这些已通过技术标或招标文件页面截图的版式习惯。"
        "输出 JSON，字段包括 document_type, cover, toc, page_setup, fonts, "
        "heading_hierarchy, numbering, headers_footers, page_numbers, tables, "
        "spacing, style_rules, human_confirm_items。"
        "不要写长段解释，只输出结构化 JSON；不确定的内容放入 human_confirm_items。"
    )


def _local_layout_fallback(render: dict[str, Any], *, analysis_type: str) -> dict[str, Any]:
    pages = render.get("pages", [])
    return {
        "document_type": "unknown",
        "analysis_type": analysis_type,
        "page_samples": [
            {
                "page": item.get("page"),
                "width": item.get("width"),
                "height": item.get("height"),
                "image_path": item.get("image_path"),
            }
            for item in pages
        ],
        "style_rules": [],
        "visual_findings": [],
        "human_confirm_items": ["视觉模型未完成分析，需人工复核最终 PDF 观感。"],
    }


def _sample_page_indexes(page_count: int, max_pages: int) -> list[int]:
    if page_count <= 0:
        return []
    candidates = [0, 1, page_count // 2, page_count - 1]
    indexes: list[int] = []
    for idx in candidates:
        if 0 <= idx < page_count and idx not in indexes:
            indexes.append(idx)
        if len(indexes) >= max_pages:
            break
    return indexes


def _image_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _api_key_for_provider(provider: str) -> str:
    if os.environ.get("PASS_BID_VISION_API_KEY"):
        return os.environ["PASS_BID_VISION_API_KEY"]
    if provider == "aliyun_qwen":
        return os.environ.get("DASHSCOPE_API_KEY", "")
    if provider == "kimi":
        return os.environ.get("MOONSHOT_API_KEY", "")
    if provider == "doubao":
        return os.environ.get("ARK_API_KEY") or os.environ.get("VOLCENGINE_API_KEY", "")
    return ""


def _endpoint_for_provider(provider: str) -> str:
    if os.environ.get("PASS_BID_VISION_BASE_URL"):
        base = os.environ["PASS_BID_VISION_BASE_URL"].rstrip("/")
        return f"{base}/chat/completions" if not base.endswith("/chat/completions") else base
    if provider == "kimi":
        return "https://api.moonshot.cn/v1/chat/completions"
    if provider == "doubao":
        return "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    return "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def _missing_key_message(provider: str) -> str:
    if provider == "kimi":
        return "Vision API key missing: set MOONSHOT_API_KEY or PASS_BID_VISION_API_KEY."
    if provider == "doubao":
        return "Vision API key missing: set ARK_API_KEY/VOLCENGINE_API_KEY or PASS_BID_VISION_API_KEY."
    return "Vision API key missing: set DASHSCOPE_API_KEY or PASS_BID_VISION_API_KEY."


def _safe_stem(path: Path) -> str:
    stem = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", path.stem).strip(" ._")
    return stem or "document"
