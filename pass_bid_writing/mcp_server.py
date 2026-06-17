from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import db
from .analysis import (
    build_response_matrix,
    extract_case_patterns,
    extract_outline,
    extract_tender_requirements,
    generate_outline,
)
from .config import ensure_storage_dirs, get_settings
from .documents import check_docx_compliance, export_docx_to_pdf, generate_docx, safe_filename
from .projects import resolve_projects_root, scan_projects, scan_single_project, select_project_files
from .text import compact_text, extract_text
from .vision import extract_layout_profile, visual_check_document


mcp = FastMCP(
    "pass-bid-writing",
    instructions=(
        "Standalone tools for Hermes-centered pass/fail technical bid writing. "
        "Use these tools to ingest accepted tender/bid case pairs, extract tender "
        "requirements, build response matrices, retrieve accepted writing patterns, "
        "generate editable DOCX drafts, check compliance, and export PDFs. Keep this "
        "workflow separate from bid-review/scoring tools."
    ),
)


def _settings():
    settings = get_settings()
    ensure_storage_dirs(settings)
    db.init_db(settings.database_path)
    return settings


def _resolve_path(value: str, *, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _store_project(conn, project: dict[str, Any]) -> int:
    project_id = db.create_or_update_project(
        conn,
        name=str(project.get("name", "")),
        project_kind=str(project.get("project_kind", "unknown")),
        project_dir=str(project.get("project_dir", "")),
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
    return project_id


def _store_layout_profile(
    *,
    settings,
    source_path: Path,
    source_kind: str,
) -> dict[str, Any]:
    result = extract_layout_profile(
        source_path=source_path,
        settings=settings,
        source_kind=source_kind,
    )
    with db.db_session(settings.database_path) as conn:
        layout_profile_id = db.create_layout_profile(
            conn,
            source_path=str(source_path),
            source_kind=source_kind,
            provider=str(result.get("provider", "")),
            model=str(result.get("model", "")),
            status=str(result.get("status", "")),
            profile=result.get("profile", {}),
            render=result.get("render", {}),
        )
    result["layout_profile_id"] = layout_profile_id
    return result


def _load_layout_profile(settings, layout_profile_id: int | None) -> dict[str, Any] | None:
    if layout_profile_id is None:
        return None
    with db.db_session(settings.database_path) as conn:
        record = db.get_layout_profile(conn, int(layout_profile_id))
    if not record:
        raise ValueError(f"layout_profile not found: {layout_profile_id}")
    return record.get("profile", {})


@mcp.tool()
def writing_scan_projects(root: str = "projects") -> dict[str, Any]:
    """
    Scan local project folders.

    Recommended layout:
    projects/passed_cases/<项目名>/ for accepted cases, and
    projects/new_tenders/<项目名>/ for tenders to draft. Aliases passed/unpassed
    are also recognized.
    """
    settings = _settings()
    root_path = resolve_projects_root(root, workspace_root=settings.root_dir, default_root=settings.projects_dir)
    return scan_projects(root_path)


@mcp.tool()
def writing_extract_layout_profile(
    file_path: str,
    source_kind: str = "reference",
) -> dict[str, Any]:
    """Render a PDF/DOCX and ask the configured vision model for a layout profile."""
    settings = _settings()
    source = _resolve_path(file_path, base=settings.root_dir)
    if not source.exists():
        raise ValueError(f"file_path not found: {source}")
    return _store_layout_profile(settings=settings, source_path=source, source_kind=source_kind)


@mcp.tool()
def writing_ingest_passed_case(
    project_dir: str,
    auto_visual: bool = True,
    project_type: str = "",
    region: str = "浙江",
    tags: str = "",
) -> dict[str, Any]:
    """
    Learn one accepted project folder from projects/passed_cases/<项目名>/.

    The folder may contain files directly. The tool chooses the tender file and
    accepted technical bid by filename/content-role heuristics, then stores text,
    writing patterns, and an optional vision layout profile.
    """
    settings = _settings()
    project_path = _resolve_path(project_dir, base=settings.root_dir)
    project = scan_single_project(project_path, project_kind="passed_case")
    selected = select_project_files(project)
    tender_file = selected.get("tender")
    bid_file = selected.get("accepted_bid")
    if not tender_file or not bid_file:
        raise ValueError("passed case needs both a tender file and an accepted technical bid file")

    tender = extract_text(str(tender_file["path"]))
    bid = extract_text(str(bid_file["path"]))
    requirements = extract_tender_requirements(tender["text"], source_path=tender.get("path", ""))
    outline = extract_outline(bid["text"])
    patterns = extract_case_patterns(tender["text"], bid["text"])
    layout_result: dict[str, Any] | None = None
    layout_profile_id: int | None = None
    if auto_visual:
        layout_result = _store_layout_profile(
            settings=settings,
            source_path=Path(str(bid_file["path"])),
            source_kind="accepted_bid",
        )
        layout_profile_id = int(layout_result["layout_profile_id"])
        patterns["layout_profile_id"] = layout_profile_id
        patterns["layout_status"] = layout_result.get("status")

    with db.db_session(settings.database_path) as conn:
        project_id = _store_project(conn, project)
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


@mcp.tool()
def writing_prepare_new_tender(
    project_dir: str,
    auto_visual: bool = True,
) -> dict[str, Any]:
    """
    Prepare one new tender folder from projects/new_tenders/<项目名>/.

    The tool chooses the tender file, extracts requirements, builds a response
    matrix, and optionally stores a vision layout profile for format requirements.
    """
    settings = _settings()
    project_path = _resolve_path(project_dir, base=settings.root_dir)
    project = scan_single_project(project_path, project_kind="new_tender")
    selected = select_project_files(project)
    tender_file = selected.get("tender")
    if not tender_file:
        raise ValueError("new tender project needs at least one tender/source document")

    tender = extract_text(str(tender_file["path"]))
    requirements = extract_tender_requirements(tender["text"], source_path=tender.get("path", ""))
    response_matrix = build_response_matrix(requirements)
    layout_result: dict[str, Any] | None = None
    if auto_visual:
        layout_result = _store_layout_profile(
            settings=settings,
            source_path=Path(str(tender_file["path"])),
            source_kind="new_tender",
        )
    with db.db_session(settings.database_path) as conn:
        project_id = _store_project(conn, project)
    return {
        "project_id": project_id,
        "project": project,
        "selected": selected,
        "requirements": requirements,
        "response_matrix": response_matrix,
        "layout_profile": layout_result,
        "outputs_dir": str(project_path / "outputs"),
    }


@mcp.tool()
def writing_visual_check_document(
    docx_path: str,
    layout_profile_id: int | None = None,
) -> dict[str, Any]:
    """Render a generated DOCX/PDF and run vision-based final PDF appearance checks."""
    settings = _settings()
    source = _resolve_path(docx_path, base=settings.root_dir)
    if not source.exists():
        raise ValueError(f"docx_path not found: {source}")
    reference_layout = _load_layout_profile(settings, layout_profile_id)
    result = visual_check_document(
        target_path=source,
        settings=settings,
        reference_layout=reference_layout,
    )
    with db.db_session(settings.database_path) as conn:
        analysis_id = db.create_visual_analysis(
            conn,
            target_path=str(source),
            analysis_type="visual_check",
            provider=str(result.get("provider", "")),
            model=str(result.get("model", "")),
            status=str(result.get("status", "")),
            analysis=result.get("profile", {}),
            render=result.get("render", {}),
        )
    result["visual_analysis_id"] = analysis_id
    return result


@mcp.tool()
def writing_ingest_case_pair(
    tender_file: str,
    bid_file: str,
    title: str = "",
    project_type: str = "",
    region: str = "浙江",
    tags: str = "",
) -> dict[str, Any]:
    """
    Import one accepted case pair: tender file + accepted pass/fail technical bid.

    Supported source files: txt, md, pdf, docx. The tool extracts text, stores the
    pair in the dedicated writing database, and saves reusable case patterns.
    """
    settings = _settings()
    tender = extract_text(tender_file)
    bid = extract_text(bid_file)
    case_title = title.strip() or Path(bid.get("path") or bid_file).stem or "通过制案例"
    requirements = extract_tender_requirements(tender["text"], source_path=tender.get("path", ""))
    outline = extract_outline(bid["text"])
    patterns = extract_case_patterns(tender["text"], bid["text"])

    with db.db_session(settings.database_path) as conn:
        case_id = db.create_case_pair(
            conn,
            title=case_title,
            project_type=project_type,
            region=region,
            tags=tags,
            tender_path=tender.get("path", ""),
            bid_path=bid.get("path", ""),
            tender_text=tender["text"],
            bid_text=bid["text"],
            outline=outline,
            requirements=requirements,
            patterns=patterns,
        )
        db.create_lesson(
            conn,
            title=f"{case_title} 通过制写作模式",
            lesson="; ".join(patterns.get("style_notes", [])),
            scope="pass_bid_writing",
            tags=tags or "case,pass-fail,technical",
            source="case_ingest",
            case_id=case_id,
        )
        saved = db.get_case_pair(conn, case_id)

    return {
        "case": saved,
        "summary": {
            "tender_chars": len(tender["text"]),
            "bid_chars": len(bid["text"]),
            "outline_count": len(outline),
            "requirement_count": requirements.get("requirement_count", 0),
            "scene_terms": patterns.get("scene_terms", []),
        },
    }


@mcp.tool()
def writing_extract_tender_requirements(
    tender_file: str = "",
    tender_text: str = "",
) -> dict[str, Any]:
    """Extract pass/fail technical-bid requirements from a tender file or text."""
    if tender_file.strip():
        extracted = extract_text(tender_file)
        text = extracted["text"]
        source_path = extracted.get("path", "")
    elif tender_text.strip():
        text = tender_text
        source_path = ""
    else:
        raise ValueError("tender_file or tender_text is required")
    return extract_tender_requirements(text, source_path=source_path)


@mcp.tool()
def writing_build_response_matrix(
    requirements: dict[str, Any],
    outline: list[dict[str, Any]] | None = None,
    case_id: int | None = None,
) -> dict[str, Any]:
    """
    Build a response matrix mapping tender requirements to target bid sections.

    When case_id is provided, the accepted case outline is used as the preferred
    section vocabulary.
    """
    settings = _settings()
    case_outline = outline
    if case_id is not None:
        with db.db_session(settings.database_path) as conn:
            case = db.get_case_pair(conn, int(case_id))
            if case is None:
                raise ValueError(f"case not found: {case_id}")
            case_outline = case.get("outline", []) or outline
    rows = build_response_matrix(requirements, case_outline)
    return {
        "matrix": rows,
        "requirement_count": len(requirements.get("requirements", [])),
        "human_check_count": sum(1 for row in rows if row.get("human_check")),
    }


@mcp.tool()
def writing_search_case_patterns(
    query: str,
    project_type: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """Search accepted case patterns and writing lessons."""
    settings = _settings()
    with db.db_session(settings.database_path) as conn:
        cases = db.search_case_pairs(conn, query=query, project_type=project_type, limit=limit)
        lessons = db.search_lessons(conn, query=query, scope="pass_bid_writing", limit=limit)
    results = []
    for case in cases:
        patterns = case.get("patterns", {})
        results.append(
            {
                "case_id": case.get("id"),
                "title": case.get("title"),
                "project_type": case.get("project_type"),
                "tags": case.get("tags"),
                "scene_terms": patterns.get("scene_terms", []),
                "layout_profile_id": patterns.get("layout_profile_id") or case.get("layout_profile_id"),
                "layout_status": patterns.get("layout_status", ""),
                "outline": patterns.get("outline", [])[:12],
                "reusable_snippets": patterns.get("reusable_snippets", [])[:8],
                "bid_excerpt": compact_text(case.get("bid_text", ""), 500),
            }
        )
    return {"query": query, "cases": results, "lessons": lessons}


@mcp.tool()
def writing_generate_outline(
    requirements: dict[str, Any] | None = None,
    project_type: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Generate a pass/fail technical-bid outline for Hermes to fill."""
    outline = generate_outline(requirements, project_type=project_type)
    return {"title": title or "通过制技术标", "outline": outline, "section_count": len(outline)}


@mcp.tool()
def writing_generate_docx(
    title: str,
    sections: dict[str, str] | list[dict[str, Any]] | None = None,
    outline: list[dict[str, Any]] | None = None,
    requirements: dict[str, Any] | None = None,
    response_matrix: list[dict[str, Any]] | None = None,
    output_name: str = "",
    tender_path: str = "",
    project_dir: str = "",
    layout_profile_id: int | None = None,
    visual_qa: bool = True,
) -> dict[str, Any]:
    """
    Generate an editable DOCX technical-bid draft.

    Hermes can pass final section text through sections. If sections is omitted,
    the tool creates a structured placeholder draft from outline and matrix.
    """
    settings = _settings()
    layout_profile = _load_layout_profile(settings, layout_profile_id)
    filename = safe_filename(output_name or title, fallback="pass_bid_draft") + ".docx"
    if project_dir.strip():
        project_path = _resolve_path(project_dir, base=settings.root_dir)
        output_dir = project_path / "outputs"
    else:
        project_path = None
        output_dir = settings.drafts_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    result = generate_docx(
        title=title,
        output_path=output_path,
        outline=outline,
        sections=sections,
        requirements=requirements,
        response_matrix=response_matrix,
        layout_profile=layout_profile,
    )
    visual_report: dict[str, Any] = {}
    if visual_qa:
        visual_report = visual_check_document(
            target_path=Path(result["docx_path"]),
            settings=settings,
            reference_layout=layout_profile,
        )
        with db.db_session(settings.database_path) as conn:
            visual_analysis_id = db.create_visual_analysis(
                conn,
                target_path=result["docx_path"],
                analysis_type="generated_docx_visual_check",
                provider=str(visual_report.get("provider", "")),
                model=str(visual_report.get("model", "")),
                status=str(visual_report.get("status", "")),
                analysis=visual_report.get("profile", {}),
                render=visual_report.get("render", {}),
            )
        visual_report["visual_analysis_id"] = visual_analysis_id
        result["visual_report"] = visual_report
    normalized_sections = {}
    if isinstance(sections, dict):
        normalized_sections = sections
    elif isinstance(sections, list):
        normalized_sections = {
            str(item.get("title", idx)): str(item.get("content", ""))
            for idx, item in enumerate(sections, start=1)
        }
    with db.db_session(settings.database_path) as conn:
        draft_id = db.create_draft(
            conn,
            title=title,
            tender_path=tender_path,
            requirements=requirements or {},
            response_matrix=response_matrix or [],
            outline=outline or [],
            section_contents=normalized_sections,
            docx_path=result["docx_path"],
            project_dir=str(project_path) if project_path else "",
            layout_profile_id=layout_profile_id,
            visual_report=visual_report,
        )
    result["draft_id"] = draft_id
    return result


@mcp.tool()
def writing_check_draft_compliance(
    draft_docx: str,
    requirements: dict[str, Any] | None = None,
    tender_file: str = "",
) -> dict[str, Any]:
    """
    Check whether a DOCX draft appears to cover extracted tender requirements.

    This is a heuristic reverse check. Hermes should use it to find likely
    omissions and human-confirmation items, not as a legal guarantee.
    """
    settings = _settings()
    docx_path = Path(draft_docx).expanduser().resolve()
    if not docx_path.exists():
        raise ValueError(f"draft_docx not found: {docx_path}")
    reqs = requirements
    if reqs is None:
        if tender_file.strip():
            extracted = extract_text(tender_file)
            reqs = extract_tender_requirements(extracted["text"], source_path=extracted.get("path", ""))
        else:
            with db.db_session(settings.database_path) as conn:
                draft = db.get_draft_by_docx(conn, str(docx_path))
            reqs = draft.get("requirements", {}) if draft else {}
    compliance = check_docx_compliance(docx_path=docx_path, requirements=reqs or {})
    with db.db_session(settings.database_path) as conn:
        draft = db.get_draft_by_docx(conn, str(docx_path))
        if draft:
            db.update_draft_compliance(conn, int(draft["id"]), compliance)
    return compliance


@mcp.tool()
def writing_export_pdf(
    docx_path: str,
    pdf_path: str = "",
) -> dict[str, Any]:
    """Export a DOCX draft to PDF using LibreOffice or Microsoft Word COM."""
    settings = _settings()
    source = Path(docx_path).expanduser().resolve()
    if not source.exists():
        raise ValueError(f"docx_path not found: {source}")
    target = Path(pdf_path).expanduser().resolve() if pdf_path.strip() else source.with_suffix(".pdf")
    result = export_docx_to_pdf(source, target)
    if result.get("status") == "ready":
        with db.db_session(settings.database_path) as conn:
            draft = db.get_draft_by_docx(conn, str(source))
            if draft:
                db.update_draft_pdf(conn, int(draft["id"]), str(target))
    return result


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
