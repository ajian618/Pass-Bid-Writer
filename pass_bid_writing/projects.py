from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any


DOCUMENT_SUFFIXES = {
    ".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls",
    ".csv", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".dwg", ".dxf",
}
ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar"}
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
    _mark_duplicate_files(files)
    return _project_summary(project_dir, kind, files)


def expand_project_archives(project_dir: Path) -> dict[str, Any]:
    """Safely expand ZIP inputs into a deterministic project-local cache."""
    project_dir = project_dir.expanduser().resolve()
    extraction_root = project_dir / "extracted"
    extracted: list[str] = []
    skipped: list[dict[str, str]] = []
    for archive in project_dir.rglob("*"):
        if not archive.is_file() or archive.suffix.lower() not in ARCHIVE_SUFFIXES:
            continue
        relative_parts = archive.relative_to(project_dir).parts
        if "extracted" in relative_parts or "outputs" in relative_parts:
            continue
        target = extraction_root / archive.stem
        target.mkdir(parents=True, exist_ok=True)
        try:
            if archive.suffix.lower() == ".zip":
                with zipfile.ZipFile(archive) as package:
                    for member in package.infolist():
                        candidate = _safe_archive_target(target, member.filename)
                        if candidate is None:
                            skipped.append({"archive": str(archive), "member": member.filename, "reason": "unsafe_path"})
                            continue
                        if member.is_dir():
                            candidate.mkdir(parents=True, exist_ok=True)
                            continue
                        candidate.parent.mkdir(parents=True, exist_ok=True)
                        if not candidate.exists() or candidate.stat().st_size != member.file_size:
                            with package.open(member) as source, candidate.open("wb") as destination:
                                destination.write(source.read())
                        extracted.append(str(candidate))
            elif archive.suffix.lower() == ".7z":
                import py7zr  # type: ignore

                with py7zr.SevenZipFile(archive, mode="r") as package:
                    names = package.getnames()
                    safe_names = [
                        name for name in names if _safe_archive_target(target, name) is not None
                    ]
                    for name in set(names).difference(safe_names):
                        skipped.append({"archive": str(archive), "member": name, "reason": "unsafe_path"})
                    package.extract(path=target, targets=safe_names)
                    extracted.extend(
                        str(_safe_archive_target(target, name))
                        for name in safe_names
                        if _safe_archive_target(target, name) is not None
                        and _safe_archive_target(target, name).is_file()
                    )
            else:
                import rarfile  # type: ignore

                with rarfile.RarFile(archive) as package:
                    for member in package.infolist():
                        candidate = _safe_archive_target(target, member.filename)
                        if candidate is None:
                            skipped.append({"archive": str(archive), "member": member.filename, "reason": "unsafe_path"})
                            continue
                        if member.isdir():
                            candidate.mkdir(parents=True, exist_ok=True)
                            continue
                        candidate.parent.mkdir(parents=True, exist_ok=True)
                        with package.open(member) as source, candidate.open("wb") as destination:
                            destination.write(source.read())
                        extracted.append(str(candidate))
        except Exception as exc:
            skipped.append({"archive": str(archive), "member": "", "reason": str(exc)})
    return {"root": str(extraction_root), "extracted": extracted, "skipped": skipped}


def _safe_archive_target(root: Path, member_name: str) -> Path | None:
    candidate = (root / member_name).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        return None
    return candidate


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
    ignored_dirs = {"outputs", "drawings", "assets", "__pycache__", ".git", ".cache"}
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
        "sha256": _file_sha256(path),
        "role": role,
        "confidence": confidence,
        "reason": reason,
    }


def _classify_role(name: str, project_kind: str) -> tuple[str, float, str]:
    text = name.lower()
    normalized = re.sub(r"[\s_\-（）()【】\[\]]+", "", text)
    tender_words = ("招标", "招標", "招标文件", "tender", "zhaobiao")
    bid_words = ("技术标", "技術標", "投标文件", "投標文件", "施工组织设计", "已通过", "passed", "bid")
    design_words = ("初步设计", "初设", "批复稿", "可研", "设计报告")
    budget_words = ("预算", "工程量清单", "招标控制价", "清单")
    drawing_words = ("图纸", "施工图", "总平", "平面图", "cad", "dwg", "dxf")
    standard_words = ("规范", "规程", "标准", "导则")
    if any(word in normalized for word in design_words):
        return "design_report", 0.86, "filename contains design report marker"
    if any(word in normalized for word in budget_words):
        return "budget", 0.84, "filename contains budget marker"
    if any(word in normalized for word in drawing_words) or Path(name).suffix.lower() in {".dwg", ".dxf"}:
        return "drawing", 0.84, "filename or suffix contains drawing marker"
    if any(word in normalized for word in standard_words):
        return "standard", 0.78, "filename contains standard marker"
    if any(word in normalized for word in tender_words):
        return "tender", 0.92, "filename contains tender marker"
    if project_kind == "passed_case" and any(word in normalized for word in bid_words):
        return "accepted_bid", 0.88, "filename contains accepted bid marker"
    if project_kind == "new_tender":
        return "candidate_tender", 0.45, "new tender project primary document candidate"
    return "attachment", 0.35, "supporting document"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mark_duplicate_files(files: list[dict[str, Any]]) -> None:
    first_by_hash: dict[str, str] = {}
    for item in files:
        digest = item.get("sha256", "")
        if not digest:
            continue
        if digest in first_by_hash:
            item["is_duplicate"] = True
            item["duplicate_of"] = first_by_hash[digest]
            item["reason"] = f"duplicate of {first_by_hash[digest]}"
        else:
            first_by_hash[digest] = item["path"]
            item["is_duplicate"] = False
            item["duplicate_of"] = ""


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
    matches = [
        item for item in files
        if item.get("role") == role and not item.get("is_duplicate")
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda item: (-float(item["confidence"]), item["name"]))[0]


def _first_primary_document(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        item for item in files
        if item.get("suffix") in {".pdf", ".doc", ".docx", ".txt", ".md"}
        and not item.get("is_duplicate")
    ]
    return candidates[0] if candidates else None


def _first_non_tender_document(
    files: list[dict[str, Any]],
    tender: dict[str, Any] | None,
) -> dict[str, Any] | None:
    tender_path = tender.get("path") if tender else ""
    candidates = [
        item
        for item in files
        if item.get("path") != tender_path
        and item.get("suffix") in {".pdf", ".doc", ".docx", ".txt", ".md"}
        and not item.get("is_duplicate")
    ]
    return candidates[0] if candidates else None
