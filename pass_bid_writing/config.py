from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    storage_dir: Path
    database_path: Path
    drafts_dir: Path


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    storage = Path(os.environ.get("PASS_BID_WRITING_STORAGE_DIR", root / "storage"))
    storage = storage.expanduser().resolve()
    return Settings(
        root_dir=root,
        storage_dir=storage,
        database_path=storage / "pass_bid_writing.db",
        drafts_dir=storage / "drafts",
    )


def ensure_storage_dirs(settings: Settings) -> None:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.drafts_dir.mkdir(parents=True, exist_ok=True)
