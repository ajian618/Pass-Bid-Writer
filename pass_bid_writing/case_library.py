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
        return db.search_case_pairs(conn, limit=limit)
