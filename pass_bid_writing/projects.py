from __future__ import annotations

import re
from pathlib import Path
from typing import Any


DOCUMENT_SUFFIXES = {".pdf", ".docx", ".doc", ".txt", ".md"}
PASSED_ALIASES = ("passed_cases", "passed")
NEW_TENDER_ALIASES = ("new_tenders", "unpassed")


def resolve_projects_root(root: str, *, workspace_root: Path, default_root: Path) -> Path:
    if root.strip():
        candidate = Path(root).expanduser()
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        return candidate.resolve()
    return default_root.resolve()


def scan_projects(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    passed = _scan_kind(root, "passed_case", PASSED_ALIASES)
    new_tenders = _scan_kind(root, "new_tender", NEW_TENDER_ALIASES)
    return {
        "root": str(root),
        "recommended_dirs": {
            "passed_cases": str(root / "passed_cases"),
            "new_tenders": str(root / "new_tenders"),
        },
        "aliases": {
            "passed_cases": list(PASSED_ALIASES),
            "new_tenders": list(NEW_TENDER_ALIASES),
        },
        "passed_cases": passed,
        "new_tenders": new_tenders,
        "passed_case_count": len(passed),
        "new_tender_count": len(new_tenders),
    }


def scan_single_project(project_dir: Path, *, project_kind: str = "") -> dict[str, Any]:
    project_dir = project_dir.expanduser().resolve()
    if not project_dir.exists():
        raise ValueError(f"project_dir not found: {project_dir}")
    if not project_dir.is_dir():
        raise ValueError(f"project_dir is not a directory: {project_dir}")
    kind = project_kind or _infer_project_kind(project_dir)
    files = [_describe_file(path, kind) for path in _iter_document_files(project_dir)]
    files.sort(key=lambda item: (-float(item["confidence"]), item["name"]))
    return _project_summary(project_dir, kind, files)


def select_project_files(project: dict[str, Any]) -> dict[str, Any]:
    files = list(project.get("files", []))
    tender = _best_role(files, "tender")
    accepted = _best_role(files, "accepted_bid")
    if project.get("project_kind") == "new_tender" and tender is None:
        tender = _first_primary_document(files)
    if project.get("project_kind") == "passed_case":
        if tender is None:
            tender = _best_role(files, "tender")
        if accepted is None:
            accepted = _first_non_tender_document(files, tender)
    return {"tender": tender, "accepted_bid": accepted}


def _scan_kind(root: Path, project_kind: str, aliases: tuple[str, ...]) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for alias in aliases:
        container = root / alias
        if not container.exists():
            continue
        for child in sorted(container.iterdir(), key=lambda item: item.name):
            if child.is_dir() and child.resolve() not in seen:
                seen.add(child.resolve())
                projects.append(scan_single_project(child, project_kind=project_kind))
    return projects


def _infer_project_kind(project_dir: Path) -> str:
    parts = {part.lower() for part in project_dir.parts}
    if parts.intersection(PASSED_ALIASES):
        return "passed_case"
    if parts.intersection(NEW_TENDER_ALIASES):
        return "new_tender"
    return "unknown"


def _iter_document_files(project_dir: Path) -> list[Path]:
    ignored_dirs = {"outputs", "__pycache__", ".git", ".cache"}
    files: list[Path] = []
    for path in project_dir.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in DOCUMENT_SUFFIXES:
            files.append(path.resolve())
    return files


def _describe_file(path: Path, project_kind: str) -> dict[str, Any]:
    role, confidence, reason = _classify_role(path.name, project_kind)
    return {
        "path": str(path),
        "name": path.name,
        "suffix": path.suffix.lower(),
        "size": path.stat().st_size,
        "role": role,
        "confidence": confidence,
        "reason": reason,
    }


def _classify_role(name: str, project_kind: str) -> tuple[str, float, str]:
    text = name.lower()
    normalized = re.sub(r"[\s_\-（）()【】\[\]]+", "", text)
    tender_words = ("招标", "招標", "招标文件", "tender", "zhaobiao")
    bid_words = ("技术标", "技術標", "投标文件", "投標文件", "施工组织设计", "已通过", "passed", "bid")
    if any(word in normalized for word in tender_words):
        return "tender", 0.92, "filename contains tender marker"
    if project_kind == "passed_case" and any(word in normalized for word in bid_words):
        return "accepted_bid", 0.88, "filename contains accepted bid marker"
    if project_kind == "new_tender":
        return "candidate_tender", 0.45, "new tender project primary document candidate"
    return "attachment", 0.35, "supporting document"


def _project_summary(project_dir: Path, project_kind: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    selected = select_project_files({"project_kind": project_kind, "files": files})
    return {
        "name": project_dir.name,
        "project_kind": project_kind,
        "project_dir": str(project_dir),
        "files": files,
        "file_count": len(files),
        "selected": selected,
        "ready": _is_ready(project_kind, selected),
        "outputs_dir": str(project_dir / "outputs") if project_kind == "new_tender" else "",
    }


def _is_ready(project_kind: str, selected: dict[str, Any]) -> bool:
    if project_kind == "passed_case":
        return bool(selected.get("tender") and selected.get("accepted_bid"))
    if project_kind == "new_tender":
        return bool(selected.get("tender"))
    return False


def _best_role(files: list[dict[str, Any]], role: str) -> dict[str, Any] | None:
    matches = [item for item in files if item.get("role") == role]
    if not matches:
        return None
    return sorted(matches, key=lambda item: (-float(item["confidence"]), item["name"]))[0]


def _first_primary_document(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [item for item in files if item.get("suffix") in {".pdf", ".docx", ".txt", ".md"}]
    return candidates[0] if candidates else None


def _first_non_tender_document(
    files: list[dict[str, Any]],
    tender: dict[str, Any] | None,
) -> dict[str, Any] | None:
    tender_path = tender.get("path") if tender else ""
    candidates = [
        item
        for item in files
        if item.get("path") != tender_path and item.get("suffix") in {".pdf", ".docx", ".txt", ".md"}
    ]
    return candidates[0] if candidates else None
