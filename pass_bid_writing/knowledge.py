from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import db
from .analysis import suggest_section
from .config import get_settings
from .schemas import CaseAsset, StandardClause
from .text import compact_text, extract_located_text


CLAUSE_PATTERN = re.compile(
    r"^\s*(?:(第\s*[0-9一二三四五六七八九十百]+\s*条)|"
    r"(\d+(?:\.\d+){1,5}))\s*[、.．:]?\s*(.*)$"
)


def extract_standard_clauses(
    source_path: Path,
    *,
    standard_code: str,
    applicable_sections: list[str] | None = None,
    max_clauses: int = 800,
) -> list[dict[str, Any]]:
    blocks = extract_located_text(source_path)
    clauses: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for block in blocks:
        page = block.get("page")
        lines = [re.sub(r"\s+", " ", line).strip() for line in str(block.get("text", "")).splitlines()]
        index = 0
        while index < len(lines):
            line = lines[index]
            match = CLAUSE_PATTERN.match(line)
            if not match:
                index += 1
                continue
            clause_id = (match.group(1) or match.group(2) or "").replace(" ", "")
            content = match.group(3).strip()
            continuation: list[str] = []
            cursor = index + 1
            while cursor < len(lines) and len(continuation) < 3:
                next_line = lines[cursor]
                if not next_line or CLAUSE_PATTERN.match(next_line):
                    break
                if len(next_line) <= 220:
                    continuation.append(next_line)
                cursor += 1
            text = compact_text(" ".join([content, *continuation]).strip(), 1000)
            identity = (clause_id, page)
            if text and identity not in seen:
                seen.add(identity)
                strong = any(word in text for word in ("必须", "严禁", "不得", "禁止"))
                clauses.append(
                    StandardClause(
                        standard_code=standard_code,
                        clause_id=clause_id,
                        text=text,
                        source_path=str(source_path),
                        page=page,
                        applicable_sections=applicable_sections or [],
                        applicability="由招标文件引用，具体施工部位由章节任务匹配",
                        mandatory_level="mandatory" if strong else "unknown",
                    ).model_dump()
                )
            index = max(cursor, index + 1)
            if len(clauses) >= max_clauses:
                return clauses
    return clauses


def attach_standard_file(
    *,
    run_id: int,
    state: dict[str, Any],
    standard_code: str,
    target: Path,
    official_url: str = "",
) -> dict[str, Any]:
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    standard = next(
        (
            item
            for item in state.get("standards", [])
            if item.get("code", "").replace(" ", "") == standard_code.replace(" ", "")
        ),
        None,
    )
    if standard is None:
        raise ValueError(f"未找到规范编号：{standard_code}")
    source_blocks = extract_located_text(target)
    source_text = re.sub(
        r"\s+",
        "",
        "\n".join(str(block.get("text", "")) for block in source_blocks),
    ).upper()
    normalized_code = re.sub(r"\s+", "", standard["code"]).upper().replace("—", "-").replace("–", "-")
    code_verified = normalized_code in source_text.replace("—", "-").replace("–", "-")
    standard["status"] = "available" if code_verified else "needs_confirmation"
    standard["local_path"] = str(target)
    standard["sha256"] = digest
    if official_url:
        standard["official_url"] = official_url
    clauses = extract_standard_clauses(
        target,
        standard_code=standard["code"],
        applicable_sections=standard.get("affected_sections", []),
    )
    existing = [
        item
        for item in state.get("standard_clauses", [])
        if item.get("standard_code", "").replace(" ", "") != standard_code.replace(" ", "")
    ]
    state["standard_clauses"] = [*existing, *clauses]
    standard["clause_count"] = len(clauses)
    standard["clause_parse_status"] = "ready" if clauses else "needs_confirmation"
    standard["identity_verified"] = code_verified
    for item in state.get("confirmations", []):
        if (
            item.get("category") == "规范待下载"
            and standard_code.replace(" ", "") in item.get("title", "").replace(" ", "")
        ):
            item["status"] = "resolved"
            item["resolution"] = str(target)
    if not clauses:
        state.setdefault("confirmations", []).append(
            {
                "category": "规范解析待确认",
                "title": f"{standard_code}未识别到可定位条款",
                "detail": "规范原文已保存，但未识别到编号条款。请确认文件是否为扫描件或目录页。",
                "severity": "high",
                "affected_sections": standard.get("affected_sections", []),
                "status": "open",
                "recommended_action": "上传可检索PDF/DOCX，或执行视觉资料分析后人工确认条款。",
            }
        )
    if not code_verified:
        state.setdefault("confirmations", []).append(
            {
                "category": "规范版本待确认",
                "title": f"{standard_code}原文身份未核验",
                "detail": "上传文件的可检索文字中未发现招标引用的完整标准编号，可能是扫描件、错误版本或错误文件。",
                "severity": "high",
                "affected_sections": standard.get("affected_sections", []),
                "status": "open",
                "recommended_action": "人工核对封面和版本；扫描件可运行千问视觉分析后再确认。",
            }
        )
    _persist_attached_standard(run_id, standard, clauses)
    _refresh_section_standard_basis(state, standard, clauses)
    return {"standard": standard, "clauses": clauses}


def load_case_assets(
    *,
    project_type: str,
    requirement_text: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    settings = get_settings()
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        cases = db.search_case_pairs(conn, project_type=project_type, limit=limit)
        if not cases:
            keywords = _case_search_keywords(project_type, requirement_text)
            for keyword in keywords:
                cases.extend(db.search_case_pairs(conn, query=keyword, limit=limit))
                if len(cases) >= limit:
                    break
    deduped: list[dict[str, Any]] = []
    seen_cases: set[int] = set()
    for case in cases:
        case_id = int(case["id"])
        if case_id in seen_cases:
            continue
        seen_cases.add(case_id)
        deduped.append(case)
        if len(deduped) >= limit:
            break

    assets: list[dict[str, Any]] = []
    for case in deduped:
        case_id = int(case["id"])
        patterns = case.get("patterns", {}) or {}
        outline = patterns.get("outline") or case.get("outline") or []
        if outline:
            assets.append(
                CaseAsset(
                    asset_id=f"case-{case_id}-outline",
                    case_id=case_id,
                    case_title=case.get("title", ""),
                    asset_type="outline",
                    title=f"{case.get('title', '')}章节结构",
                    content=outline,
                    applicable_project_types=[case.get("project_type", "")],
                    applicable_sections=["全局"],
                    reuse_rule="structure_only",
                    source_path=case.get("bid_path", ""),
                    layout_profile_id=case.get("layout_profile_id"),
                ).model_dump()
            )
        for index, snippet in enumerate(patterns.get("reusable_snippets", [])[:16], start=1):
            keyword = str(snippet.get("keyword", "案例措辞"))
            section = canonical_section_title(suggest_section(keyword + str(snippet.get("text", ""))))
            assets.append(
                CaseAsset(
                    asset_id=f"case-{case_id}-wording-{index}",
                    case_id=case_id,
                    case_title=case.get("title", ""),
                    asset_type="wording",
                    title=f"{keyword}稳健措辞",
                    content={
                        "keyword": keyword,
                        "text": _sanitize_case_text(str(snippet.get("text", ""))),
                    },
                    applicable_project_types=[case.get("project_type", "")],
                    applicable_sections=[section],
                    reuse_rule="replace_parameters",
                    source_path=case.get("bid_path", ""),
                    layout_profile_id=case.get("layout_profile_id"),
                ).model_dump()
            )
        for index, note in enumerate(patterns.get("style_notes", [])[:8], start=1):
            assets.append(
                CaseAsset(
                    asset_id=f"case-{case_id}-style-{index}",
                    case_id=case_id,
                    case_title=case.get("title", ""),
                    asset_type="style_note",
                    title="公司成品写作规则",
                    content=note,
                    applicable_project_types=[case.get("project_type", "")],
                    applicable_sections=["全局"],
                    reuse_rule="structure_only",
                    source_path=case.get("bid_path", ""),
                    layout_profile_id=case.get("layout_profile_id"),
                ).model_dump()
            )
        layout_id = patterns.get("layout_profile_id") or case.get("layout_profile_id")
        if layout_id:
            assets.append(
                CaseAsset(
                    asset_id=f"case-{case_id}-layout",
                    case_id=case_id,
                    case_title=case.get("title", ""),
                    asset_type="layout",
                    title=f"{case.get('title', '')}版式配置",
                    content={"layout_profile_id": int(layout_id)},
                    applicable_project_types=[case.get("project_type", "")],
                    applicable_sections=["全局"],
                    reuse_rule="layout_only",
                    source_path=case.get("bid_path", ""),
                    layout_profile_id=int(layout_id),
                ).model_dump()
            )
    deduped_assets: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    for asset in assets:
        signature = json.dumps(
            {
                "asset_type": asset.get("asset_type"),
                "title": asset.get("title"),
                "content": asset.get("content"),
                "applicable_sections": asset.get("applicable_sections"),
                "reuse_rule": asset.get("reuse_rule"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if signature in seen_assets:
            continue
        seen_assets.add(signature)
        deduped_assets.append(asset)
    return deduped_assets


def canonical_section_title(title: str) -> str:
    aliases = {
        "编制说明及工程概况": "编制说明",
        "主要施工方案与技术措施": "主要施工方法与技术措施",
        "安全生产、文明施工及应急措施": "安全生产、文明施工与应急措施",
        "环境保护与水土保持措施": "环境保护与水土保持",
        "资源配置计划": "主要施工设备与检验仪器投入",
        "季节性施工、度汛及水利专项措施": "季节性施工、施工导流与度汛",
        "资料管理、验收配合及后续服务": "资料管理、验收配合与附件",
    }
    return aliases.get(title, title)


def _case_search_keywords(project_type: str, requirement_text: str) -> list[str]:
    candidates = [
        word for word in ("河道", "堤防", "泵站", "水闸", "水库", "疏浚", "护岸", "围堰", "导流")
        if word in project_type + requirement_text
    ]
    return candidates or ["水利"]


def _sanitize_case_text(text: str) -> str:
    return re.sub(
        r"\d+(?:\.\d+)?\s*(?:日历天|天|个月|年|%|％|mm|cm|m|km|m²|m3|m³|"
        r"kW|MPa|kPa|台|套|辆|人|班|次)",
        "【项目参数】",
        text,
        flags=re.IGNORECASE,
    )


def _persist_attached_standard(
    run_id: int,
    standard: dict[str, Any],
    clauses: list[dict[str, Any]],
) -> None:
    settings = get_settings()
    with db.db_session(settings.database_path) as conn:
        conn.execute(
            """
            UPDATE standard_documents
            SET local_path = ?, sha256 = ?, official_url = ?, status = ?, metadata_json = ?, updated_at = ?
            WHERE production_run_id = ? AND REPLACE(standard_code, ' ', '') = REPLACE(?, ' ', '')
            """,
            (
                standard.get("local_path", ""),
                standard.get("sha256", ""),
                standard.get("official_url", ""),
                standard.get("status", ""),
                json.dumps(
                    {
                        "official_platform": standard.get("official_platform", ""),
                        "search_query": standard.get("search_query", ""),
                        "clause_count": len(clauses),
                    },
                    ensure_ascii=False,
                ),
                db.utc_now(),
                run_id,
                standard.get("code", ""),
            ),
        )
        conn.execute(
            "DELETE FROM standard_clauses WHERE production_run_id = ? AND REPLACE(standard_code, ' ', '') = REPLACE(?, ' ', '')",
            (run_id, standard.get("code", "")),
        )
        for clause in clauses:
            conn.execute(
                """
                INSERT INTO standard_clauses
                (production_run_id, standard_code, clause_id, clause_text, source_path, source_page,
                 applicable_sections_json, applicability, mandatory_level, verification_status,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    clause["standard_code"],
                    clause["clause_id"],
                    clause["text"],
                    clause["source_path"],
                    clause.get("page"),
                    json.dumps(clause.get("applicable_sections", []), ensure_ascii=False),
                    clause.get("applicability", ""),
                    clause.get("mandatory_level", "unknown"),
                    clause.get("verification_status", "verified_local_source"),
                    db.utc_now(),
                    db.utc_now(),
                ),
            )


def _refresh_section_standard_basis(
    state: dict[str, Any],
    standard: dict[str, Any],
    clauses: list[dict[str, Any]],
) -> None:
    clause_refs = [
        f"{item['standard_code']} {item['clause_id']}（原文第{item.get('page') or '—'}页）"
        for item in clauses[:12]
    ]
    affected = set(standard.get("affected_sections", []))
    for section in state.get("sections", []):
        if section.get("title") not in affected:
            continue
        base = [
            item
            for item in section.get("reference_basis", [])
            if not item.startswith(standard.get("code", "") + " ")
        ]
        section["reference_basis"] = [*base, *clause_refs]
