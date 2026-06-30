from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

import fitz

from pass_bid_writing.case_library import ingest_case_folder
from pass_bid_writing.production import (
    _save_run_state,
    approve_production_section,
    assemble_production_docx,
    confirm_file_roles,
    confirm_task_spec,
    get_run_state,
    prepare_production_project,
)
from pass_bid_writing.visual_sources import analyze_visual_sources


def build_fixture(root: Path) -> tuple[Path, Path]:
    case = root / "case"
    project = root / "project"
    case.mkdir(parents=True)
    project.mkdir(parents=True)
    (case / "招标文件.txt").write_text(
        "河道治理工程通过制评审，要求进度、质量、安全和围堰导流措施。",
        encoding="utf-8",
    )
    (case / "已通过技术标.txt").write_text(
        "第一章 施工总体部署\n第二章 围堰导流\n第三章 质量和安全保证措施",
        encoding="utf-8",
    )
    (project / "招标文件.txt").write_text(
        "\n".join(
            [
                "项目名称：河道综合治理E2E工程",
                "总工期：180日历天。",
                "质量目标：合格。",
                "采用《水利水电工程施工组织设计规范》SL 303-2017。",
                "应提供施工总平面布置、进度计划、围堰导流和安全度汛措施。",
            ]
        ),
        encoding="utf-8",
    )
    (project / "初步设计报告.txt").write_text(
        "建设内容包括河道疏浚、护岸和排水工程。",
        encoding="utf-8",
    )
    (project / "河道平面图.dwg").write_bytes(b"DWG fixture placeholder")
    pdf = fitz.open()
    page = pdf.new_page(width=842, height=595)
    page.insert_text((72, 72), "Drawing No. E2E-01")
    page.insert_text((72, 110), "River construction plan")
    pdf.save(project / "河道平面图.pdf")
    pdf.close()
    return case, project


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="")
    args = parser.parse_args()
    root = (
        Path(args.output_root).expanduser().resolve()
        if args.output_root
        else Path(tempfile.mkdtemp(prefix="pass-bid-v1-e2e-"))
    )
    data_root = root / "app-data"
    os.environ["PASS_BID_DATA_DIR"] = str(data_root)
    os.environ["PASS_BID_WRITING_DISABLE_WORD_COM"] = "1"
    case, project = build_fixture(root)

    learned = ingest_case_folder(
        str(case),
        project_type="河道治理工程",
        analyze_layout=False,
    )
    state = prepare_production_project(str(project), project_type="河道治理工程")
    state = confirm_file_roles(state["run_id"])
    if state["status"] == "visual_analysis_pending":
        state = analyze_visual_sources(state["run_id"])
    state = confirm_task_spec(state["run_id"])

    # Offline smoke test seeds human-approved content. Live chapter generation is
    # covered separately when a DeepSeek key is configured.
    state["status"] = "generating"
    section_codes = [section["code"] for section in state["sections"]]
    for section_code in section_codes:
        section = next(item for item in state["sections"] if item["code"] == section_code)
        section["content"] = (
            "本章依据已导入的招标文件、初步设计资料和受控编制蓝图形成。"
            "项目专属数字仅引用证据库，缺失参数保留人工确认标记。\n\n"
            "| 控制项 | 执行要求 |\n|---|---|\n| 质量 | 按招标要求和已取得规范执行 |\n"
        )
        section["status"] = "awaiting_approval"
        _save_run_state(state["run_id"], state)
        state = approve_production_section(state["run_id"], section_code)
    state = assemble_production_docx(state["run_id"])
    final = get_run_state(state["run_id"])
    assert final is not None
    assert Path(final["docx"]["docx_path"]).exists()
    assert final["drawings"]
    assert any(item.get("source_pdf_path") for item in final["drawings"])

    print(
        json.dumps(
            {
                "status": "ok",
                "root": str(root),
                "run_id": final["run_id"],
                "case_id": learned["case"]["id"],
                "docx": final["docx"]["docx_path"],
                "drawing_count": len(final["drawings"]),
                "report_count": len(final.get("reports", {})),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
