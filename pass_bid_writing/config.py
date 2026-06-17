from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_local_env(root: Path) -> None:
    """Load repo-local .env values without overriding profile/system env vars."""
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    storage_dir: Path
    database_path: Path
    drafts_dir: Path
    projects_dir: Path
    vision_dir: Path
    render_dir: Path
    vision_enabled: str
    vision_provider: str
    vision_model: str


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    load_local_env(root)
    storage = Path(os.environ.get("PASS_BID_WRITING_STORAGE_DIR", root / "storage"))
    storage = storage.expanduser().resolve()
    projects = Path(os.environ.get("PASS_BID_PROJECTS_DIR", root / "projects"))
    projects = projects.expanduser().resolve()
    vision_dir = Path(os.environ.get("PASS_BID_VISION_DIR", storage / "vision"))
    vision_dir = vision_dir.expanduser().resolve()
    return Settings(
        root_dir=root,
        storage_dir=storage,
        database_path=storage / "pass_bid_writing.db",
        drafts_dir=storage / "drafts",
        projects_dir=projects,
        vision_dir=vision_dir,
        render_dir=vision_dir / "renders",
        vision_enabled=os.environ.get("PASS_BID_VISION_ENABLED", "auto").strip().lower() or "auto",
        vision_provider=os.environ.get("PASS_BID_VISION_PROVIDER", "aliyun_qwen").strip().lower()
        or "aliyun_qwen",
        vision_model=os.environ.get("PASS_BID_VISION_MODEL", "qwen3.7-plus").strip()
        or "qwen3.7-plus",
    )


def ensure_storage_dirs(settings: Settings) -> None:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.drafts_dir.mkdir(parents=True, exist_ok=True)
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.vision_dir.mkdir(parents=True, exist_ok=True)
    settings.render_dir.mkdir(parents=True, exist_ok=True)
