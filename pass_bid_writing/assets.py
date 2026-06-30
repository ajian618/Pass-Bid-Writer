from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def generate_document_assets(state: dict[str, Any], output_dir: Path) -> dict[str, str]:
    """Create editable, deterministic diagram sources without inventing project parameters."""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, str] = {}

    workflow = [
        "资料与角色确认",
        "项目证据提取",
        "规范与蓝图匹配",
        "任务书确认",
        "章节与图表生产",
        "一致性与视觉复核",
        "DOCX初稿交付",
    ]
    assets["production_workflow_svg"] = str(
        _write_flow_svg(assets_dir / "施组生产流程图.svg", "施组生产流程", workflow)
    )
    assets["production_workflow_png"] = str(
        _write_flow_png(assets_dir / "施组生产流程图.png", "施组生产流程", workflow)
    )
    organization_levels = [
        ["项目经理"],
        ["技术负责人", "施工负责人", "质量负责人", "安全负责人"],
        ["工程技术组", "质量检验组", "安全环保组", "物资设备组", "合同资料组"],
    ]
    assets["organization_chart_svg"] = str(
        _write_org_svg(assets_dir / "项目组织机构图.svg", organization_levels)
    )
    assets["organization_chart_png"] = str(
        _write_org_png(assets_dir / "项目组织机构图.png", organization_levels)
    )
    assets["quality_flow_svg"] = str(
        _write_flow_svg(
            assets_dir / "质量控制流程图.svg",
            "质量控制流程",
            ["技术交底", "材料与设备进场检验", "工序自检", "专检与报验", "验收记录归档"],
        )
    )
    assets["quality_flow_png"] = str(
        _write_flow_png(
            assets_dir / "质量控制流程图.png",
            "质量控制流程",
            ["技术交底", "材料与设备进场检验", "工序自检", "专检与报验", "验收记录归档"],
        )
    )
    assets["safety_flow_svg"] = str(
        _write_flow_svg(
            assets_dir / "安全管理流程图.svg",
            "安全管理流程",
            ["危险源辨识", "专项方案与交底", "班前检查", "过程巡查", "整改复验", "闭环归档"],
        )
    )
    assets["safety_flow_png"] = str(
        _write_flow_png(
            assets_dir / "安全管理流程图.png",
            "安全管理流程",
            ["危险源辨识", "专项方案与交底", "班前检查", "过程巡查", "整改复验", "闭环归档"],
        )
    )
    schedule_rows = [
        {
            "stage": "施工准备",
            "basis": "招标要求、设计资料、现场条件",
            "time": "【待人工确认】",
        },
        {
            "stage": "主体工程施工",
            "basis": "工程量清单、施工图、专项工法",
            "time": "【待人工确认】",
        },
        {
            "stage": "设备安装与配套工程",
            "basis": "设备清单、专业图纸、厂家资料",
            "time": "【待人工确认】",
        },
        {
            "stage": "验收与移交",
            "basis": "验收规程、招标节点要求",
            "time": "【待人工确认】",
        },
    ]
    schedule_json = assets_dir / "施工进度计划_待确认.json"
    schedule_json.write_text(
        json.dumps(
            {
                "notice": "本文件只定义进度图结构，不虚构开竣工日期、持续时间或逻辑关系。",
                "project_facts": [
                    fact for fact in state.get("facts", [])
                    if fact.get("key") in {"总工期", "计划工期"}
                ],
                "rows": schedule_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assets["schedule_source_json"] = str(schedule_json)
    assets["schedule_template_svg"] = str(
        _write_schedule_svg(assets_dir / "施工进度计划_待确认.svg", schedule_rows)
    )
    assets["schedule_template_png"] = str(
        _write_schedule_png(assets_dir / "施工进度计划_待确认.png", schedule_rows)
    )

    manifest = assets_dir / "assets_manifest.json"
    section_map = {item.get("code"): item for item in state.get("sections", [])}
    basis_links = {
        "production_workflow": _asset_basis(section_map, ["03"]),
        "organization_chart": _asset_basis(section_map, ["03", "11"]),
        "schedule_template": _asset_basis(section_map, ["05"]),
        "quality_flow": _asset_basis(section_map, ["07"]),
        "safety_flow": _asset_basis(section_map, ["08"]),
    }
    manifest.write_text(
        json.dumps(
            {
                "project": state.get("project", {}).get("name", ""),
                "rule": "所有具体日期、数量和节点必须来自项目事实；当前缺失处保留待人工确认。",
                "assets": assets,
                "basis_links": basis_links,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assets["manifest"] = str(manifest)
    return assets


def _asset_basis(
    section_map: dict[str, dict[str, Any]],
    codes: list[str],
) -> dict[str, list[str]]:
    project_basis: list[str] = []
    reference_basis: list[str] = []
    missing_basis: list[str] = []
    for code in codes:
        section = section_map.get(code, {})
        project_basis.extend(section.get("project_basis", []))
        reference_basis.extend(section.get("reference_basis", []))
        missing_basis.extend(section.get("missing_inputs", []))
    return {
        "project_basis": list(dict.fromkeys(project_basis)),
        "reference_basis": list(dict.fromkeys(reference_basis)),
        "missing_basis": list(dict.fromkeys(missing_basis)),
    }


def _write_flow_svg(path: Path, title: str, nodes: list[str]) -> Path:
    width = 1180
    box_width = 130
    gap = 28
    start_x = 26
    boxes: list[str] = []
    arrows: list[str] = []
    for index, node in enumerate(nodes):
        x = start_x + index * (box_width + gap)
        boxes.append(
            f'<rect x="{x}" y="76" width="{box_width}" height="62" rx="8" '
            'fill="#f2f7fd" stroke="#8fb7e7" stroke-width="1.5"/>'
            f'<text x="{x + box_width / 2}" y="111" text-anchor="middle" '
            f'font-family="Microsoft YaHei, sans-serif" font-size="14" fill="#233850">{escape(node)}</text>'
        )
        if index < len(nodes) - 1:
            x1 = x + box_width + 5
            x2 = x + box_width + gap - 5
            arrows.append(
                f'<line x1="{x1}" y1="107" x2="{x2}" y2="107" stroke="#1769e0" '
                'stroke-width="2" marker-end="url(#arrow)"/>'
            )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="180" viewBox="0 0 {width} 180">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 Z" fill="#1769e0"/></marker></defs>'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<text x="26" y="36" font-family="Microsoft YaHei, sans-serif" font-size="20" '
        f'font-weight="700" fill="#19324f">{escape(title)}</text>'
        + "".join(arrows)
        + "".join(boxes)
        + "</svg>"
    )
    path.write_text(svg, encoding="utf-8")
    return path


def _write_schedule_svg(path: Path, rows: list[dict[str, str]]) -> Path:
    row_height = 48
    height = 82 + len(rows) * row_height
    body: list[str] = []
    for index, row in enumerate(rows):
        y = 68 + index * row_height
        fill = "#f8fafc" if index % 2 == 0 else "#ffffff"
        body.append(f'<rect x="20" y="{y}" width="1120" height="{row_height}" fill="{fill}"/>')
        body.append(
            f'<text x="38" y="{y + 30}" font-family="Microsoft YaHei, sans-serif" '
            f'font-size="14" fill="#263b53">{escape(row["stage"])}</text>'
        )
        body.append(
            f'<text x="270" y="{y + 30}" font-family="Microsoft YaHei, sans-serif" '
            f'font-size="13" fill="#5b6b7d">{escape(row["basis"])}</text>'
        )
        body.append(
            f'<text x="920" y="{y + 30}" font-family="Microsoft YaHei, sans-serif" '
            f'font-size="13" fill="#a86106">{escape(row["time"])}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1160" height="{height}" viewBox="0 0 1160 {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        '<text x="20" y="32" font-family="Microsoft YaHei, sans-serif" font-size="20" '
        'font-weight="700" fill="#19324f">施工进度计划结构（待项目参数确认）</text>'
        '<rect x="20" y="50" width="1120" height="18" fill="#dfeaf7"/>'
        + "".join(body)
        + '<rect x="20" y="68" width="1120" height="'
        + str(len(rows) * row_height)
        + '" fill="none" stroke="#c8d5e4"/>'
        + "</svg>"
    )
    path.write_text(svg, encoding="utf-8")
    return path


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _write_flow_png(path: Path, title: str, nodes: list[str]) -> Path:
    width, height = 1770, 270
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((38, 24), title, fill="#19324f", font=_font(28, bold=True))
    box_width, gap, start_x = 195, 42, 38
    for index, node in enumerate(nodes):
        x = start_x + index * (box_width + gap)
        draw.rounded_rectangle((x, 112, x + box_width, 205), radius=12, fill="#f2f7fd", outline="#8fb7e7", width=2)
        bbox = draw.textbbox((0, 0), node, font=_font(18))
        draw.text(
            (x + (box_width - (bbox[2] - bbox[0])) / 2, 146),
            node,
            fill="#233850",
            font=_font(18),
        )
        if index < len(nodes) - 1:
            x1, x2, y = x + box_width + 8, x + box_width + gap - 8, 158
            draw.line((x1, y, x2, y), fill="#1769e0", width=4)
            draw.polygon([(x2, y), (x2 - 12, y - 8), (x2 - 12, y + 8)], fill="#1769e0")
    image.save(path, "PNG")
    return path


def _write_schedule_png(path: Path, rows: list[dict[str, str]]) -> Path:
    width = 1740
    row_height = 78
    height = 130 + len(rows) * row_height
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 20), "施工进度计划结构（待项目参数确认）", fill="#19324f", font=_font(28, bold=True))
    draw.rectangle((30, 82, width - 30, 126), fill="#dfeaf7")
    headers = [("施工阶段", 50), ("依据", 390), ("时间参数", 1380)]
    for text, x in headers:
        draw.text((x, 91), text, fill="#233850", font=_font(18, bold=True))
    for index, row in enumerate(rows):
        y = 126 + index * row_height
        fill = "#f8fafc" if index % 2 == 0 else "#ffffff"
        draw.rectangle((30, y, width - 30, y + row_height), fill=fill, outline="#c8d5e4")
        draw.text((50, y + 26), row["stage"], fill="#263b53", font=_font(18))
        draw.text((390, y + 26), row["basis"], fill="#5b6b7d", font=_font(17))
        draw.text((1380, y + 26), row["time"], fill="#a86106", font=_font(17))
    image.save(path, "PNG")
    return path


def _write_org_svg(path: Path, levels: list[list[str]]) -> Path:
    width, height = 1180, 430
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="26" y="36" font-family="Microsoft YaHei, sans-serif" font-size="20" font-weight="700" fill="#19324f">项目组织机构图（岗位名称，人员待确认）</text>',
    ]
    level_y = [76, 190, 310]
    centers: list[list[float]] = []
    for level, items in enumerate(levels):
        gap = width / (len(items) + 1)
        item_centers = []
        for index, item in enumerate(items, start=1):
            center = gap * index
            item_centers.append(center)
            box_width = min(170, gap - 24)
            parts.append(
                f'<rect x="{center - box_width / 2}" y="{level_y[level]}" width="{box_width}" height="54" rx="8" fill="#f2f7fd" stroke="#8fb7e7" stroke-width="1.5"/>'
                f'<text x="{center}" y="{level_y[level] + 33}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="14" fill="#233850">{escape(item)}</text>'
            )
        centers.append(item_centers)
    for child in centers[1]:
        parts.append(f'<line x1="{centers[0][0]}" y1="130" x2="{child}" y2="190" stroke="#1769e0" stroke-width="1.6"/>')
    for child in centers[2]:
        nearest = min(centers[1], key=lambda parent: abs(parent - child))
        parts.append(f'<line x1="{nearest}" y1="244" x2="{child}" y2="310" stroke="#1769e0" stroke-width="1.6"/>')
    parts.append("</svg>")
    path.write_text("".join(parts), encoding="utf-8")
    return path


def _write_org_png(path: Path, levels: list[list[str]]) -> Path:
    width, height = 1770, 645
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((38, 24), "项目组织机构图（岗位名称，人员待确认）", fill="#19324f", font=_font(28, bold=True))
    level_y = [114, 285, 465]
    centers: list[list[float]] = []
    for level, items in enumerate(levels):
        gap = width / (len(items) + 1)
        item_centers = []
        for index, item in enumerate(items, start=1):
            center = gap * index
            item_centers.append(center)
            box_width = min(255, gap - 36)
            draw.rounded_rectangle(
                (center - box_width / 2, level_y[level], center + box_width / 2, level_y[level] + 82),
                radius=12,
                fill="#f2f7fd",
                outline="#8fb7e7",
                width=2,
            )
            bbox = draw.textbbox((0, 0), item, font=_font(20))
            draw.text(
                (center - (bbox[2] - bbox[0]) / 2, level_y[level] + 28),
                item,
                fill="#233850",
                font=_font(20),
            )
        centers.append(item_centers)
    for child in centers[1]:
        draw.line((centers[0][0], 196, child, 285), fill="#1769e0", width=3)
    for child in centers[2]:
        nearest = min(centers[1], key=lambda parent: abs(parent - child))
        draw.line((nearest, 367, child, 465), fill="#1769e0", width=3)
    image.save(path, "PNG")
    return path
