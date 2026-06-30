from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import ezdxf
from openpyxl import Workbook

from pass_bid_writing.knowledge import attach_standard_file
from pass_bid_writing.mcp_server import writing_ingest_passed_case
from pass_bid_writing.production import (
    confirm_file_roles,
    confirm_task_spec,
    generate_production_docx,
    prepare_production_project,
)
from pass_bid_writing.visual_sources import analyze_visual_sources


def build_fixture(root: Path) -> tuple[Path, Path, Path]:
    passed = root / "passed_cases" / "历史河道案例"
    project = root / "new_tenders" / "河道综合治理E2E"
    passed.mkdir(parents=True, exist_ok=True)
    project.mkdir(parents=True, exist_ok=True)
    (passed / "招标文件.txt").write_text(
        "河道治理工程采用通过制评审，要求进度、质量、安全、导流和度汛措施。",
        encoding="utf-8",
    )
    (passed / "已通过技术标.txt").write_text(
        "第一章 施工总体部署\n"
        "项目按准备、主体施工、验收移交组织，所有项目参数均以本项目图纸为准。\n"
        "第二章 围堰导流\n"
        "导流顺序、围堰位置和水位参数应结合设计文件复核。",
        encoding="utf-8",
    )
    (project / "招标文件.txt").write_text(
        "\n".join(
            [
                "项目名称：河道综合治理E2E工程",
                "建设地点：浙江省某市",
                "本项目施工组织设计采用通过制评审。",
                "总工期：180日历天。",
                "质量目标：合格。",
                "技术标准和要求：《水利水电工程施工组织设计规范》SL 303-2017。",
                "验收执行《水利水电建设工程验收规程》SL 223-2008。",
                "投标人应提供施工总平面布置、施工进度计划和关键节点。",
                "须提供主要施工方案、围堰导流、排水降水和安全度汛措施。",
                "必须提供质量、安全、环境保护、人员、机械和检验仪器配置。",
                "须附招标要求的表格、流程图、组织机构图和进度图。",
            ]
        ),
        encoding="utf-8",
    )
    (project / "初步设计报告.txt").write_text(
        "项目名称：河道综合治理E2E工程\n"
        "建设地点：浙江省某市\n"
        "质量目标：合格\n"
        "主要建设内容包括河道疏浚、护岸和排水工程。\n",
        encoding="utf-8",
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "工程量清单"
    sheet.append(["项目名称", "单位", "工程量", "来源"])
    sheet.append(["河道疏浚", "m3", "", "待设计处确认"])
    sheet.append(["护岸工程", "m", "", "待设计处确认"])
    workbook.save(project / "招标预算.xlsx")
    drawing = ezdxf.new()
    modelspace = drawing.modelspace()
    modelspace.add_line((0, 0), (100, 0))
    modelspace.add_line((100, 0), (100, 50))
    modelspace.add_text("河道施工范围", height=5).set_placement((10, 10))
    drawing.saveas(project / "设计图纸.dxf")
    standard = root / "SL303-2017_规范原文.txt"
    standard.write_text(
        "SL 303-2017 水利水电工程施工组织设计规范\n"
        "1.0.1 本规范适用于水利水电工程施工组织设计。\n"
        "3.2.1 施工总布置应结合工程条件统筹确定。\n"
        "3.2.2 严禁在没有设计依据时改变工程边界。\n",
        encoding="utf-8",
    )
    return passed, project, standard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="")
    parser.add_argument("--skip-generation", action="store_true")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    root = (
        Path(args.output_root).expanduser().resolve()
        if args.output_root
        else workspace / "storage" / "e2e-smoke" / datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    passed, project, standard = build_fixture(root)
    learned = writing_ingest_passed_case(
        str(passed),
        auto_visual=False,
        project_type="河道治理工程",
        tags="e2e,passed_case",
    )
    state = prepare_production_project(str(project), project_type="河道治理工程")
    state = confirm_file_roles(state["run_id"])
    if state["status"] == "visual_analysis_pending":
        state = analyze_visual_sources(state["run_id"])
    attach_standard_file(
        run_id=state["run_id"],
        state=state,
        standard_code="SL 303-2017",
        target=standard,
    )
    from pass_bid_writing.production import _save_run_state

    _save_run_state(state["run_id"], state)
    state = confirm_task_spec(state["run_id"])
    if not args.skip_generation:
        state = generate_production_docx(state["run_id"])
    summary = {
        "root": str(root),
        "run_id": state["run_id"],
        "case_id": learned["case"]["id"],
        "status": state["status"],
        "file_count": len(state["files"]),
        "fact_count": len(state["facts"]),
        "standard_count": len(state["standards"]),
        "standard_clause_count": len(state.get("standard_clauses", [])),
        "case_asset_count": len(state.get("case_assets", [])),
        "section_count": len(state["sections"]),
        "reports": state.get("reports", {}),
        "docx": state.get("docx", {}),
        "compliance": state.get("compliance", {}),
        "document_audit": state.get("document_audit", {}),
        "visual_report": state.get("visual_report", {}),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
