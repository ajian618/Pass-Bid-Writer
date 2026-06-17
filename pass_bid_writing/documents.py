from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .text import extract_docx_text


def safe_filename(value: str, fallback: str = "draft") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", value).strip(" ._")
    return cleaned or fallback


def apply_chinese_font(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "FangSong"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "仿宋")
    normal.font.size = Pt(12)
    normal.paragraph_format.first_line_indent = Pt(24)
    normal.paragraph_format.line_spacing = 1.5
    for style_name in ("Heading 1", "Heading 2", "Heading 3"):
        style = styles[style_name]
        style.font.name = "SimHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.bold = True
        style.font.color.rgb = RGBColor(31, 78, 121)
        style.paragraph_format.first_line_indent = Pt(0)
    styles["Heading 1"].font.size = Pt(16)
    styles["Heading 2"].font.size = Pt(15)
    styles["Heading 3"].font.size = Pt(14)


def apply_layout_profile(
    document: Document,
    layout_profile: dict[str, Any] | None,
    *,
    title: str,
) -> None:
    section = document.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.15)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.45)

    header_text = _layout_text(layout_profile or {}, "headers_footers", "header") or title
    paragraph = section.header.paragraphs[0]
    paragraph.text = header_text
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_paragraph_font(paragraph, "SimSun", 9)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("第 ")
    _add_page_number(footer)
    footer.add_run(" 页")
    _set_paragraph_font(footer, "SimSun", 9)


def add_cover_page(document: Document, title: str, layout_profile: dict[str, Any] | None) -> None:
    for _ in range(6):
        document.add_paragraph("")
    title_para = document.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.paragraph_format.first_line_indent = Pt(0)
    title_run = title_para.add_run(title)
    title_run.bold = True
    _set_run_font(title_run, "SimHei", "黑体", 22)

    subtitle = _layout_text(layout_profile or {}, "cover", "subtitle") or "通过制技术标"
    subtitle_para = document.add_paragraph()
    subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_para.paragraph_format.first_line_indent = Pt(0)
    subtitle_run = subtitle_para.add_run(subtitle)
    _set_run_font(subtitle_run, "SimHei", "黑体", 16)

    for _ in range(8):
        document.add_paragraph("")
    note_para = document.add_paragraph()
    note_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note_para.paragraph_format.first_line_indent = Pt(0)
    note = _layout_text(layout_profile or {}, "cover", "bottom_text") or "投标文件技术部分"
    note_run = note_para.add_run(note)
    _set_run_font(note_run, "SimSun", "宋体", 12)
    document.add_page_break()


def add_toc_page(document: Document) -> None:
    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.first_line_indent = Pt(0)
    run = heading.add_run("目录")
    run.bold = True
    _set_run_font(run, "SimHei", "黑体", 16)

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Pt(0)
    _add_complex_field(paragraph, r'TOC \o "1-3" \h \z \u')
    document.add_page_break()


def _layout_text(profile: dict[str, Any], section: str, key: str) -> str:
    value = profile.get(section, {})
    if isinstance(value, dict):
        candidate = value.get(key) or value.get("text") or value.get("pattern")
        if isinstance(candidate, str):
            return candidate.strip()
    return ""


def _set_paragraph_font(paragraph, font_name: str, size: int) -> None:
    for run in paragraph.runs:
        _set_run_font(run, font_name, font_name, size)


def _set_run_font(run, font_name: str, east_asia: str, size: int) -> None:
    run.font.name = font_name
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:eastAsia"), east_asia)
    run.font.size = Pt(size)


def _add_page_number(paragraph) -> None:
    _add_complex_field(paragraph, "PAGE")


def _add_complex_field(paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    fld_char_1 = OxmlElement("w:fldChar")
    fld_char_1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = instruction
    fld_char_2 = OxmlElement("w:fldChar")
    fld_char_2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char_1)
    run._r.append(instr_text)
    run._r.append(fld_char_2)


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _set_cell_text(cell, text: str, *, bold: bool = False) -> None:
    cell.text = text
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for paragraph in cell.paragraphs:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if bold else WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Pt(0)
        for run in paragraph.runs:
            run.bold = bold
            _set_run_font(run, "SimSun", "宋体", 10.5)


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


def add_markdown_content(
    document: Document,
    content: str,
    *,
    layout_profile: dict[str, Any] | None = None,
) -> dict[str, int]:
    lines = content.splitlines()
    idx = 0
    stats = {"paragraphs": 0, "tables": 0, "headings": 0, "lists": 0}
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if _is_markdown_table_start(lines, idx):
            rows, idx = _consume_markdown_table(lines, idx)
            add_word_table(document, rows, layout_profile=layout_profile)
            stats["tables"] += 1
            continue
        heading = _parse_markdown_or_chinese_heading(line)
        if heading:
            level, title = heading
            document.add_heading(title, level=max(1, min(level, 3)))
            stats["headings"] += 1
            idx += 1
            continue
        if re.match(r"^[-*]\s+", line):
            paragraph = document.add_paragraph(re.sub(r"^[-*]\s+", "", line), style="List Bullet")
            paragraph.paragraph_format.first_line_indent = Pt(0)
            stats["lists"] += 1
            idx += 1
            continue
        if re.match(r"^\d+[.)、]\s+", line):
            paragraph = document.add_paragraph(re.sub(r"^\d+[.)、]\s+", "", line), style="List Number")
            paragraph.paragraph_format.first_line_indent = Pt(0)
            stats["lists"] += 1
            idx += 1
            continue
        document.add_paragraph(line)
        stats["paragraphs"] += 1
        idx += 1
    return stats


def _parse_markdown_or_chinese_heading(line: str) -> tuple[int, str] | None:
    markdown = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
    if markdown:
        return len(markdown.group(1)), markdown.group(2).strip()
    if re.match(r"^第[一二三四五六七八九十百\d]+章[、\s：:]", line):
        return 1, line
    if re.match(r"^第[一二三四五六七八九十百\d]+节[、\s：:]", line):
        return 2, line
    if re.match(r"^[一二三四五六七八九十]+[、.．]\s*", line):
        return 3, line
    return None


def _is_markdown_table_start(lines: list[str], idx: int) -> bool:
    if idx + 1 >= len(lines):
        return False
    return _is_pipe_row(lines[idx]) and _is_table_separator(lines[idx + 1])


def _is_pipe_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not _is_pipe_row(stripped):
        return False
    body = stripped.strip("|").strip()
    return bool(body) and all(re.fullmatch(r":?-{3,}:?", part.strip()) for part in body.split("|"))


def _consume_markdown_table(lines: list[str], idx: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    while idx < len(lines) and _is_pipe_row(lines[idx]):
        if not _is_table_separator(lines[idx]):
            rows.append([cell.strip() for cell in lines[idx].strip().strip("|").split("|")])
        idx += 1
    width = max((len(row) for row in rows), default=0)
    normalized = [row + [""] * (width - len(row)) for row in rows if width]
    return normalized, idx


def add_word_table(
    document: Document,
    rows: list[list[str]],
    *,
    layout_profile: dict[str, Any] | None = None,
) -> None:
    if not rows:
        return
    column_count = max(len(row) for row in rows)
    table = document.add_table(rows=0, cols=column_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    header_fill = _layout_text(layout_profile or {}, "tables", "header_fill") or "D9EAF7"
    for row_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for col_idx in range(column_count):
            cell = cells[col_idx]
            text = row[col_idx] if col_idx < len(row) else ""
            _set_cell_text(cell, text, bold=row_idx == 0)
            if row_idx == 0:
                _shade_cell(cell, header_fill)


def generate_docx(
    *,
    title: str,
    output_path: Path,
    outline: list[dict[str, Any]] | None = None,
    sections: dict[str, str] | list[dict[str, Any]] | None = None,
    requirements: dict[str, Any] | None = None,
    response_matrix: list[dict[str, Any]] | None = None,
    layout_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    apply_chinese_font(document)
    apply_layout_profile(document, layout_profile, title=title)
    add_cover_page(document, title, layout_profile)
    add_toc_page(document)
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
            add_markdown_content(document, content, layout_profile=layout_profile)

    if response_matrix:
        document.add_heading("响应矩阵复核表", level=1)
        table = document.add_table(rows=1, cols=5)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"
        headers = ["编号", "类别", "招标要求", "对应章节", "人工核查"]
        for idx, header in enumerate(headers):
            _set_cell_text(table.rows[0].cells[idx], header, bold=True)
            _shade_cell(table.rows[0].cells[idx], "D9EAF7")
        for row in response_matrix:
            cells = table.add_row().cells
            _set_cell_text(cells[0], str(row.get("requirement_id", "")))
            _set_cell_text(cells[1], str(row.get("category", "")))
            _set_cell_text(cells[2], str(row.get("requirement", "")))
            _set_cell_text(cells[3], str(row.get("target_section", "")))
            _set_cell_text(cells[4], "是" if row.get("human_check") else "否")

    document.save(str(output_path))
    field_update = update_docx_fields(output_path)
    return {
        "docx_path": str(output_path),
        "section_count": len(document.paragraphs),
        "table_count": len(document.tables),
        "field_update": field_update,
    }


def update_docx_fields(docx_path: Path) -> dict[str, Any]:
    """Update TOC/page fields when Microsoft Word COM is available."""
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        return {"status": "skipped", "engine": "none", "message": str(exc)}

    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        document = word.Documents.Open(str(docx_path.resolve()))
        document.Fields.Update()
        for toc in document.TablesOfContents:
            toc.Update()
        document.Save()
        document.Close(False)
        return {"status": "ready", "engine": "word_com"}
    except Exception as exc:
        return {"status": "blocked", "engine": "word_com", "message": str(exc)}
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


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
        document.Fields.Update()
        for toc in document.TablesOfContents:
            toc.Update()
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
