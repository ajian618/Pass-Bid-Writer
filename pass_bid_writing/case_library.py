from __future__ import annotations

from pathlib import Path
from typing import Any

from . import db
from .analysis import extract_case_patterns, extract_outline, extract_tender_requirements
from .config import ensure_storage_dirs, get_settings
from .projects import scan_single_project, select_project_files
from .text import extract_text
from .vision import extract_layout_profile


def ingest_case_folder(
    project_dir: str,
    *,
    project_type: str = "",
    region: str = "浙江",
    tags: str = "",
    analyze_layout: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    ensure_storage_dirs(settings)
    db.init_db(settings.database_path)
    project_path = Path(project_dir).expanduser().resolve()
    project = scan_single_project(project_path, project_kind="passed_case")
    selected = select_project_files(project)
    tender_file = selected.get("tender")
    bid_file = selected.get("accepted_bid")
    if not tender_file or not bid_file:
        raise ValueError("案例资料夹必须同时包含招标文件和已通过技术标")

    tender = extract_text(str(tender_file["path"]))
    bid = extract_text(str(bid_file["path"]))
    requirements = extract_tender_requirements(
        tender["text"],
        source_path=tender.get("path", ""),
    )
    outline = extract_outline(bid["text"])
    patterns = extract_case_patterns(tender["text"], bid["text"])
    layout_result: dict[str, Any] | None = None
    layout_profile_id: int | None = None
    if analyze_layout:
        layout_result = extract_layout_profile(
            source_path=Path(str(bid_file["path"])),
            settings=settings,
            source_kind="accepted_bid",
        )
        with db.db_session(settings.database_path) as conn:
            layout_profile_id = db.create_layout_profile(
                conn,
                source_path=str(bid_file["path"]),
                source_kind="accepted_bid",
                provider=str(layout_result.get("provider", "")),
                model=str(layout_result.get("model", "")),
                status=str(layout_result.get("status", "")),
                profile=layout_result.get("profile", {}),
                render=layout_result.get("render", {}),
            )
        layout_result["layout_profile_id"] = layout_profile_id
        patterns["layout_profile_id"] = layout_profile_id
        patterns["layout_status"] = layout_result.get("status")

    with db.db_session(settings.database_path) as conn:
        project_id = db.create_or_update_project(
            conn,
            name=str(project.get("name", "")),
            project_kind="passed_case",
            project_dir=str(project_path),
            summary=project,
        )
        for item in project.get("files", []):
            db.upsert_project_file(
                conn,
                project_id=project_id,
                file_path=str(item.get("path", "")),
                file_name=str(item.get("name", "")),
                suffix=str(item.get("suffix", "")),
                role=str(item.get("role", "attachment")),
                confidence=float(item.get("confidence", 0)),
                metadata=item,
            )
        case_id = db.create_case_pair(
            conn,
            title=project.get("name", "") or Path(str(bid_file["path"])).stem,
            project_type=project_type,
            region=region,
            tags=tags or "passed_case,technical_bid",
            tender_path=tender.get("path", ""),
            bid_path=bid.get("path", ""),
            tender_text=tender["text"],
            bid_text=bid["text"],
            outline=outline,
            requirements=requirements,
            patterns=patterns,
            project_dir=str(project_path),
            layout_profile_id=layout_profile_id,
        )
        db.create_lesson(
            conn,
            title=f"{project.get('name', '')} 通过制写作与版式模式",
            lesson="; ".join(patterns.get("style_notes", [])),
            scope="pass_bid_writing",
            tags=tags or "case,pass-fail,technical,layout",
            source="passed_case_folder",
            case_id=case_id,
        )
        saved = db.get_case_pair(conn, case_id)
    return {
        "project_id": project_id,
        "case": saved,
        "selected": selected,
        "layout_profile": layout_result,
        "summary": {
            "tender_chars": len(tender["text"]),
            "bid_chars": len(bid["text"]),
            "outline_count": len(outline),
            "requirement_count": requirements.get("requirement_count", 0),
            "scene_terms": patterns.get("scene_terms", []),
        },
    }


def list_cases(limit: int = 100) -> list[dict[str, Any]]:
    settings = get_settings()
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        cases = db.search_case_pairs(conn, limit=limit, include_disabled=True)
    return [_case_summary(case) for case in cases]


def get_case(case_id: int) -> dict[str, Any]:
    settings = get_settings()
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        case = db.get_case_pair(conn, case_id)
    if case is None:
        raise ValueError(f"case not found: {case_id}")
    return _case_detail(case)


def update_case(case_id: int, changes: dict[str, Any]) -> dict[str, Any]:
    current = get_case(case_id)
    review_status = str(changes.get("review_status", current["review_status"]))
    if review_status not in {"pending_review", "confirmed", "needs_correction"}:
        raise ValueError("不支持的案例审核状态")
    outline = _normalize_outline(changes.get("outline", current["outline"]))
    scene_terms = _string_list(changes.get("scene_terms", current["scene_terms"]), limit=80)
    style_notes = _string_list(changes.get("style_notes", current["style_notes"]), limit=30)
    snippets = _normalize_snippets(
        changes.get("reusable_snippets", current["reusable_snippets"])
    )
    patterns = dict(current.get("patterns", {}))
    patterns.update(
        {
            "outline": outline,
            "scene_terms": scene_terms,
            "style_notes": style_notes,
            "reusable_snippets": snippets,
        }
    )
    settings = get_settings()
    with db.db_session(settings.database_path) as conn:
        saved = db.update_case_pair(
            conn,
            case_id,
            title=str(changes.get("title", current["title"])).strip() or current["title"],
            project_type=str(changes.get("project_type", current["project_type"])).strip(),
            region=str(changes.get("region", current["region"])).strip(),
            tags=str(changes.get("tags", current["tags"])).strip(),
            outline=outline,
            patterns=patterns,
            enabled=bool(changes.get("enabled", current["enabled"])),
            review_status=review_status,
            review_notes=str(changes.get("review_notes", current["review_notes"])).strip(),
        )
    if saved is None:
        raise ValueError(f"case not found: {case_id}")
    return _case_detail(saved)


def _case_summary(case: dict[str, Any]) -> dict[str, Any]:
    patterns = case.get("patterns", {}) or {}
    outline = patterns.get("outline") or case.get("outline") or []
    return {
        "id": int(case["id"]),
        "title": case.get("title", ""),
        "project_type": case.get("project_type", ""),
        "region": case.get("region", ""),
        "tags": case.get("tags", ""),
        "enabled": bool(case.get("enabled", 1)),
        "review_status": case.get("review_status", "pending_review"),
        "review_notes": case.get("review_notes", ""),
        "outline_count": len(outline),
        "scene_term_count": len(patterns.get("scene_terms", [])),
        "snippet_count": len(patterns.get("reusable_snippets", [])),
        "style_note_count": len(patterns.get("style_notes", [])),
        "layout_status": patterns.get("layout_status", ""),
        "updated_at": case.get("updated_at", ""),
    }


def _case_detail(case: dict[str, Any]) -> dict[str, Any]:
    patterns = case.get("patterns", {}) or {}
    outline = patterns.get("outline") or case.get("outline") or []
    return {
        **_case_summary(case),
        "project_dir": case.get("project_dir", ""),
        "tender_path": case.get("tender_path", ""),
        "bid_path": case.get("bid_path", ""),
        "layout_profile_id": case.get("layout_profile_id"),
        "outline": outline,
        "scene_terms": patterns.get("scene_terms", []),
        "reusable_snippets": patterns.get("reusable_snippets", []),
        "style_notes": patterns.get("style_notes", []),
        "patterns": patterns,
        "requirements": case.get("requirements", {}),
        "created_at": case.get("created_at", ""),
    }


def _normalize_outline(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value if isinstance(value, list) else [], start=1):
        if isinstance(item, str):
            title = item.strip()
            level = 1
        elif isinstance(item, dict):
            title = str(item.get("title", "")).strip()
            level = max(1, min(6, int(item.get("level", 1) or 1)))
        else:
            continue
        if title:
            result.append({"level": level, "title": title, "order": index})
    if not result:
        raise ValueError("案例目录至少保留一个有效章节")
    return result[:200]


def _string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result[:limit]


def _normalize_snippets(value: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword", "")).strip() or "案例措辞"
        text = str(item.get("text", "")).strip()
        if text:
            result.append({"keyword": keyword[:80], "text": text[:2000]})
    return result[:50]
