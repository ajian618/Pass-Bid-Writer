from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .evidence_links import is_reference_only_value, parse_document_reference
from .text import compact_text, split_meaningful_lines


REQUIREMENT_KEYWORDS: dict[str, list[str]] = {
    "format": ["技术标", "施工组织设计", "暗标", "明标", "格式", "目录", "页码", "字体", "签章", "装订"],
    "pass_fail": ["通过制", "合格制", "符合性", "响应性", "通过", "不通过", "否决", "废标", "实质性响应"],
    "schedule": ["工期", "进度", "节点", "开工", "完工", "总工期"],
    "quality": ["质量", "验收", "合格", "创优"],
    "safety": ["安全", "文明施工", "应急", "风险"],
    "environment": ["环保", "环境保护", "水土保持", "扬尘", "噪声"],
    "resources": ["项目经理", "技术负责人", "人员", "机械", "设备", "材料", "劳动力"],
    "water_scene": ["水利", "水电", "河道", "堤防", "水库", "泵站", "闸站", "水闸", "围堰", "导流", "度汛", "排水", "降水"],
}

STANDARD_SECTIONS = [
    "编制说明及工程概况",
    "施工总体部署",
    "施工进度计划及保证措施",
    "主要施工方案与技术措施",
    "质量管理体系与保证措施",
    "安全生产、文明施工及应急措施",
    "环境保护与水土保持措施",
    "资源配置计划",
    "季节性施工、度汛及水利专项措施",
    "资料管理、验收配合及后续服务",
]

MANDATORY_MARKERS = (
    "必须",
    "应当",
    "应提供",
    "须提供",
    "须附",
    "不得",
    "严禁",
    "投标人应",
    "承包人应",
    "需提交",
    "技术标要求",
    "施工组织设计应",
)


def classify_requirement(line: str) -> str:
    scores: Counter[str] = Counter()
    for category, keywords in REQUIREMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in line:
                scores[category] += 1
    if not scores:
        return "general"
    return scores.most_common(1)[0][0]


def extract_tender_requirements(
    text: str,
    *,
    source_path: str = "",
    located_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lines = _located_requirement_lines(text, located_blocks)
    requirements: list[dict[str, Any]] = []
    reference_links: list[dict[str, Any]] = []
    seen: set[str] = set()
    all_keywords = [kw for keywords in REQUIREMENT_KEYWORDS.values() for kw in keywords]
    for line_no, line, page, context in lines:
        if any(keyword in line for keyword in all_keywords) or any(marker in line for marker in MANDATORY_MARKERS):
            reference = parse_document_reference(line)
            if reference:
                reference_links.append(
                    {
                        "kind": "requirement_reference",
                        "category": classify_requirement(line),
                        "source_path": source_path,
                        "source_page": page,
                        "source_line": line_no,
                        "source_excerpt": compact_text(line, 260),
                        **reference,
                        "status": "unresolved",
                    }
                )
                if _is_reference_pointer_line(line):
                    continue
            key = line[:120]
            if key in seen:
                continue
            seen.add(key)
            requirements.append(
                {
                    "id": f"REQ-{len(requirements) + 1:03d}",
                    "category": classify_requirement(line),
                    "requirement": compact_text(line, 260),
                    "source_line": line_no,
                    "source_page": page,
                    "source_path": source_path,
                    "source_context": compact_text(context, 500),
                    "suggested_section": suggest_section(line),
                    "status": "needs_response",
                }
            )
    _resolve_requirement_references(reference_links, requirements)

    pass_fail_mode = any(item["category"] == "pass_fail" for item in requirements)
    unresolved_references = [
        item for item in reference_links if item.get("status") != "resolved"
    ]
    return {
        "source_path": source_path,
        "detected_mode": "pass_fail" if pass_fail_mode else "unknown",
        "requirement_count": len(requirements),
        "requirements": requirements,
        "reference_links": reference_links,
        "human_confirmation_items": [
            "确认本项目技术标是否明确为通过制/合格制。",
            "确认暗标、签章、页码、字体、目录、装订等格式要求。",
            "确认工期、质量目标、人员设备、关键水利施工场景是否完整。",
        ]
        + [
            f"核对未解析的招标引用：{item['source_excerpt']}"
            for item in unresolved_references[:20]
        ],
    }


def _located_requirement_lines(
    text: str,
    located_blocks: list[dict[str, Any]] | None,
) -> list[tuple[int, str, int | None, str]]:
    if not located_blocks:
        return [
            (line_no, line, None, line)
            for line_no, line in split_meaningful_lines(text)
        ]
    result: list[tuple[int, str, int | None, str]] = []
    line_no = 0
    for block in located_blocks:
        context = str(block.get("text", ""))
        for _, line in split_meaningful_lines(context):
            line_no += 1
            result.append((line_no, line, block.get("page"), context))
    return result


def _is_reference_pointer_line(line: str) -> bool:
    value = re.split(r"[：:]", line, maxsplit=1)[-1]
    return is_reference_only_value(value)


def _resolve_requirement_references(
    reference_links: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> None:
    for reference in reference_links:
        same_category = [
            item
            for item in requirements
            if item.get("category") == reference.get("category")
        ]
        candidates = same_category
        explicitly_located = False
        target_page = reference.get("target_page")
        if target_page is not None:
            exact = [
                item for item in candidates if item.get("source_page") == target_page
            ]
            if exact:
                candidates = exact
                explicitly_located = True
        target_table = str(reference.get("target_table", ""))
        if target_table:
            table_matches = [
                item
                for item in candidates
                if target_table in re.sub(r"\s+", "", str(item.get("source_context", "")))
            ]
            if table_matches:
                candidates = table_matches
                explicitly_located = True
        if not candidates or (len(candidates) != 1 and not explicitly_located):
            continue
        reference["status"] = "resolved"
        reference["resolved_requirement_ids"] = [item["id"] for item in candidates]
        reference["resolved_pages"] = sorted(
            {
                item.get("source_page")
                for item in candidates
                if item.get("source_page") is not None
            }
        )
        for target in candidates:
            target.setdefault("reference_chain", []).append(
                {
                    "source_path": reference.get("source_path", ""),
                    "source_page": reference.get("source_page"),
                    "source_excerpt": reference.get("source_excerpt", ""),
                    "target_page": target_page,
                    "target_table": target_table,
                }
            )


def extract_outline(text: str, max_items: int = 80) -> list[dict[str, Any]]:
    heading_re = re.compile(
        r"^\s*((第[一二三四五六七八九十百]+[章节篇])|([一二三四五六七八九十]+[、.．])|(\d+([.．]\d+)*[、.．]?)|（[一二三四五六七八九十\d]+）)\s*(.+?)\s*$"
    )
    outline: list[dict[str, Any]] = []
    for line_no, line in split_meaningful_lines(text):
        match = heading_re.match(line)
        if not match:
            continue
        title = match.group(6).strip() if match.group(6) else line.strip()
        if len(title) > 80:
            continue
        outline.append({"level": infer_heading_level(line), "title": title, "source_line": line_no})
        if len(outline) >= max_items:
            break
    if not outline:
        outline = [{"level": 1, "title": title, "source_line": 0} for title in STANDARD_SECTIONS]
    return outline


def infer_heading_level(line: str) -> int:
    if line.startswith("第"):
        return 1
    number = re.match(r"^\s*(\d+(?:[.．]\d+)*)", line)
    if number:
        return min(number.group(1).count(".") + number.group(1).count("．") + 1, 4)
    if re.match(r"^\s*[一二三四五六七八九十]+[、.．]", line):
        return 1
    return 2


def extract_case_patterns(tender_text: str, bid_text: str) -> dict[str, Any]:
    outline = extract_outline(bid_text)
    scene_terms = []
    for category, keywords in REQUIREMENT_KEYWORDS.items():
        if category in {"water_scene", "schedule", "quality", "safety", "environment", "resources"}:
            for keyword in keywords:
                if keyword in bid_text or keyword in tender_text:
                    scene_terms.append(keyword)
    scene_terms = sorted(set(scene_terms))

    snippets: list[dict[str, str]] = []
    lines = [line for _, line in split_meaningful_lines(bid_text)]
    for keyword in scene_terms[:20]:
        for line in lines:
            if keyword in line and 18 <= len(line) <= 260:
                snippets.append({"keyword": keyword, "text": compact_text(line, 220)})
                break

    return {
        "outline": outline[:40],
        "scene_terms": scene_terms,
        "reusable_snippets": snippets[:30],
        "style_notes": [
            "优先使用已通过技术标中的章节顺序和稳健措辞。",
            "项目参数不明确时保留人工确认占位，不虚构。",
            "通过制正文强调完整响应、施工组织闭环和风险措施覆盖。",
        ],
    }


def suggest_section(text: str) -> str:
    mapping = [
        ("schedule", "施工进度计划及保证措施"),
        ("quality", "质量管理体系与保证措施"),
        ("safety", "安全生产、文明施工及应急措施"),
        ("environment", "环境保护与水土保持措施"),
        ("resources", "资源配置计划"),
        ("water_scene", "季节性施工、度汛及水利专项措施"),
        ("format", "编制说明及工程概况"),
        ("pass_fail", "编制说明及工程概况"),
    ]
    category = classify_requirement(text)
    for key, section in mapping:
        if category == key:
            return section
    return "主要施工方案与技术措施"


def build_response_matrix(requirements: dict[str, Any], outline: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    outline_titles = [item.get("title", "") for item in (outline or []) if item.get("title")]
    rows: list[dict[str, Any]] = []
    for item in requirements.get("requirements", []):
        section = item.get("suggested_section") or suggest_section(item.get("requirement", ""))
        if outline_titles:
            section = best_outline_match(section, outline_titles)
        rows.append(
            {
                "requirement_id": item.get("id", f"REQ-{len(rows) + 1:03d}"),
                "category": item.get("category", "general"),
                "requirement": item.get("requirement", ""),
                "source_line": item.get("source_line", 0),
                "source_page": item.get("source_page"),
                "source_path": item.get("source_path", requirements.get("source_path", "")),
                "target_section": section,
                "response_strategy": response_strategy(item.get("category", "general")),
                "draft_status": "pending",
                "human_check": item.get("category") in {"format", "resources", "schedule"},
            }
        )
    return rows


def best_outline_match(section: str, outline_titles: list[str]) -> str:
    section_tokens = set(section)
    best = section
    best_score = 0
    for title in outline_titles:
        score = len(section_tokens.intersection(set(title)))
        if score > best_score:
            best = title
            best_score = score
    return best


def response_strategy(category: str) -> str:
    strategies = {
        "format": "按招标文件格式要求编排目录、签章、页码、暗标/明标规则，提交前人工复核。",
        "pass_fail": "作为实质性响应项逐条覆盖，避免遗漏导致不通过。",
        "schedule": "写明总工期、关键节点、资源保障和纠偏措施，具体日期需人工确认。",
        "quality": "建立质量目标、组织体系、过程控制、验收资料和整改闭环。",
        "safety": "覆盖安全责任、风险辨识、专项方案、文明施工和应急处置。",
        "environment": "覆盖水土保持、扬尘噪声、弃土弃渣、污水和生态保护。",
        "resources": "列明人员、机械、材料和劳动力计划，数量型号需人工确认。",
        "water_scene": "补充水利专项施工措施，如围堰导流、度汛、排水降水、泵闸调试。",
    }
    return strategies.get(category, "在相关施工组织章节中明确响应，不留空泛表述。")


def generate_outline(requirements: dict[str, Any] | None = None, project_type: str = "") -> list[dict[str, Any]]:
    sections = list(STANDARD_SECTIONS)
    text_blob = project_type
    if requirements:
        text_blob += " " + " ".join(
            item.get("requirement", "") for item in requirements.get("requirements", [])
        )
    if any(term in text_blob for term in ["泵站", "闸站", "水闸"]):
        sections.insert(4, "泵站、水闸及机电设备安装调试措施")
    if any(term in text_blob for term in ["河道", "堤防", "疏浚"]):
        sections.insert(4, "河道治理、堤防及疏浚施工措施")
    if any(term in text_blob for term in ["水库", "除险加固"]):
        sections.insert(4, "水库工程及运行约束专项措施")
    return [{"level": 1, "title": title, "order": idx + 1} for idx, title in enumerate(sections)]
