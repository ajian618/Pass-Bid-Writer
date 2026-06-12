from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

from .text import extract_docx_text


def safe_filename(value: str, fallback: str = "draft") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", value).strip(" ._")
    return cleaned or fallback


def apply_chinese_font(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "SimSun"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(12)
    for style_name in ("Heading 1", "Heading 2", "Heading 3"):
        style = styles[style_name]
        style.font.name = "SimHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")


def normalize_sections(
    *,
    outline: list[dict[str, Any]] | None,
    sections: dict[str, str] | list[dict[str, Any]] | None,
    response_matrix: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(sections, dict):
        for idx, (title, content) in enumerate(sections.items(), start=1):
            normalized.append({"level": 1, "title": title, "content": content, "order": idx})
    elif isinstance(sections, list):
        for idx, item in enumerate(sections, start=1):
            normalized.append(
                {
                    "level": int(item.get("level", 1)),
                    "title": str(item.get("title", f"章节{idx}")),
                    "content": str(item.get("content", "")),
                    "order": int(item.get("order", idx)),
                }
            )
    elif outline:
        matrix_by_section: dict[str, list[dict[str, Any]]] = {}
        for row in response_matrix or []:
            matrix_by_section.setdefault(str(row.get("target_section", "")), []).append(row)
        for idx, item in enumerate(outline, start=1):
            title = str(item.get("title", f"章节{idx}"))
            rows = matrix_by_section.get(title, [])
            if rows:
                body = "\n".join(
                    f"【待完善】响应 {row.get('requirement_id')}: {row.get('response_strategy')}"
                    for row in rows
                )
            else:
                body = "【待完善】请 Hermes 根据响应矩阵和历史通过案例补写本章内容。"
            normalized.append(
                {
                    "level": int(item.get("level", 1)),
                    "title": title,
                    "content": body,
                    "order": int(item.get("order", idx)),
                }
            )
    else:
        normalized.append(
            {
                "level": 1,
                "title": "施工组织设计",
                "content": "【待完善】请 Hermes 根据招标文件要求生成通过制技术标正文。",
                "order": 1,
            }
        )
    return normalized


def generate_docx(
    *,
    title: str,
    output_path: Path,
    outline: list[dict[str, Any]] | None = None,
    sections: dict[str, str] | list[dict[str, Any]] | None = None,
    requirements: dict[str, Any] | None = None,
    response_matrix: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    apply_chinese_font(document)
    document.add_heading(title, level=0)
    document.add_paragraph("说明：本文件为 Hermes 生成的通过制技术标复核初稿，提交前需人工核查项目参数、格式和签章要求。")

    if requirements:
        document.add_heading("通过制响应摘要", level=1)
        document.add_paragraph(f"检测模式：{requirements.get('detected_mode', 'unknown')}")
        document.add_paragraph(f"抽取要求数量：{requirements.get('requirement_count', 0)}")

    for section in normalize_sections(
        outline=outline,
        sections=sections,
        response_matrix=response_matrix,
    ):
        level = max(1, min(int(section.get("level", 1)), 3))
        document.add_heading(str(section["title"]), level=level)
        content = str(section.get("content", "")).strip()
        if content:
            for paragraph in content.splitlines():
                if paragraph.strip():
                    document.add_paragraph(paragraph.strip())

    if response_matrix:
        document.add_heading("响应矩阵复核表", level=1)
        table = document.add_table(rows=1, cols=5)
        headers = ["编号", "类别", "招标要求", "对应章节", "人工核查"]
        for idx, header in enumerate(headers):
            table.rows[0].cells[idx].text = header
        for row in response_matrix:
            cells = table.add_row().cells
            cells[0].text = str(row.get("requirement_id", ""))
            cells[1].text = str(row.get("category", ""))
            cells[2].text = str(row.get("requirement", ""))
            cells[3].text = str(row.get("target_section", ""))
            cells[4].text = "是" if row.get("human_check") else "否"

    document.save(str(output_path))
    return {"docx_path": str(output_path), "section_count": len(document.paragraphs)}


def check_docx_compliance(
    *,
    docx_path: Path,
    requirements: dict[str, Any],
) -> dict[str, Any]:
    draft_text = extract_docx_text(docx_path)
    missing: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    for item in requirements.get("requirements", []):
        requirement = str(item.get("requirement", ""))
        keywords = [kw for kw in re.split(r"[，。；、\s]+", requirement) if len(kw) >= 2]
        important = keywords[:8]
        hits = [kw for kw in important if kw in draft_text]
        result = {
            "requirement_id": item.get("id"),
            "category": item.get("category"),
            "requirement": requirement,
            "matched_keywords": hits,
        }
        if hits:
            covered.append(result)
        else:
            missing.append(result)

    placeholders = sorted(set(re.findall(r"【[^】]*(?:待完善|人工确认|待确认)[^】]*】", draft_text)))
    return {
        "docx_path": str(docx_path),
        "requirement_count": len(requirements.get("requirements", [])),
        "covered_count": len(covered),
        "missing_count": len(missing),
        "placeholder_count": len(placeholders),
        "missing_requirements": missing,
        "placeholders": placeholders,
        "status": "needs_human_review" if missing or placeholders else "ready_for_manual_final_check",
    }


def export_docx_to_pdf(docx_path: Path, pdf_path: Path) -> dict[str, Any]:
    docx_path = docx_path.resolve()
    pdf_path = pdf_path.resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    libreoffice = shutil.which("soffice") or shutil.which("libreoffice")
    if libreoffice:
        completed = subprocess.run(
            [
                libreoffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_path.parent),
                str(docx_path),
            ],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        generated = pdf_path.parent / f"{docx_path.stem}.pdf"
        if generated.exists() and generated != pdf_path:
            generated.replace(pdf_path)
        if pdf_path.exists():
            return {"status": "ready", "pdf_path": str(pdf_path), "engine": "libreoffice"}
        return {
            "status": "blocked",
            "engine": "libreoffice",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "message": "LibreOffice conversion did not create the expected PDF.",
        }

    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        return {
            "status": "blocked",
            "pdf_path": str(pdf_path),
            "engine": "none",
            "message": f"PDF export requires Microsoft Word COM or LibreOffice: {exc}",
        }

    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        document = word.Documents.Open(str(docx_path))
        document.SaveAs(str(pdf_path), FileFormat=17)
        document.Close(False)
        return {"status": "ready", "pdf_path": str(pdf_path), "engine": "word_com"}
    except Exception as exc:
        return {
            "status": "blocked",
            "pdf_path": str(pdf_path),
            "engine": "word_com",
            "message": str(exc),
        }
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
