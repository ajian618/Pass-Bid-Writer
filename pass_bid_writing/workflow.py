from __future__ import annotations

from pathlib import Path
from typing import Any

from . import db
from .case_library import ingest_case_folder
from .config import ensure_storage_dirs, get_settings
from .production import (
    _save_run_state,
    approve_production_section,
    assemble_production_docx,
    confirm_file_roles,
    confirm_task_spec,
    generate_production_section,
    get_run_state,
    mark_generation_failed,
    prepare_production_project,
    review_production_draft,
    suggest_task_spec,
)
from .reports import export_production_reports
from .visual_sources import analyze_visual_sources


ACTION_LABELS = {
    "analyze_project": "分析项目资料",
    "confirm_file_roles": "确认文件角色",
    "analyze_visuals": "提取视觉证据",
    "confirm_task_spec": "确认编制任务书",
    "suggest_task_spec": "根据资料与案例生成建议任务书",
    "generate_chapter": "生成章节正文",
    "revise_chapter": "按要求重写章节",
    "assemble": "装配DOCX和交付文件",
    "review_draft": "复核施工组织设计",
    "export_reports": "更新控制报告",
    "ingest_case": "学习已通过案例",
}


def create_job(
    action: str,
    *,
    run_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if action not in ACTION_LABELS:
        raise ValueError(f"unsupported workflow action: {action}")
    settings = get_settings()
    ensure_storage_dirs(settings)
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        active = [
            item
            for item in db.list_workflow_jobs(
                conn,
                production_run_id=run_id,
                limit=20,
            )
            if item.get("status") in {"queued", "running"}
        ]
        if active:
            raise ValueError(f"当前已有任务正在执行：{active[0].get('message', '')}")
        job_id = db.create_workflow_job(
            conn,
            action=action,
            production_run_id=run_id,
            message=ACTION_LABELS[action],
            metadata=metadata,
        )
        job = db.get_workflow_job(conn, job_id)
    if job is None:
        raise RuntimeError("后台任务创建失败")
    if run_id is not None:
        _set_workflow_state(
            run_id,
            status="queued",
            action=action,
            job_id=job_id,
            message=ACTION_LABELS[action],
        )
    return job


def run_job(job_id: int) -> None:
    settings = get_settings()
    ensure_storage_dirs(settings)
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        job = db.get_workflow_job(conn, job_id)
        if job is None:
            return
        db.update_workflow_job(
            conn,
            job_id,
            status="running",
            message=ACTION_LABELS.get(job["action"], job["action"]),
        )
    run_id = int(job["production_run_id"]) if job.get("production_run_id") else None
    if run_id is not None:
        _set_workflow_state(
            run_id,
            status="running",
            action=str(job["action"]),
            job_id=job_id,
            message=ACTION_LABELS.get(str(job["action"]), str(job["action"])),
        )
    try:
        result = _execute_action(str(job["action"]), run_id, job.get("metadata", {}))
        resolved_run_id = int(result.get("run_id") or run_id or 0) or None
        compact = {
            key: value
            for key, value in result.items()
            if key in {"run_id", "status", "message", "case_id", "docx_path", "pdf_path"}
        }
        with db.db_session(settings.database_path) as conn:
            db.update_workflow_job(
                conn,
                job_id,
                status="succeeded",
                production_run_id=resolved_run_id,
                message="任务已完成",
                result=compact,
            )
        if resolved_run_id is not None:
            _set_workflow_state(
                resolved_run_id,
                status="idle",
                action=str(job["action"]),
                job_id=job_id,
                message="任务已完成",
            )
    except Exception as exc:
        error = str(exc)
        with db.db_session(settings.database_path) as conn:
            db.update_workflow_job(
                conn,
                job_id,
                status="failed",
                production_run_id=run_id,
                message="任务执行失败",
                error_text=error,
            )
        if run_id is not None:
            if job.get("action") in {"generate_chapter", "revise_chapter", "assemble"}:
                mark_generation_failed(run_id, error)
            _set_workflow_state(
                run_id,
                status="failed",
                action=str(job["action"]),
                job_id=job_id,
                message="任务执行失败",
                error=error,
            )


def get_job(job_id: int) -> dict[str, Any] | None:
    settings = get_settings()
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        return db.get_workflow_job(conn, job_id)


def list_jobs(run_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    settings = get_settings()
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        return db.list_workflow_jobs(
            conn,
            production_run_id=run_id,
            limit=limit,
        )


def recover_interrupted_jobs() -> None:
    settings = get_settings()
    db.init_db(settings.database_path)
    with db.db_session(settings.database_path) as conn:
        rows = conn.execute(
            "SELECT id FROM workflow_jobs WHERE status IN ('queued', 'running')"
        ).fetchall()
        for row in rows:
            db.update_workflow_job(
                conn,
                int(row["id"]),
                status="failed",
                message="程序上次退出时任务未完成",
                error_text="interrupted_by_restart",
            )


def approve_chapter(run_id: int, section_code: str) -> dict[str, Any]:
    return approve_production_section(run_id, section_code)


def _execute_action(
    action: str,
    run_id: int | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if action == "analyze_project":
        state = prepare_production_project(
            str(metadata["project_dir"]),
            project_type=str(metadata.get("project_type", "水利工程通用")),
            expand_archives=True,
        )
        return {"run_id": state["run_id"], "status": state["status"]}
    if action == "ingest_case":
        result = ingest_case_folder(
            str(metadata["project_dir"]),
            project_type=str(metadata.get("project_type", "")),
            analyze_layout=bool(metadata.get("analyze_layout", True)),
        )
        return {
            "case_id": int(result.get("case", {}).get("id", 0)),
            "status": "succeeded",
        }
    if run_id is None:
        raise ValueError("该任务缺少生产run_id")
    if action == "confirm_file_roles":
        state = confirm_file_roles(run_id)
    elif action == "analyze_visuals":
        state = analyze_visual_sources(run_id)
    elif action == "confirm_task_spec":
        state = confirm_task_spec(run_id)
    elif action == "suggest_task_spec":
        state = suggest_task_spec(run_id)
    elif action in {"generate_chapter", "revise_chapter"}:
        state = generate_production_section(
            run_id,
            str(metadata["section_code"]),
            revision_instruction=(
                str(metadata.get("instruction", ""))
                if action == "revise_chapter"
                else ""
            ),
        )
    elif action == "assemble":
        state = assemble_production_docx(run_id)
    elif action == "review_draft":
        state = review_production_draft(run_id)
    elif action == "export_reports":
        state = get_run_state(run_id)
        if state is None:
            raise ValueError(f"production run not found: {run_id}")
        output_dir = Path(state["project"]["project_dir"]) / "outputs"
        state["reports"] = export_production_reports(state, output_dir)
        _save_run_state(run_id, state)
    else:
        raise ValueError(f"unsupported workflow action: {action}")
    return {"run_id": run_id, "status": state.get("status", "")}


def _set_workflow_state(
    run_id: int,
    *,
    status: str,
    action: str,
    job_id: int,
    message: str,
    error: str = "",
) -> None:
    state = get_run_state(run_id)
    if state is None:
        return
    state["workflow"] = {
        "status": status,
        "action": action,
        "job_id": int(job_id),
        "message": message,
        "error": error,
    }
    _save_run_state(run_id, state)
