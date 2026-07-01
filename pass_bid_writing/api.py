from __future__ import annotations

import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .blueprints import build_blueprint
from .case_library import get_case, list_cases, update_case
from .config import ensure_storage_dirs, get_settings
from .drawings import update_drawing_asset
from .knowledge import attach_standard_file
from .model_router import ModelRouter
from .production import (
    _input_is_available,
    _save_run_state,
    get_run_state,
    prepare_production_project,
    update_task_spec,
)
from .reports import export_production_reports
from .workflow import (
    approve_chapter,
    create_job,
    get_job,
    list_jobs,
    recover_interrupted_jobs,
    run_job,
)


class ConfirmRequest(BaseModel):
    confirmed: bool = True


class ChapterRevisionRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=4000)


class ReviewItemRequest(BaseModel):
    status: str = "resolved"
    resolution: str = ""
    fact_key: str = ""
    value: str = ""
    unit: str = ""


class FileRoleRequest(BaseModel):
    path: str
    role: str


class DrawingUpdateRequest(BaseModel):
    drawing_no: str | None = None
    title: str | None = None
    caption: str | None = None
    placement: str | None = None
    applicable_sections: list[str] | None = None
    crop: dict[str, float] | None = None
    status: str | None = None


class StandardStatusRequest(BaseModel):
    run_id: int
    standard_code: str
    status: str
    resolution: str = ""


class OfficialFetchRequest(BaseModel):
    run_id: int
    standard_code: str
    official_url: str


class ModelConfigRequest(BaseModel):
    deepseek_api_key: str | None = None
    deepseek_model: str | None = None
    dashscope_api_key: str | None = None
    qwen_flash_model: str | None = None
    qwen_plus_model: str | None = None
    bigmodel_api_key: str | None = None
    glm_vision_model: str | None = None


class CaseUpdateRequest(BaseModel):
    title: str | None = None
    project_type: str | None = None
    region: str | None = None
    tags: str | None = None
    outline: list[dict[str, Any]] | None = None
    scene_terms: list[str] | None = None
    reusable_snippets: list[dict[str, str]] | None = None
    style_notes: list[str] | None = None
    enabled: bool | None = None
    review_status: str | None = None
    review_notes: str | None = None


class TaskSpecSectionRequest(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    purpose: str = Field(default="", max_length=1000)
    required_inputs: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)


class TaskSpecUpdateRequest(BaseModel):
    sections: list[TaskSpecSectionRequest] = Field(min_length=1, max_length=30)
    revision_note: str = Field(default="", max_length=2000)


OFFICIAL_HOST_SUFFIXES = (
    ".gov.cn",
    "gov.cn",
    "openstd.samr.gov.cn",
    "mwr.gov.cn",
    "zj.gov.cn",
)


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_storage_dirs(settings)
    db.init_db(settings.database_path)
    recover_interrupted_jobs()
    app = FastAPI(title="施工组织设计生成台", version="1.1.2")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": "1.1.2",
            "data_dir": str(settings.data_dir),
            "models": ModelRouter().status(),
        }

    @app.get("/api/projects")
    def projects() -> list[dict[str, Any]]:
        return _list_projects()

    @app.delete("/api/projects/{run_id}")
    def delete_project(run_id: int) -> dict[str, Any]:
        try:
            deleted = _delete_project(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if deleted is None:
            raise HTTPException(status_code=404, detail="项目不存在或已删除")
        next_state = get_run_state()
        return {
            "deleted": deleted,
            "projects": _list_projects(),
            "state": _with_workflow(next_state or _empty_dashboard()),
        }

    @app.get("/api/cases")
    def cases() -> list[dict[str, Any]]:
        return list_cases()

    @app.get("/api/cases/{case_id}")
    def case_detail(case_id: int) -> dict[str, Any]:
        try:
            return get_case(case_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/cases/{case_id}")
    def edit_case(case_id: int, request: CaseUpdateRequest) -> dict[str, Any]:
        try:
            return update_case(case_id, request.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/config")
    def model_config() -> dict[str, Any]:
        return {
            "models": ModelRouter().status(),
            "data_dir": str(settings.data_dir),
            "config_path": str(settings.config_dir / ".env"),
            "configured_keys": {
                key: bool(os.environ.get(key, "").strip())
                for key in ("DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "ZHIPU_API_KEY")
            },
        }

    @app.patch("/api/config")
    def update_model_config(request: ModelConfigRequest) -> dict[str, Any]:
        env_mapping = {
            "deepseek_api_key": "DEEPSEEK_API_KEY",
            "deepseek_model": "PASS_BID_TEXT_MODEL",
            "dashscope_api_key": "DASHSCOPE_API_KEY",
            "qwen_flash_model": "PASS_BID_BATCH_MODEL",
            "qwen_plus_model": "PASS_BID_VISION_MODEL",
            "bigmodel_api_key": "ZHIPU_API_KEY",
            "glm_vision_model": "PASS_BID_REVIEW_VISION_MODEL",
        }
        env_path = settings.config_dir / ".env"
        values = _read_env_values(env_path)
        for field, env_key in env_mapping.items():
            value = getattr(request, field)
            if value is None:
                continue
            cleaned = value.strip()
            if cleaned:
                values[env_key] = cleaned
                os.environ[env_key] = cleaned
            # Empty fields intentionally keep the previous local value so the
            # browser never has to read a saved secret back into the form.
        _write_env_values(env_path, values)
        return model_config()

    @app.get("/api/dashboard")
    def dashboard(run_id: int | None = None) -> dict[str, Any]:
        state = get_run_state(run_id)
        return _with_workflow(state or _empty_dashboard())

    @app.get("/api/jobs/{job_id}")
    def workflow_job(job_id: int) -> dict[str, Any]:
        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="后台任务不存在")
        state = (
            get_run_state(int(job["production_run_id"]))
            if job.get("production_run_id")
            else None
        )
        return {"job": job, "state": _with_workflow(state) if state else None}

    @app.post("/api/projects/import", status_code=202)
    async def import_project(
        background_tasks: BackgroundTasks,
        project_name: str = Form(...),
        project_type: str = Form("水利工程通用"),
        files: list[UploadFile] = File(...),
        relative_paths: list[str] = Form(default=[]),
    ) -> dict[str, Any]:
        if not files:
            raise HTTPException(status_code=400, detail="请选择包含项目资料的文件夹")
        project_root = _new_import_root(settings.projects_dir, project_name)
        source_root = project_root / "sources"
        source_root.mkdir(parents=True, exist_ok=False)
        for folder in ("extracted", "drawings", "standards", "assets", "outputs"):
            (project_root / folder).mkdir(parents=True, exist_ok=True)
        try:
            saved = await _save_uploads(files, relative_paths, source_root)
        except Exception:
            shutil.rmtree(project_root, ignore_errors=True)
            raise
        if not saved:
            shutil.rmtree(project_root, ignore_errors=True)
            raise HTTPException(status_code=400, detail="文件夹中没有可导入文件")
        manifest = {
            "project_name": project_name.strip(),
            "project_type": project_type,
            "imported_at": _now(),
            "file_count": len(saved),
            "files": saved,
        }
        (project_root / "project.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            job = create_job(
                "analyze_project",
                metadata={
                    "project_dir": str(project_root),
                    "project_type": project_type,
                },
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        background_tasks.add_task(run_job, int(job["id"]))
        return {
            "job": job,
            "project": {
                "name": project_name,
                "project_dir": str(project_root),
                "file_count": len(saved),
            },
        }

    @app.post("/api/cases/import", status_code=202)
    async def import_case(
        background_tasks: BackgroundTasks,
        case_name: str = Form(...),
        project_type: str = Form(""),
        files: list[UploadFile] = File(...),
        relative_paths: list[str] = Form(default=[]),
    ) -> dict[str, Any]:
        case_root = _new_import_root(settings.cases_dir, case_name)
        source_root = case_root / "sources"
        source_root.mkdir(parents=True, exist_ok=False)
        try:
            saved = await _save_uploads(files, relative_paths, source_root)
        except Exception:
            shutil.rmtree(case_root, ignore_errors=True)
            raise
        if not saved:
            shutil.rmtree(case_root, ignore_errors=True)
            raise HTTPException(status_code=400, detail="案例文件夹为空")
        job = create_job(
            "ingest_case",
            metadata={
                "project_dir": str(case_root),
                "project_type": project_type,
                "analyze_layout": True,
            },
        )
        background_tasks.add_task(run_job, int(job["id"]))
        return {"job": job, "case_dir": str(case_root)}

    @app.post("/api/runs/{run_id}/sources", status_code=202)
    async def add_project_sources(
        run_id: int,
        background_tasks: BackgroundTasks,
        files: list[UploadFile] = File(...),
        relative_paths: list[str] = Form(default=[]),
    ) -> dict[str, Any]:
        state = _require_state(run_id)
        project_root = Path(state["project"]["project_dir"]).resolve()
        source_root = project_root / "sources"
        saved = await _save_uploads(files, relative_paths, source_root)
        if not saved:
            raise HTTPException(status_code=400, detail="没有上传补充资料")
        job = create_job(
            "analyze_project",
            metadata={
                "project_dir": str(project_root),
                "project_type": state["project"].get("project_type", "水利工程通用"),
            },
        )
        background_tasks.add_task(run_job, int(job["id"]))
        return {"job": job, "saved": saved}

    @app.post("/api/runs/{run_id}/confirm-file-roles", status_code=202)
    def confirm_file_roles(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _queue_action(run_id, "confirm_file_roles", background_tasks)

    @app.post("/api/runs/{run_id}/analyze-visuals", status_code=202)
    def analyze_visuals(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _queue_action(run_id, "analyze_visuals", background_tasks)

    @app.post("/api/runs/{run_id}/confirm-task-spec", status_code=202)
    def confirm_task(
        run_id: int,
        request: ConfirmRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        if not request.confirmed:
            raise HTTPException(status_code=400, detail="任务书未确认")
        return _queue_action(run_id, "confirm_task_spec", background_tasks)

    @app.post("/api/runs/{run_id}/suggest-task-spec", status_code=202)
    def suggest_task(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _queue_action(run_id, "suggest_task_spec", background_tasks)

    @app.put("/api/runs/{run_id}/task-spec")
    def save_task_spec(
        run_id: int,
        request: TaskSpecUpdateRequest,
    ) -> dict[str, Any]:
        try:
            state = update_task_spec(
                run_id,
                [item.model_dump() for item in request.sections],
                revision_note=request.revision_note,
            )
            return _with_workflow(state)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/chapters/{section_code}/generate", status_code=202)
    def generate_chapter(
        run_id: int,
        section_code: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        return _queue_action(
            run_id,
            "generate_chapter",
            background_tasks,
            {"section_code": section_code},
        )

    @app.post("/api/runs/{run_id}/chapters/{section_code}/revise", status_code=202)
    def revise_chapter(
        run_id: int,
        section_code: str,
        request: ChapterRevisionRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        return _queue_action(
            run_id,
            "revise_chapter",
            background_tasks,
            {"section_code": section_code, "instruction": request.instruction},
        )

    @app.post("/api/runs/{run_id}/chapters/{section_code}/approve")
    def approve_section(run_id: int, section_code: str) -> dict[str, Any]:
        try:
            return _with_workflow(approve_chapter(run_id, section_code))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/assemble", status_code=202)
    def assemble(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _queue_action(run_id, "assemble", background_tasks)

    @app.post("/api/runs/{run_id}/review-draft", status_code=202)
    def review_draft(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _queue_action(run_id, "review_draft", background_tasks)

    @app.post("/api/runs/{run_id}/export-reports", status_code=202)
    def export_reports(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _queue_action(run_id, "export_reports", background_tasks)

    @app.patch("/api/runs/{run_id}/review-items/{item_index}")
    def resolve_review_item(
        run_id: int,
        item_index: int,
        request: ReviewItemRequest,
    ) -> dict[str, Any]:
        state = _require_state(run_id)
        if request.status not in {"open", "resolved", "dismissed"}:
            raise HTTPException(status_code=400, detail="不支持的复核状态")
        items = state.get("confirmations", [])
        if item_index < 0 or item_index >= len(items):
            raise HTTPException(status_code=404, detail="人工复核项不存在")
        item = items[item_index]
        item["status"] = request.status
        item["resolution"] = request.resolution
        if request.fact_key.strip() and request.value.strip():
            existing = next(
                (fact for fact in state.get("facts", []) if fact.get("key") == request.fact_key.strip()),
                None,
            )
            fact_payload = {
                "key": request.fact_key.strip(),
                "value": request.value.strip(),
                "unit": request.unit.strip(),
                "source_path": "人工确认",
                "source_page": None,
                "source_excerpt": request.resolution or "工作台人工补录",
                "confidence": 1.0,
                "status": "confirmed",
            }
            if existing:
                existing.update(fact_payload)
            else:
                state.setdefault("facts", []).append(fact_payload)
        _refresh_sections_and_metrics(state)
        _save_run_state(run_id, state)
        return _with_workflow(state)

    @app.patch("/api/runs/{run_id}/files/role")
    def update_file_role(run_id: int, request: FileRoleRequest) -> dict[str, Any]:
        state = _require_state(run_id)
        allowed = {
            "tender",
            "design_report",
            "budget",
            "drawing",
            "standard",
            "accepted_bid",
            "attachment",
        }
        if request.role not in allowed:
            raise HTTPException(status_code=400, detail="不支持的文件角色")
        target = str(Path(request.path).expanduser().resolve())
        if not any(str(Path(item["path"]).resolve()) == target for item in state.get("files", [])):
            raise HTTPException(status_code=404, detail="项目中不存在该文件")
        overrides = {
            item["path"]: item.get("role", "attachment")
            for item in state.get("files", [])
        }
        overrides[target] = request.role
        try:
            next_state = prepare_production_project(
                state["project"]["project_dir"],
                project_type=state["project"]["project_type"],
                expand_archives=False,
                role_overrides=overrides,
            )
            return _with_workflow(next_state)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/runs/{run_id}/drawings/{drawing_id}")
    def update_drawing(
        run_id: int,
        drawing_id: str,
        request: DrawingUpdateRequest,
    ) -> dict[str, Any]:
        state = _require_state(run_id)
        updates = request.model_dump(exclude_none=True)
        if updates.get("placement") not in {None, "inline", "landscape_page"}:
            raise HTTPException(status_code=400, detail="不支持的图纸插入方式")
        if updates.get("status") not in {
            None,
            "pending_analysis",
            "pending_confirmation",
            "confirmed",
            "rejected",
            "missing_pdf",
        }:
            raise HTTPException(status_code=400, detail="不支持的图纸状态")
        if updates.get("status") == "confirmed":
            updates["confirmed_at"] = _now()
        try:
            update_drawing_asset(state, drawing_id, updates)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _resolve_drawing_confirmation(state)
        _refresh_sections_and_metrics(state)
        _save_run_state(run_id, state)
        return _with_workflow(state)

    @app.post("/api/standards/upload")
    async def upload_standard(
        run_id: int,
        standard_code: str,
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        state = _require_state(run_id)
        standards_dir = Path(state["project"]["project_dir"]) / "standards"
        standards_dir.mkdir(parents=True, exist_ok=True)
        target = standards_dir / _safe_filename(file.filename or f"{standard_code}.pdf")
        await _save_upload(file, target)
        try:
            result = attach_standard_file(
                run_id=run_id,
                state=state,
                standard_code=standard_code,
                target=target,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        state["reports"] = export_production_reports(
            state,
            Path(state["project"]["project_dir"]) / "outputs",
        )
        _refresh_sections_and_metrics(state)
        _save_run_state(run_id, state)
        return {
            "status": "available",
            "standard_code": standard_code,
            "local_path": str(target),
            "clause_count": len(result["clauses"]),
        }

    @app.patch("/api/standards/status")
    def set_standard_status(request: StandardStatusRequest) -> dict[str, Any]:
        state = _require_state(request.run_id)
        allowed = {
            "pending_download",
            "available",
            "not_applicable",
            "needs_confirmation",
        }
        if request.status not in allowed:
            raise HTTPException(status_code=400, detail="不支持的规范状态")
        standard = next(
            (
                item
                for item in state.get("standards", [])
                if item.get("code", "").replace(" ", "")
                == request.standard_code.replace(" ", "")
            ),
            None,
        )
        if standard is None:
            raise HTTPException(status_code=404, detail="规范不存在")
        if request.status == "available" and not standard.get("local_path"):
            raise HTTPException(status_code=409, detail="没有本地原文，不能标记为已取得")
        standard["status"] = request.status
        standard["status_resolution"] = request.resolution
        _refresh_sections_and_metrics(state)
        _save_run_state(request.run_id, state)
        return _with_workflow(state)

    @app.post("/api/standards/fetch")
    def fetch_standard(request: OfficialFetchRequest) -> dict[str, Any]:
        state = _require_state(request.run_id)
        host = (urllib.parse.urlparse(request.official_url).hostname or "").lower()
        if not any(host == suffix or host.endswith(suffix) for suffix in OFFICIAL_HOST_SUFFIXES):
            raise HTTPException(status_code=400, detail="仅允许从政府或标准主管部门下载")
        standards_dir = Path(state["project"]["project_dir"]) / "standards"
        standards_dir.mkdir(parents=True, exist_ok=True)
        target = standards_dir / f"{_safe_filename(request.standard_code)}.pdf"
        try:
            req = urllib.request.Request(
                request.official_url,
                headers={"User-Agent": "PassBidWriter/1.0"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                content = response.read(50 * 1024 * 1024 + 1)
            if len(content) > 50 * 1024 * 1024:
                raise ValueError("规范文件超过50MB限制")
            if not content.startswith(b"%PDF"):
                raise ValueError("官方地址没有返回PDF")
            target.write_bytes(content)
            attach_standard_file(
                run_id=request.run_id,
                state=state,
                standard_code=request.standard_code,
                target=target,
                official_url=request.official_url,
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"自动下载失败：{exc}") from exc
        _refresh_sections_and_metrics(state)
        _save_run_state(request.run_id, state)
        return _with_workflow(state)

    @app.get("/api/files")
    def get_file(path: str) -> FileResponse:
        resolved = Path(path).expanduser().resolve()
        allowed_roots = [settings.data_dir.resolve(), settings.root_dir.resolve()]
        if not any(root == resolved or root in resolved.parents for root in allowed_roots):
            raise HTTPException(status_code=403, detail="文件不在应用数据目录内")
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(resolved)

    dist = settings.root_dir / "workbench" / "dist"
    if dist.exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend(full_path: str) -> FileResponse:
            candidate = (dist / full_path).resolve()
            if candidate.exists() and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


async def _save_uploads(
    files: list[UploadFile],
    relative_paths: list[str],
    source_root: Path,
) -> list[str]:
    saved: list[str] = []
    for index, upload in enumerate(files):
        raw_relative = (
            relative_paths[index]
            if index < len(relative_paths)
            else upload.filename or f"file-{index + 1}"
        )
        relative = _safe_relative_path(raw_relative)
        target = (source_root / relative).resolve()
        if source_root.resolve() not in target.parents:
            raise HTTPException(status_code=400, detail="文件路径不安全")
        target.parent.mkdir(parents=True, exist_ok=True)
        await _save_upload(upload, target)
        saved.append(str(target))
    return saved


async def _save_upload(upload: UploadFile, target: Path) -> None:
    with target.open("wb") as destination:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            destination.write(chunk)


def _queue_action(
    run_id: int,
    action: str,
    background_tasks: BackgroundTasks,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_state(run_id)
    try:
        job = create_job(action, run_id=run_id, metadata=metadata)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(run_job, int(job["id"]))
    return _with_workflow(_require_state(run_id))


def _require_state(run_id: int) -> dict[str, Any]:
    state = get_run_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="生产任务不存在")
    return state


def _with_workflow(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state.get("run_id")
    jobs = list_jobs(int(run_id), 12) if run_id else list_jobs(None, 12)
    state["workflow"] = {
        "status": "idle",
        "action": "",
        "message": "等待操作",
        "error": "",
        **state.get("workflow", {}),
    }
    state["workflow_jobs"] = jobs
    return state


def _list_projects() -> list[dict[str, Any]]:
    settings = get_settings()
    with db.db_session(settings.database_path) as conn:
        rows = conn.execute(
            "SELECT id, state_json, updated_at FROM production_runs ORDER BY id DESC"
        ).fetchall()
    result: list[dict[str, Any]] = []
    seen_dirs: set[str] = set()
    for row in rows:
        state = json.loads(row["state_json"] or "{}")
        project = state.get("project", {})
        project_dir = str(project.get("project_dir", ""))
        if not project_dir or project_dir in seen_dirs:
            continue
        seen_dirs.add(project_dir)
        result.append(
            {
                "run_id": int(row["id"]),
                "name": project.get("name", ""),
                "project_type": project.get("project_type", ""),
                "project_dir": project_dir,
                "status": state.get("status", ""),
                "stage": state.get("stage", ""),
                "updated_at": row["updated_at"],
            }
        )
    return result


def _delete_project(run_id: int) -> dict[str, Any] | None:
    settings = get_settings()
    with db.db_session(settings.database_path) as conn:
        deleted = db.delete_project_with_runs(conn, run_id=run_id)
    if deleted is None:
        return None
    project_dir = Path(str(deleted.get("project_dir", ""))).expanduser()
    files_removed = False
    if str(project_dir):
        root = settings.projects_dir.resolve()
        target = project_dir.resolve()
        if target != root and root in target.parents and target.exists():
            try:
                shutil.rmtree(target)
                files_removed = True
            except OSError as exc:
                deleted["file_cleanup_error"] = str(exc)
    deleted["files_removed"] = files_removed
    return deleted


def _refresh_sections_and_metrics(state: dict[str, Any]) -> None:
    for section in state.get("sections", []):
        if section.get("status") in {"generated", "awaiting_approval"}:
            continue
        section["missing_inputs"] = [
            item
            for item in section.get("required_inputs", [])
            if not _input_is_available(
                item,
                state.get("facts", []),
                state.get("requirements", {}),
                state.get("standards", []),
            )
        ]
        section["status"] = "ready" if not section["missing_inputs"] else "needs_input"
    metrics = state.setdefault("metrics", {})
    metrics["fact_count"] = len(state.get("facts", []))
    metrics["open_confirmations"] = sum(
        1 for item in state.get("confirmations", []) if item.get("status") == "open"
    )
    metrics["high_risks"] = sum(
        1
        for item in state.get("confirmations", [])
        if item.get("status") == "open" and item.get("severity") == "high"
    )
    standards = state.get("standards", [])
    ready = sum(
        1 for item in standards if item.get("status") in {"available", "not_applicable"}
    )
    metrics["standards_ready"] = ready
    metrics["standards_readiness"] = round(ready / len(standards) * 100) if standards else 100
    evidence_links = state.get("evidence_links", [])
    resolved_links = sum(
        1 for item in evidence_links if item.get("status") == "resolved"
    )
    metrics["reference_link_count"] = len(evidence_links)
    metrics["reference_link_resolved"] = resolved_links
    metrics["reference_link_readiness"] = (
        round(resolved_links / len(evidence_links) * 100)
        if evidence_links
        else 100
    )


def _resolve_drawing_confirmation(state: dict[str, Any]) -> None:
    available = {
        str(item.get("source_dwg_path", ""))
        for item in state.get("drawings", [])
        if item.get("source_pdf_path")
    }
    for item in state.get("confirmations", []):
        if item.get("category") != "图纸待转换":
            continue
        if str(item.get("source_path", "")) in available:
            item["status"] = "resolved"
            item["resolution"] = "已关联图纸PDF"


def _new_import_root(base: Path, name: str) -> Path:
    safe = _safe_filename(name.strip()) or "project"
    return base / f"{uuid.uuid4().hex[:10]}-{safe}"


def _safe_relative_path(value: str) -> Path:
    normalized = str(value or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise HTTPException(status_code=400, detail="文件夹中包含不安全路径")
    safe_parts = [_safe_filename(part) for part in parts]
    if any(not part for part in safe_parts):
        raise HTTPException(status_code=400, detail="文件名无效")
    return Path(*safe_parts)


def _safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", Path(value).name).strip(" .")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env_values(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# PassBidWriter local model configuration",
        "# This file stays under LOCALAPPDATA and must not be committed.",
    ]
    for key in sorted(values):
        escaped = values[key].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _empty_dashboard() -> dict[str, Any]:
    blueprint = build_blueprint("水利工程通用")
    sections = [
        {
            **section,
            "project_basis": [],
            "reference_basis": [f"蓝图：{blueprint['title']} {blueprint['version']}"],
            "missing_inputs": section["required_inputs"],
            "completion": 0,
            "status": "needs_input",
            "model": "deepseek",
        }
        for section in blueprint["sections"]
    ]
    return {
        "run_id": None,
        "project": {
            "name": "尚未导入项目",
            "project_dir": "",
            "project_type": "水利工程通用",
            "file_count": 0,
        },
        "stage": "资料导入",
        "stage_index": 1,
        "status": "empty",
        "files": [],
        "requirements": {},
        "standards": [],
        "standard_clauses": [],
        "case_assets": [],
        "visual_jobs": [],
        "drawings": [],
        "facts": [],
        "sections": sections,
        "confirmations": [],
        "model_differences": [],
        "models": ModelRouter().status(),
        "blueprint": blueprint,
        "metrics": {
            "requirement_count": 0,
            "requirement_coverage": 0,
            "file_count": 0,
            "fact_count": 0,
            "standards_count": 0,
            "standards_ready": 0,
            "standards_readiness": 0,
            "section_count": len(sections),
            "chapter_completion": 0,
            "open_confirmations": 0,
            "high_risks": 0,
        },
        "reports": {},
    }


app = create_app()
