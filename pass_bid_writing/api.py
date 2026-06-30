from __future__ import annotations

import json
import shutil
import urllib.parse
import urllib.request
import threading
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .blueprints import build_blueprint
from .config import ensure_storage_dirs, get_settings
from .model_router import ModelRouter
from .knowledge import attach_standard_file
from .production import (
    _save_run_state,
    confirm_file_roles,
    confirm_task_spec,
    generate_production_docx,
    get_run_state,
    mark_generation_failed,
    mark_generation_started,
    prepare_production_project,
    review_production_draft,
)
from .reports import export_production_reports
from .visual_sources import analyze_visual_sources


class PrepareRequest(BaseModel):
    project_dir: str
    project_type: str = "水利工程通用"
    expand_archives: bool = True


class ConfirmRequest(BaseModel):
    confirmed: bool = True


class OfficialFetchRequest(BaseModel):
    run_id: int
    standard_code: str
    official_url: str


class FileRoleRequest(BaseModel):
    path: str
    role: str


class ResolutionRequest(BaseModel):
    status: str = "resolved"
    resolution: str = ""


class CaseFolderRequest(BaseModel):
    project_dir: str
    project_type: str = ""
    region: str = "浙江"
    tags: str = ""
    auto_visual: bool = True


class StandardStatusRequest(BaseModel):
    run_id: int
    standard_code: str
    status: str
    resolution: str = ""


OFFICIAL_HOST_SUFFIXES = (
    ".gov.cn",
    "gov.cn",
    "openstd.samr.gov.cn",
    "mwr.gov.cn",
    "zj.gov.cn",
)

ACTIVE_GENERATIONS: set[int] = set()
ACTIVE_VISUAL_ANALYSES: set[int] = set()
ACTIVE_LOCK = threading.Lock()


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_storage_dirs(settings)
    db.init_db(settings.database_path)
    app = FastAPI(title="施工组织设计生产工作台", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "models": ModelRouter().status()}

    @app.get("/api/dashboard")
    def dashboard(run_id: int | None = None) -> dict[str, Any]:
        state = get_run_state(run_id)
        return state or _empty_dashboard()

    @app.post("/api/projects/prepare")
    def prepare(request: PrepareRequest) -> dict[str, Any]:
        try:
            return prepare_production_project(
                request.project_dir,
                project_type=request.project_type,
                expand_archives=request.expand_archives,
            )
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cases/ingest")
    def ingest_case(request: CaseFolderRequest) -> dict[str, Any]:
        from .mcp_server import writing_ingest_passed_case

        try:
            return writing_ingest_passed_case(
                request.project_dir,
                auto_visual=request.auto_visual,
                project_type=request.project_type,
                region=request.region,
                tags=request.tags,
            )
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/confirm-task-spec")
    def confirm(run_id: int, request: ConfirmRequest) -> dict[str, Any]:
        if not request.confirmed:
            raise HTTPException(status_code=400, detail="任务书未确认")
        try:
            return confirm_task_spec(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/confirm-file-roles")
    def confirm_roles(run_id: int) -> dict[str, Any]:
        try:
            return confirm_file_roles(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/analyze-visuals", status_code=202)
    def analyze_visuals(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        state = get_run_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        if state.get("status") not in {"visual_analysis_pending", "visual_analysis_failed", "analyzing_visuals"}:
            raise HTTPException(status_code=409, detail="当前任务不在多模态资料分析阶段")
        with ACTIVE_LOCK:
            if run_id in ACTIVE_VISUAL_ANALYSES:
                raise HTTPException(status_code=409, detail="多模态资料分析已在运行")
            ACTIVE_VISUAL_ANALYSES.add(run_id)
        state["status"] = "analyzing_visuals"
        state["stage"] = "证据提取"
        state["stage_index"] = 3
        state.setdefault("visual_analysis", {})["status"] = "running"
        _save_state(run_id, state)
        background_tasks.add_task(_run_visual_analysis_safely, run_id)
        return state

    @app.post("/api/runs/{run_id}/export-reports")
    def export_reports(run_id: int) -> dict[str, str]:
        state = get_run_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        output_dir = Path(state["project"]["project_dir"]) / "outputs"
        reports = export_production_reports(state, output_dir)
        state["reports"] = reports
        _save_state(run_id, state)
        return reports

    @app.post("/api/runs/{run_id}/review-draft")
    def review_draft(run_id: int) -> dict[str, Any]:
        try:
            return review_production_draft(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/generate-docx", status_code=202)
    def generate_docx(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
        try:
            with ACTIVE_LOCK:
                if run_id in ACTIVE_GENERATIONS:
                    raise HTTPException(status_code=409, detail="章节生成任务已在运行")
                ACTIVE_GENERATIONS.add(run_id)
            state = mark_generation_started(run_id)
            background_tasks.add_task(_run_generation_safely, run_id)
            return state
        except ValueError as exc:
            with ACTIVE_LOCK:
                ACTIVE_GENERATIONS.discard(run_id)
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch("/api/runs/{run_id}/files/role")
    def update_file_role(run_id: int, request: FileRoleRequest) -> dict[str, Any]:
        state = get_run_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        allowed = {
            "tender", "design_report", "budget", "drawing", "standard",
            "accepted_bid", "attachment",
        }
        if request.role not in allowed:
            raise HTTPException(status_code=400, detail="不支持的文件角色")
        target = str(Path(request.path).expanduser().resolve())
        if not any(str(Path(item["path"]).resolve()) == target for item in state.get("files", [])):
            raise HTTPException(status_code=404, detail="项目中不存在该文件")
        overrides = {item["path"]: item.get("role", "attachment") for item in state["files"]}
        overrides[target] = request.role
        try:
            return prepare_production_project(
                state["project"]["project_dir"],
                project_type=state["project"]["project_type"],
                expand_archives=False,
                role_overrides=overrides,
            )
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/runs/{run_id}/confirmations/{item_index}")
    def resolve_confirmation(
        run_id: int,
        item_index: int,
        request: ResolutionRequest,
    ) -> dict[str, Any]:
        state = get_run_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        if request.status not in {"open", "resolved", "dismissed"}:
            raise HTTPException(status_code=400, detail="不支持的确认状态")
        items = state.get("confirmations", [])
        if item_index < 0 or item_index >= len(items):
            raise HTTPException(status_code=404, detail="待确认事项不存在")
        items[item_index]["status"] = request.status
        items[item_index]["resolution"] = request.resolution
        state["metrics"]["open_confirmations"] = sum(
            1 for item in items if item.get("status") == "open"
        )
        state["metrics"]["high_risks"] = sum(
            1
            for item in items
            if item.get("status") == "open" and item.get("severity") == "high"
        )
        _save_state(run_id, state)
        return state

    @app.patch("/api/runs/{run_id}/model-differences/{item_index}")
    def resolve_model_difference(
        run_id: int,
        item_index: int,
        request: ResolutionRequest,
    ) -> dict[str, Any]:
        state = get_run_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        items = state.get("model_differences", [])
        if item_index < 0 or item_index >= len(items):
            raise HTTPException(status_code=404, detail="模型差异不存在")
        items[item_index]["status"] = request.status
        items[item_index]["resolution"] = request.resolution
        _save_state(run_id, state)
        return state

    @app.post("/api/standards/upload")
    async def upload_standard(
        run_id: int,
        standard_code: str,
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        state = get_run_state(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        standards_dir = Path(state["project"]["project_dir"]) / ".production" / "standards"
        standards_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename or f"{standard_code}.pdf").name
        target = standards_dir / safe_name
        with target.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
        try:
            result = attach_standard_file(
                run_id=run_id,
                state=state,
                standard_code=standard_code,
                target=target,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _refresh_state_metrics(state)
        state["reports"] = export_production_reports(
            state,
            Path(state["project"]["project_dir"]) / "outputs",
        )
        _save_state(run_id, state)
        return {
            "status": "available",
            "standard_code": standard_code,
            "local_path": str(target),
            "clause_count": len(result["clauses"]),
        }

    @app.post("/api/standards/fetch")
    def fetch_standard(request: OfficialFetchRequest) -> dict[str, Any]:
        state = get_run_state(request.run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        host = (urllib.parse.urlparse(request.official_url).hostname or "").lower()
        if not any(host == suffix or host.endswith(suffix) for suffix in OFFICIAL_HOST_SUFFIXES):
            raise HTTPException(status_code=400, detail="仅允许从政府或标准主管部门官方域名下载")
        standards_dir = Path(state["project"]["project_dir"]) / ".production" / "standards"
        standards_dir.mkdir(parents=True, exist_ok=True)
        target = standards_dir / f"{_safe_name(request.standard_code)}.pdf"
        try:
            req = urllib.request.Request(
                request.official_url,
                headers={"User-Agent": "PassBidWriter/1.0"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                content_type = response.headers.get("Content-Type", "")
                content = response.read(50 * 1024 * 1024 + 1)
            if len(content) > 50 * 1024 * 1024:
                raise ValueError("规范文件超过50MB限制")
            if "pdf" not in content_type.lower() and not content.startswith(b"%PDF"):
                raise ValueError("官方地址没有返回PDF文件")
            target.write_bytes(content)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"自动下载失败，请按待下载清单人工获取：{exc}",
            ) from exc
        try:
            result = attach_standard_file(
                run_id=request.run_id,
                state=state,
                standard_code=request.standard_code,
                target=target,
                official_url=request.official_url,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _refresh_state_metrics(state)
        state["reports"] = export_production_reports(
            state,
            Path(state["project"]["project_dir"]) / "outputs",
        )
        _save_state(request.run_id, state)
        return {
            "status": "available",
            "standard_code": request.standard_code,
            "local_path": str(target),
            "clause_count": len(result["clauses"]),
        }

    @app.patch("/api/standards/status")
    def set_standard_status(request: StandardStatusRequest) -> dict[str, Any]:
        state = get_run_state(request.run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="生产任务不存在")
        allowed = {"pending_download", "available", "not_applicable", "needs_confirmation"}
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
        if request.status == "not_applicable":
            for item in state.get("confirmations", []):
                if (
                    item.get("category") == "规范待下载"
                    and request.standard_code.replace(" ", "")
                    in item.get("title", "").replace(" ", "")
                ):
                    item["status"] = "resolved"
                    item["resolution"] = request.resolution or "人工确认本项目不适用"
        _refresh_state_metrics(state)
        _save_state(request.run_id, state)
        return state

    @app.get("/api/files")
    def get_file(path: str) -> FileResponse:
        resolved = Path(path).expanduser().resolve()
        allowed_roots = [settings.root_dir.resolve(), settings.storage_dir.resolve()]
        if not any(root == resolved or root in resolved.parents for root in allowed_roots):
            raise HTTPException(status_code=403, detail="文件不在工作区内")
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


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in value)


def _save_state(run_id: int, state: dict[str, Any]) -> None:
    _save_run_state(run_id, state)


def _refresh_state_metrics(state: dict[str, Any]) -> None:
    standards = state.get("standards", [])
    confirmations = state.get("confirmations", [])
    ready = sum(
        1 for item in standards if item.get("status") in {"available", "not_applicable"}
    )
    state["metrics"]["standards_ready"] = ready
    state["metrics"]["standards_readiness"] = (
        round(ready / len(standards) * 100) if standards else 100
    )
    state["metrics"]["open_confirmations"] = sum(
        1 for item in confirmations if item.get("status") == "open"
    )
    state["metrics"]["high_risks"] = sum(
        1
        for item in confirmations
        if item.get("status") == "open" and item.get("severity") == "high"
    )


def _run_generation_safely(run_id: int) -> None:
    try:
        generate_production_docx(run_id)
    except Exception as exc:
        mark_generation_failed(run_id, str(exc))
    finally:
        with ACTIVE_LOCK:
            ACTIVE_GENERATIONS.discard(run_id)


def _run_visual_analysis_safely(run_id: int) -> None:
    try:
        analyze_visual_sources(run_id)
    except Exception as exc:
        state = get_run_state(run_id)
        if state is None:
            return
        state["status"] = "visual_analysis_failed"
        state.setdefault("visual_analysis", {})["status"] = "failed"
        state["visual_analysis"]["error"] = str(exc)
        state.setdefault("confirmations", []).append(
            {
                "category": "视觉分析失败",
                "title": "多模态资料分析未完成",
                "detail": str(exc),
                "severity": "high",
                "affected_sections": ["全局"],
                "status": "open",
                "recommended_action": "检查视觉模型配置或源文件后重新运行。",
            }
        )
        _save_state(run_id, state)
    finally:
        with ACTIVE_LOCK:
            ACTIVE_VISUAL_ANALYSES.discard(run_id)


def _empty_dashboard() -> dict[str, Any]:
    blueprint = build_blueprint("水利工程通用")
    sections = []
    for index, section in enumerate(blueprint["sections"]):
        sections.append(
            {
                "code": section["code"],
                "title": section["title"],
                "purpose": section["purpose"],
                "required_inputs": section["required_inputs"],
                "components": section["components"],
                "acceptance": section["acceptance"],
                "project_basis": [],
                "reference_basis": [f"蓝图：{blueprint['title']} {blueprint['version']}"],
                "missing_inputs": section["required_inputs"],
                "completion": 0 if index > 3 else 20 + index * 8,
                "status": "needs_input",
                "model": "deepseek-v4-pro",
            }
        )
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
        "standards": [],
        "standard_clauses": [],
        "case_assets": [],
        "visual_jobs": [],
        "visual_analysis": {"status": "not_started", "total": 0, "completed": 0, "failed": 0, "needs_review": 0},
        "facts": [],
        "sections": sections,
        "confirmations": [
            {
                "category": "下一步",
                "title": "导入一个待编制项目",
                "detail": "选择包含招标文件、初设、预算和图纸的项目资料夹。",
                "severity": "medium",
                "affected_sections": [],
                "status": "open",
            }
        ],
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
            "chapter_completion": 8,
            "open_confirmations": 1,
            "high_risks": 0,
        },
        "reports": {},
    }


app = create_app()
