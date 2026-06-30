from __future__ import annotations

import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def build_drawing_registry(files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pair original DWGs with user-exported PDFs and create explicit gaps."""
    dwgs = [item for item in files if str(item.get("suffix", "")).lower() == ".dwg"]
    pdfs = [
        item
        for item in files
        if str(item.get("suffix", "")).lower() == ".pdf"
        and item.get("role") == "drawing"
    ]
    drawings: list[dict[str, Any]] = []
    confirmations: list[dict[str, Any]] = []
    used_pdf_paths: set[str] = set()

    for index, dwg in enumerate(dwgs, start=1):
        matched, score = _best_pdf_match(dwg, pdfs)
        if matched and score >= 0.55:
            used_pdf_paths.add(str(matched["path"]))
            drawings.append(
                _drawing_record(
                    key=f"dwg-{index:03d}",
                    source_dwg=dwg,
                    source_pdf=matched,
                    match_score=score,
                )
            )
        else:
            drawings.append(
                _drawing_record(
                    key=f"dwg-{index:03d}",
                    source_dwg=dwg,
                    source_pdf=None,
                    match_score=0,
                )
            )
            confirmations.append(
                {
                    "category": "图纸待转换",
                    "title": f"{dwg['name']} 尚无对应PDF",
                    "detail": "V1不直接解析DWG。请使用AutoCAD手动导出PDF并上传到本项目。",
                    "severity": "high",
                    "affected_sections": ["施工总体布置", "主要施工方案"],
                    "status": "open",
                    "recommended_action": "上传同名或相近文件名的图纸PDF后重新分析资料。",
                    "source_path": dwg["path"],
                }
            )

    for index, pdf in enumerate(pdfs, start=1):
        if str(pdf["path"]) in used_pdf_paths:
            continue
        drawings.append(
            _drawing_record(
                key=f"pdf-{index:03d}",
                source_dwg=None,
                source_pdf=pdf,
                match_score=0,
            )
        )
    return drawings, confirmations


def merge_visual_drawings(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand PDF-level drawing records into page-level, reviewable assets."""
    registry = list(state.get("drawings", []))
    by_pdf = {
        str(item.get("source_pdf_path", "")): item
        for item in registry
        if item.get("source_pdf_path")
    }
    visual_jobs = [
        job
        for job in state.get("visual_jobs", [])
        if job.get("source_role") == "drawing" and job.get("suffix") == ".pdf"
    ]
    analyzable_sources = {
        str(job.get("source_path", ""))
        for job in visual_jobs
        if job.get("images") or job.get("result")
    }
    expanded: list[dict[str, Any]] = [
        item
        for item in registry
        if not item.get("source_pdf_path")
        or str(item.get("source_pdf_path", "")) not in analyzable_sources
    ]
    for job in visual_jobs:
        if not (job.get("images") or job.get("result")):
            continue
        source = str(job.get("source_path", ""))
        base = by_pdf.get(source) or _drawing_record(
            key=f"pdf-{len(expanded) + 1:03d}",
            source_dwg=None,
            source_pdf={
                "path": source,
                "name": job.get("source_name", Path(source).name),
            },
            match_score=0,
        )
        detected = list(job.get("result", {}).get("drawings", []))
        if not detected:
            detected = [
                {
                    "drawing_no": "",
                    "title": Path(source).stem,
                    "page": page_index,
                    "visible_notes": [],
                }
                for page_index, _ in enumerate(job.get("images", []), start=1)
            ]
        for page_index, item in enumerate(detected, start=1):
            page = _safe_int(item.get("page")) or page_index
            expanded.append(
                {
                    **base,
                    "drawing_id": f"{base['drawing_id']}-p{page:03d}",
                    "source_page": page,
                    "drawing_no": str(item.get("drawing_no", "")).strip(),
                    "title": str(item.get("title", "")).strip() or Path(source).stem,
                    "caption": str(item.get("title", "")).strip() or Path(source).stem,
                    "visible_notes": item.get("visible_notes", []),
                    "confidence": float(item.get("confidence", 0.75) or 0.75),
                    "status": "pending_confirmation",
                    "preview_path": _job_preview(job, page),
                }
            )
    state["drawings"] = _dedupe_drawings(expanded)
    return state["drawings"]


def update_drawing_asset(
    state: dict[str, Any],
    drawing_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    drawing = next(
        (item for item in state.get("drawings", []) if item.get("drawing_id") == drawing_id),
        None,
    )
    if drawing is None:
        raise ValueError(f"drawing not found: {drawing_id}")
    for key in (
        "drawing_no",
        "title",
        "caption",
        "placement",
        "applicable_sections",
        "crop",
        "status",
        "confirmed_at",
    ):
        if key in updates:
            drawing[key] = updates[key]
    if drawing.get("status") == "confirmed":
        drawing["confirmed_at"] = updates.get("confirmed_at", "")
    return drawing


def render_confirmed_drawing(
    drawing: dict[str, Any],
    output_dir: Path,
    *,
    dpi: int = 300,
) -> Path:
    source = Path(str(drawing.get("source_pdf_path", "")))
    if not source.exists():
        raise ValueError(f"drawing PDF not found: {source}")
    page_number = max(1, int(drawing.get("source_page") or 1))
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{_safe_name(drawing.get('drawing_id', source.stem))}.png"
    try:
        import fitz  # type: ignore
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(f"图纸渲染依赖不可用：{exc}") from exc
    document = fitz.open(str(source))
    if page_number > document.page_count:
        document.close()
        raise ValueError(f"图纸PDF没有第{page_number}页")
    page = document.load_page(page_number - 1)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    temp = output.with_suffix(".full.png")
    pix.save(str(temp))
    document.close()
    crop = drawing.get("crop") or {}
    if crop and all(key in crop for key in ("x", "y", "width", "height")):
        with Image.open(temp) as image:
            x = _crop_value(crop["x"], image.width)
            y = _crop_value(crop["y"], image.height)
            width = _crop_value(crop["width"], image.width)
            height = _crop_value(crop["height"], image.height)
            right = min(image.width, max(x + 1, x + width))
            bottom = min(image.height, max(y + 1, y + height))
            image.crop((x, y, right, bottom)).save(output)
        temp.unlink(missing_ok=True)
    else:
        shutil.move(str(temp), str(output))
    return output


def _drawing_record(
    *,
    key: str,
    source_dwg: dict[str, Any] | None,
    source_pdf: dict[str, Any] | None,
    match_score: float,
) -> dict[str, Any]:
    return {
        "drawing_id": key,
        "source_dwg_path": str((source_dwg or {}).get("path", "")),
        "source_dwg_name": str((source_dwg or {}).get("name", "")),
        "source_pdf_path": str((source_pdf or {}).get("path", "")),
        "source_pdf_name": str((source_pdf or {}).get("name", "")),
        "match_score": round(match_score, 3),
        "source_page": None,
        "drawing_no": "",
        "title": Path(str((source_pdf or source_dwg or {}).get("name", "图纸"))).stem,
        "caption": "",
        "crop": {},
        "applicable_sections": [],
        "placement": "inline",
        "preview_path": "",
        "confidence": 0,
        "status": "pending_analysis" if source_pdf else "missing_pdf",
        "confirmed_at": "",
    }


def _best_pdf_match(
    dwg: dict[str, Any],
    pdfs: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float]:
    source_key = _normalized_stem(str(dwg.get("name", "")))
    best = None
    best_score = 0.0
    for pdf in pdfs:
        score = SequenceMatcher(
            None,
            source_key,
            _normalized_stem(str(pdf.get("name", ""))),
        ).ratio()
        if score > best_score:
            best = pdf
            best_score = score
    return best, best_score


def _normalized_stem(value: str) -> str:
    stem = Path(value).stem.lower()
    stem = re.sub(r"(图纸|施工图|设计图|cad|pdf|dwg|最终版|送审版)", "", stem)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", stem)


def _job_preview(job: dict[str, Any], page: int) -> str:
    images = list(job.get("images", []))
    page_marker = f"page-{page:03d}"
    for image in images:
        path = Path(str(image))
        if page_marker in path.name and "tile-" not in path.name:
            return str(path)
    return str(images[page - 1]) if 0 < page <= len(images) else ""


def _dedupe_drawings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for item in items:
        key = (
            str(item.get("source_pdf_path", "")),
            _safe_int(item.get("source_page")),
            str(item.get("drawing_no", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _crop_value(value: Any, total: int) -> int:
    number = float(value)
    if 0 <= number <= 1:
        number *= total
    return max(0, min(total, round(number)))


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_name(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", str(value)).strip("_") or "drawing"
