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
from .text import compact_text, extract_text


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
) -> dict[str, Any]:
    """
    Generate an editable DOCX technical-bid draft.

    Hermes can pass final section text through sections. If sections is omitted,
    the tool creates a structured placeholder draft from outline and matrix.
    """
    settings = _settings()
    filename = safe_filename(output_name or title, fallback="pass_bid_draft") + ".docx"
    output_path = settings.drafts_dir / filename
    result = generate_docx(
        title=title,
        output_path=output_path,
        outline=outline,
        sections=sections,
        requirements=requirements,
        response_matrix=response_matrix,
    )
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
