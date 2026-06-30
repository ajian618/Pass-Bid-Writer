from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_files(*paths: Path) -> None:
    """Load local configuration without overriding process environment values."""
    for env_path in paths:
        if not env_path.exists():
            continue
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
    data_dir: Path
    config_dir: Path
    storage_dir: Path
    database_path: Path
    drafts_dir: Path
    projects_dir: Path
    cases_dir: Path
    logs_dir: Path
    vision_dir: Path
    render_dir: Path
    vision_enabled: str
    vision_provider: str
    vision_model: str


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    data_dir = Path(
        os.environ.get("PASS_BID_DATA_DIR", local_app_data / "PassBidWriter")
    ).expanduser().resolve()
    config_dir = data_dir / "config"
    load_env_files(config_dir / ".env", root / ".env")
    storage = data_dir / "database"
    projects = data_dir / "projects"
    cases = data_dir / "cases"
    logs = data_dir / "logs"
    vision_dir = storage / "vision"
    return Settings(
        root_dir=root,
        data_dir=data_dir,
        config_dir=config_dir,
        storage_dir=storage,
        database_path=storage / "pass_bid_writing.db",
        drafts_dir=storage / "drafts",
        projects_dir=projects,
        cases_dir=cases,
        logs_dir=logs,
        vision_dir=vision_dir,
        render_dir=vision_dir / "renders",
        vision_enabled=os.environ.get("PASS_BID_VISION_ENABLED", "auto").strip().lower() or "auto",
        vision_provider=os.environ.get("PASS_BID_VISION_PROVIDER", "aliyun_qwen").strip().lower()
        or "aliyun_qwen",
        vision_model=os.environ.get("PASS_BID_VISION_MODEL", "qwen3.7-plus").strip()
        or "qwen3.7-plus",
    )


def ensure_storage_dirs(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.drafts_dir.mkdir(parents=True, exist_ok=True)
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.cases_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.vision_dir.mkdir(parents=True, exist_ok=True)
    settings.render_dir.mkdir(parents=True, exist_ok=True)
