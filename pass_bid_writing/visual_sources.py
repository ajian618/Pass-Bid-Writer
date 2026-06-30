from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import get_settings
from .model_router import ModelRouter
from .vision import render_document_pages


VISUAL_ROLES = {"tender", "design_report", "budget", "drawing", "standard"}
DIRECT_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def build_visual_jobs(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for file_info in files:
        if file_info.get("is_duplicate"):
            continue
        suffix = str(file_info.get("suffix", "")).lower()
        if file_info.get("role") not in VISUAL_ROLES:
            continue
        if suffix not in DIRECT_IMAGE_SUFFIXES | {".pdf", ".doc", ".docx", ".dxf", ".dwg"}:
            continue
        jobs.append(
            {
                "job_id": f"visual-{len(jobs) + 1:03d}",
                "source_path": file_info["path"],
                "source_name": file_info["name"],
                "source_role": file_info["role"],
                "suffix": suffix,
                "status": "pending",
                "provider": "",
                "model": "",
                "images": [],
                "result": {},
                "error": "",
            }
        )
    return jobs


def analyze_visual_sources(run_id: int) -> dict[str, Any]:
    from .production import _save_run_state, get_run_state

    state = get_run_state(run_id)
    if state is None:
        raise ValueError(f"production run not found: {run_id}")
    router = ModelRouter()
    statuses = {item["role"]: item for item in router.status()}
    primary_ready = statuses["vision_primary"]["configured"]
    batch_ready = statuses["vision_batch"]["configured"]
    jobs = state.get("visual_jobs", [])
    state["visual_analysis"] = {
        "status": "running",
        "total": len(jobs),
        "completed": 0,
        "failed": 0,
        "needs_review": 0,
    }
    state["stage"] = "证据提取"
    state["stage_index"] = 3
    state["status"] = "analyzing_visuals"
    _save_run_state(run_id, state)

    if not jobs:
        return _finish_visual_analysis(run_id, state)
    if not primary_ready and not batch_ready:
        for job in jobs:
            job["status"] = "not_configured"
            job["error"] = "DASHSCOPE_API_KEY 未配置"
        state.setdefault("confirmations", []).append(
            {
                "category": "视觉模型未配置",
                "title": "千问视觉资料结构化未执行",
                "detail": "当前未配置 DASHSCOPE_API_KEY；扫描件、复杂表格和图纸中的信息未进入项目事实库。",
                "severity": "high",
                "affected_sections": ["全局"],
                "status": "open",
                "recommended_action": "配置百炼密钥后重新运行多模态分析，或由人工核对视觉资料。",
            }
        )
        return _finish_visual_analysis(run_id, state)

    for job in jobs:
        try:
            images = _job_images(job)
            job["images"] = [str(path) for path in images]
            if not images:
                raise RuntimeError("没有可供视觉模型读取的页面或预览图")
            complex_role = job["source_role"] in {"design_report", "budget", "drawing"}
            if complex_role and statuses["vision_batch"]["configured"]:
                try:
                    job["classification"] = router.complete_json(
                        role="vision_batch",
                        system="你是文件页面分类器，只描述页面类型和可见信息，不推断项目参数。",
                        prompt=json.dumps(
                            {
                                "任务": "按输入顺序分类页面",
                                "输出": {
                                    "pages": [
                                        {
                                            "input_index": 1,
                                            "page_type": "封面/目录/正文/表格/图纸/附件",
                                            "importance": "high/medium/low",
                                            "visible_titles": [],
                                        }
                                    ]
                                },
                            },
                            ensure_ascii=False,
                        ),
                        images=images[:8],
                        timeout=180,
                        max_tokens=1200,
                    )
                except Exception as exc:
                    job["classification_error"] = str(exc)
            role = "vision_primary" if complex_role else "vision_batch"
            if not statuses[role]["configured"]:
                role = "vision_primary" if primary_ready else "vision_batch"
            result = router.complete_json(
                role=role,
                system=(
                    "你是水利工程投标资料视觉结构化模型。只提取图像中明确可见的内容，"
                    "不得推断缺失数字。所有事实必须保留页码或图号、可见原文和置信度。"
                ),
                prompt=_visual_prompt(job),
                images=images[:8],
                timeout=240,
                max_tokens=2600,
            )
            job["provider"] = statuses[role]["provider"]
            job["model"] = statuses[role]["model"]
            job["result"] = result
            job["status"] = "ready"
            _merge_visual_facts(state, job, result)
            state.setdefault("model_runs", []).append(
                {
                    "role": role,
                    "provider": job["provider"],
                    "model": job["model"],
                    "task_type": "visual_evidence_extraction",
                    "section": "",
                    "input_basis": [job["source_path"]],
                    "status": "success",
                }
            )
            if _needs_review(result):
                job["status"] = "needs_review"
                _review_visual_job_if_configured(state, job, router, statuses)
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            state.setdefault("model_runs", []).append(
                {
                    "role": "vision_primary",
                    "provider": "aliyun_qwen",
                    "model": statuses["vision_primary"]["model"],
                    "task_type": "visual_evidence_extraction",
                    "section": "",
                    "input_basis": [job["source_path"]],
                    "status": "failed",
                    "error": str(exc),
                }
            )
        completed = sum(1 for item in jobs if item["status"] not in {"pending", "running"})
        state["visual_analysis"].update(
            {
                "completed": completed,
                "failed": sum(1 for item in jobs if item["status"] == "failed"),
                "needs_review": sum(1 for item in jobs if item["status"] == "needs_review"),
            }
        )
        _save_run_state(run_id, state)
    return _finish_visual_analysis(run_id, state)


def _job_images(job: dict[str, Any]) -> list[Path]:
    path = Path(job["source_path"])
    suffix = path.suffix.lower()
    if suffix in DIRECT_IMAGE_SUFFIXES:
        if suffix in {".tif", ".tiff"}:
            from PIL import Image

            output_dir = path.parent / ".production" / "previews"
            output_dir.mkdir(parents=True, exist_ok=True)
            output = output_dir / f"{path.stem}.png"
            with Image.open(path) as image:
                image.convert("RGB").save(output)
            return [output]
        return [path]
    if suffix in {".pdf", ".doc", ".docx"}:
        render = render_document_pages(path, settings=get_settings(), max_pages=8)
        if render.get("status") != "ready":
            raise RuntimeError(render.get("message", "文件页面渲染失败"))
        return [Path(item["image_path"]) for item in render.get("pages", [])]
    if suffix == ".dxf":
        return [_render_dxf_preview(path)]
    if suffix == ".dwg":
        raise RuntimeError("DWG需要设计处另存为PDF/DXF或提供预览图后再分析")
    return []


def _render_dxf_preview(source: Path) -> Path:
    try:
        import ezdxf  # type: ignore
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except Exception as exc:
        raise RuntimeError(f"DXF预览依赖未安装：{exc}") from exc
    output_dir = source.parent / ".production" / "previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.png"
    document = ezdxf.readfile(source)
    modelspace = document.modelspace()
    figure = plt.figure(figsize=(14, 10), dpi=150)
    axes = figure.add_axes([0.02, 0.02, 0.96, 0.96])
    axes.set_aspect("equal")
    axes.axis("off")
    Frontend(RenderContext(document), MatplotlibBackend(axes)).draw_layout(modelspace, finalize=True)
    figure.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return output


def _visual_prompt(job: dict[str, Any]) -> str:
    return json.dumps(
        {
            "任务": "将视觉资料转换成可追溯项目证据",
            "资料角色": job["source_role"],
            "文件名": job["source_name"],
            "页面分类结果": job.get("classification", {}),
            "输出字段": {
                "document_summary": "不超过300字",
                "facts": [
                    {
                        "key": "事实名称",
                        "value": "可见值",
                        "unit": "单位",
                        "page": "页面序号",
                        "figure": "图号或表号",
                        "bbox": [0, 0, 0, 0],
                        "excerpt": "可见原文",
                        "confidence": "0到1",
                    }
                ],
                "tables": [{"title": "表名", "page": "页码", "columns": [], "rows": []}],
                "drawings": [{"drawing_no": "图号", "title": "图名", "page": "页码", "visible_notes": []}],
                "conflicts": [{"field": "冲突字段", "visible_values": [], "pages": []}],
                "needs_human_review": ["无法确认的内容"],
            },
            "约束": ["不得补全看不清的数字", "不得把图例推断为项目事实", "必须输出JSON"],
        },
        ensure_ascii=False,
    )


def _merge_visual_facts(
    state: dict[str, Any],
    job: dict[str, Any],
    result: dict[str, Any],
) -> None:
    existing = {
        (
            str(item.get("key", "")),
            str(item.get("value", "")),
            str(item.get("source_path", "")),
            item.get("source_page"),
        )
        for item in state.get("facts", [])
    }
    for item in result.get("facts", [])[:200]:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", "")).strip()
        if not key or not value:
            continue
        page = _safe_int(item.get("page"))
        identity = (key, value, job["source_path"], page)
        if identity in existing:
            continue
        existing.add(identity)
        state.setdefault("facts", []).append(
            {
                "key": key,
                "value": value,
                "unit": str(item.get("unit", "")),
                "source_path": job["source_path"],
                "source_page": page,
                "source_figure": str(item.get("figure", "")),
                "source_bbox": item.get("bbox", []),
                "source_excerpt": str(item.get("excerpt", "")),
                "confidence": max(0, min(float(item.get("confidence", 0.5)), 1)),
                "status": "extracted",
                "extraction_model": job.get("model", ""),
            }
        )
    for conflict in result.get("conflicts", [])[:50]:
        state.setdefault("confirmations", []).append(
            {
                "category": "视觉资料冲突",
                "title": f"{job['source_name']}：{conflict.get('field', '识别结果冲突')}",
                "detail": json.dumps(conflict, ensure_ascii=False),
                "severity": "high",
                "affected_sections": ["全局"],
                "status": "open",
                "recommended_action": "对照来源页面和图号人工确认，不自动投票。",
            }
        )


def _needs_review(result: dict[str, Any]) -> bool:
    if result.get("conflicts") or result.get("needs_human_review"):
        return True
    return any(float(item.get("confidence", 1)) < 0.75 for item in result.get("facts", []))


def _review_visual_job_if_configured(
    state: dict[str, Any],
    job: dict[str, Any],
    router: ModelRouter,
    statuses: dict[str, dict[str, Any]],
) -> None:
    if not statuses["vision_review"]["configured"]:
        return
    review = router.complete_json(
        role="vision_review",
        system=(
            "你是视觉证据复核模型。独立读取原图并指出与主模型结果的差异。"
            "不得投票决定最终值，输出差异和建议人工核对位置。"
        ),
        prompt=json.dumps(
            {"主模型结果": job["result"], "任务": "独立复核关键数字、表格和图号"},
            ensure_ascii=False,
        ),
        images=[Path(path) for path in job.get("images", [])[:6]],
        timeout=240,
        max_tokens=2200,
    )
    difference = {
        "task": job["source_name"],
        "source_path": job["source_path"],
        "primary_model": job["model"],
        "review_model": statuses["vision_review"]["model"],
        "primary_result": job["result"],
        "review_result": review,
        "difference": review.get("differences", review.get("difference", review)),
        "status": "open",
    }
    state.setdefault("model_differences", []).append(difference)


def _finish_visual_analysis(run_id: int, state: dict[str, Any]) -> dict[str, Any]:
    from .production import _fact_section_keywords, _input_is_available, _save_run_state

    for section in state.get("sections", []):
        for fact in state.get("facts", []):
            if not fact.get("extraction_model"):
                continue
            if any(keyword in section.get("title", "") for keyword in _fact_section_keywords(fact.get("key", ""))):
                source_name = Path(str(fact.get("source_path", ""))).name or "视觉资料"
                basis = (
                    f"{fact.get('key')}：{fact.get('value')}{fact.get('unit', '')}"
                    f"（{source_name} 第{fact.get('source_page') or '—'}页）"
                )
                if basis not in section.setdefault("project_basis", []):
                    section["project_basis"].append(basis)
        section["missing_inputs"] = [
            item
            for item in section.get("required_inputs", [])
            if not _input_is_available(
                item,
                state.get("facts", []),
                state.get("requirements", {}),
                state.get("standards", []),
            )
        ]
        if section.get("status") != "generated":
            section["status"] = "ready" if not section["missing_inputs"] else "needs_input"
            section["completion"] = max(
                5,
                min(
                    90,
                    20
                    + len(section.get("project_basis", [])) * 8
                    + len(section.get("reference_basis", [])) * 5
                    - len(section["missing_inputs"]) * 5,
                ),
            )

    state["visual_analysis"]["status"] = "completed"
    state["stage"] = "编制任务书确认"
    state["stage_index"] = 6
    state["status"] = "awaiting_confirmation"
    state["metrics"]["fact_count"] = len(state.get("facts", []))
    state["metrics"]["open_confirmations"] = sum(
        1 for item in state.get("confirmations", []) if item.get("status") == "open"
    )
    state["metrics"]["high_risks"] = sum(
        1
        for item in state.get("confirmations", [])
        if item.get("status") == "open" and item.get("severity") == "high"
    )
    _save_run_state(run_id, state)
    return state


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None
