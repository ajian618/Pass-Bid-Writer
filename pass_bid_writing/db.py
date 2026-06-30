from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _json_load(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def connect(database_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(database_path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    ddl: str,
) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


@contextmanager
def db_session(database_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(database_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with db_session(database_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS case_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                project_type TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '浙江',
                tags TEXT NOT NULL DEFAULT '',
                tender_path TEXT NOT NULL,
                bid_path TEXT NOT NULL,
                tender_text TEXT NOT NULL,
                bid_text TEXT NOT NULL,
                outline_json TEXT NOT NULL DEFAULT '[]',
                requirements_json TEXT NOT NULL DEFAULT '{}',
                patterns_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS writing_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                lesson TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'pass_bid_writing',
                tags TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'hermes',
                case_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES case_pairs(id)
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                tender_path TEXT NOT NULL DEFAULT '',
                project_dir TEXT NOT NULL DEFAULT '',
                layout_profile_id INTEGER,
                requirements_json TEXT NOT NULL DEFAULT '{}',
                response_matrix_json TEXT NOT NULL DEFAULT '[]',
                outline_json TEXT NOT NULL DEFAULT '[]',
                section_contents_json TEXT NOT NULL DEFAULT '{}',
                docx_path TEXT NOT NULL DEFAULT '',
                pdf_path TEXT NOT NULL DEFAULT '',
                compliance_json TEXT NOT NULL DEFAULT '{}',
                visual_report_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                project_kind TEXT NOT NULL,
                project_dir TEXT NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_kind, project_dir)
            );

            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                suffix TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'attachment',
                confidence REAL NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, file_path),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS layout_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_kind TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                profile_json TEXT NOT NULL DEFAULT '{}',
                render_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS visual_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_path TEXT NOT NULL,
                analysis_type TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                analysis_json TEXT NOT NULL DEFAULT '{}',
                render_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS production_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                project_type TEXT NOT NULL DEFAULT '水利工程通用',
                stage TEXT NOT NULL DEFAULT '资料导入',
                status TEXT NOT NULL DEFAULT 'draft',
                state_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS standard_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                standard_code TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                version TEXT NOT NULL DEFAULT '',
                source_page INTEGER,
                source_path TEXT NOT NULL DEFAULT '',
                official_url TEXT NOT NULL DEFAULT '',
                local_path TEXT NOT NULL DEFAULT '',
                sha256 TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending_download',
                affected_sections_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE TABLE IF NOT EXISTS standard_clauses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                standard_code TEXT NOT NULL,
                clause_id TEXT NOT NULL DEFAULT '',
                clause_text TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_page INTEGER,
                applicable_sections_json TEXT NOT NULL DEFAULT '[]',
                applicability TEXT NOT NULL DEFAULT '',
                mandatory_level TEXT NOT NULL DEFAULT 'unknown',
                verification_status TEXT NOT NULL DEFAULT 'verified_local_source',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE TABLE IF NOT EXISTS case_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                case_id INTEGER NOT NULL,
                asset_key TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content_json TEXT NOT NULL DEFAULT '{}',
                applicable_sections_json TEXT NOT NULL DEFAULT '[]',
                reuse_rule TEXT NOT NULL DEFAULT 'structure_only',
                source_path TEXT NOT NULL DEFAULT '',
                layout_profile_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id),
                FOREIGN KEY(case_id) REFERENCES case_pairs(id)
            );

            CREATE TABLE IF NOT EXISTS content_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                section_code TEXT NOT NULL,
                component_id TEXT NOT NULL,
                component_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                required INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'not_started',
                source_path TEXT NOT NULL DEFAULT '',
                basis_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE TABLE IF NOT EXISTS project_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                fact_key TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                unit TEXT NOT NULL DEFAULT '',
                source_path TEXT NOT NULL DEFAULT '',
                source_page INTEGER,
                source_excerpt TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'extracted',
                created_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE TABLE IF NOT EXISTS section_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                section_code TEXT NOT NULL,
                title TEXT NOT NULL,
                purpose TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'not_started',
                completion INTEGER NOT NULL DEFAULT 0,
                requirements_json TEXT NOT NULL DEFAULT '[]',
                inputs_json TEXT NOT NULL DEFAULT '[]',
                acceptance_json TEXT NOT NULL DEFAULT '[]',
                components_json TEXT NOT NULL DEFAULT '[]',
                basis_json TEXT NOT NULL DEFAULT '{}',
                content_text TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE TABLE IF NOT EXISTS confirmation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT 'medium',
                affected_sections_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'open',
                resolution TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE TABLE IF NOT EXISTS model_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_run_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                task_type TEXT NOT NULL,
                input_basis_json TEXT NOT NULL DEFAULT '[]',
                result_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(production_run_id) REFERENCES production_runs(id)
            );

            CREATE INDEX IF NOT EXISTS idx_case_pairs_title ON case_pairs(title);
            CREATE INDEX IF NOT EXISTS idx_case_pairs_type ON case_pairs(project_type);
            CREATE INDEX IF NOT EXISTS idx_lessons_scope ON writing_lessons(scope);
            CREATE INDEX IF NOT EXISTS idx_projects_kind ON projects(project_kind);
            CREATE INDEX IF NOT EXISTS idx_project_files_role ON project_files(role);
            CREATE INDEX IF NOT EXISTS idx_layout_profiles_source ON layout_profiles(source_path);
            CREATE INDEX IF NOT EXISTS idx_visual_analyses_target ON visual_analyses(target_path);
            CREATE INDEX IF NOT EXISTS idx_production_runs_project ON production_runs(project_id);
            CREATE INDEX IF NOT EXISTS idx_standard_documents_run ON standard_documents(production_run_id);
            CREATE INDEX IF NOT EXISTS idx_standard_clauses_run ON standard_clauses(production_run_id);
            CREATE INDEX IF NOT EXISTS idx_case_assets_run ON case_assets(production_run_id);
            CREATE INDEX IF NOT EXISTS idx_content_components_run ON content_components(production_run_id);
            CREATE INDEX IF NOT EXISTS idx_project_facts_run ON project_facts(production_run_id);
            CREATE INDEX IF NOT EXISTS idx_section_tasks_run ON section_tasks(production_run_id);
            CREATE INDEX IF NOT EXISTS idx_confirmation_items_run ON confirmation_items(production_run_id);
            """
        )
        _add_column_if_missing(conn, "case_pairs", "project_dir", "project_dir TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "case_pairs", "layout_profile_id", "layout_profile_id INTEGER")
        _add_column_if_missing(conn, "drafts", "project_dir", "project_dir TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "drafts", "layout_profile_id", "layout_profile_id INTEGER")
        _add_column_if_missing(conn, "drafts", "visual_report_json", "visual_report_json TEXT NOT NULL DEFAULT '{}'")
        _add_column_if_missing(conn, "section_tasks", "content_text", "content_text TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "section_tasks", "model", "model TEXT NOT NULL DEFAULT ''")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key, default in (
        ("outline_json", []),
        ("requirements_json", {}),
        ("patterns_json", {}),
        ("response_matrix_json", []),
        ("section_contents_json", {}),
        ("compliance_json", {}),
        ("summary_json", {}),
        ("metadata_json", {}),
        ("profile_json", {}),
        ("render_json", {}),
        ("analysis_json", {}),
        ("visual_report_json", {}),
        ("state_json", {}),
        ("affected_sections_json", []),
        ("requirements_json", []),
        ("inputs_json", []),
        ("acceptance_json", []),
        ("components_json", []),
        ("basis_json", {}),
        ("input_basis_json", []),
        ("result_json", {}),
    ):
        if key in data:
            data[key.removesuffix("_json")] = _json_load(data.pop(key), default)
    return data


def create_case_pair(
    conn: sqlite3.Connection,
    *,
    title: str,
    project_type: str,
    region: str,
    tags: str,
    tender_path: str,
    bid_path: str,
    tender_text: str,
    bid_text: str,
    outline: list[dict[str, Any]],
    requirements: dict[str, Any],
    patterns: dict[str, Any],
    project_dir: str = "",
    layout_profile_id: int | None = None,
) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        INSERT INTO case_pairs (
            title, project_type, region, tags, tender_path, bid_path,
            tender_text, bid_text, outline_json, requirements_json,
            patterns_json, project_dir, layout_profile_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            project_type,
            region,
            tags,
            tender_path,
            bid_path,
            tender_text,
            bid_text,
            _json_dump(outline),
            _json_dump(requirements),
            _json_dump(patterns),
            project_dir,
            layout_profile_id,
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def get_case_pair(conn: sqlite3.Connection, case_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM case_pairs WHERE id = ?", (case_id,)).fetchone()
    return row_to_dict(row)


def search_case_pairs(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    project_type: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if query.strip():
        like = f"%{query.strip()}%"
        clauses.append(
            "(title LIKE ? OR tags LIKE ? OR tender_text LIKE ? OR bid_text LIKE ? OR patterns_json LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    if project_type.strip():
        clauses.append("project_type LIKE ?")
        params.append(f"%{project_type.strip()}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM case_pairs {where} ORDER BY updated_at DESC LIMIT ?",
        (*params, int(limit)),
    ).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]


def create_lesson(
    conn: sqlite3.Connection,
    *,
    title: str,
    lesson: str,
    scope: str,
    tags: str,
    source: str,
    case_id: int | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO writing_lessons (title, lesson, scope, tags, source, case_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, lesson, scope, tags, source, case_id, utc_now()),
    )
    return int(cur.lastrowid)


def search_lessons(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    scope: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if query.strip():
        like = f"%{query.strip()}%"
        clauses.append("(title LIKE ? OR lesson LIKE ? OR tags LIKE ?)")
        params.extend([like, like, like])
    if scope.strip():
        clauses.append("scope = ?")
        params.append(scope.strip())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM writing_lessons {where} ORDER BY created_at DESC LIMIT ?",
        (*params, int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def create_draft(
    conn: sqlite3.Connection,
    *,
    title: str,
    tender_path: str,
    requirements: dict[str, Any],
    response_matrix: list[dict[str, Any]],
    outline: list[dict[str, Any]],
    section_contents: dict[str, str],
    docx_path: str,
    project_dir: str = "",
    layout_profile_id: int | None = None,
    visual_report: dict[str, Any] | None = None,
) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        INSERT INTO drafts (
            title, tender_path, project_dir, layout_profile_id, requirements_json,
            response_matrix_json, outline_json, section_contents_json, docx_path,
            visual_report_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            tender_path,
            project_dir,
            layout_profile_id,
            _json_dump(requirements),
            _json_dump(response_matrix),
            _json_dump(outline),
            _json_dump(section_contents),
            docx_path,
            _json_dump(visual_report or {}),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def update_draft_pdf(conn: sqlite3.Connection, draft_id: int, pdf_path: str) -> None:
    conn.execute(
        "UPDATE drafts SET pdf_path = ?, updated_at = ? WHERE id = ?",
        (pdf_path, utc_now(), draft_id),
    )


def update_draft_compliance(
    conn: sqlite3.Connection,
    draft_id: int,
    compliance: dict[str, Any],
) -> None:
    conn.execute(
        "UPDATE drafts SET compliance_json = ?, updated_at = ? WHERE id = ?",
        (_json_dump(compliance), utc_now(), draft_id),
    )


def update_draft_visual_report(
    conn: sqlite3.Connection,
    draft_id: int,
    visual_report: dict[str, Any],
) -> None:
    conn.execute(
        "UPDATE drafts SET visual_report_json = ?, updated_at = ? WHERE id = ?",
        (_json_dump(visual_report), utc_now(), draft_id),
    )


def get_draft_by_docx(conn: sqlite3.Connection, docx_path: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM drafts WHERE docx_path = ?", (docx_path,)).fetchone()
    return row_to_dict(row)


def create_or_update_project(
    conn: sqlite3.Connection,
    *,
    name: str,
    project_kind: str,
    project_dir: str,
    summary: dict[str, Any],
) -> int:
    now = utc_now()
    existing = conn.execute(
        "SELECT id FROM projects WHERE project_kind = ? AND project_dir = ?",
        (project_kind, project_dir),
    ).fetchone()
    if existing:
        project_id = int(existing["id"])
        conn.execute(
            """
            UPDATE projects
            SET name = ?, summary_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, _json_dump(summary), now, project_id),
        )
        return project_id
    cur = conn.execute(
        """
        INSERT INTO projects (name, project_kind, project_dir, summary_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, project_kind, project_dir, _json_dump(summary), now, now),
    )
    return int(cur.lastrowid)


def upsert_project_file(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    file_path: str,
    file_name: str,
    suffix: str,
    role: str,
    confidence: float,
    metadata: dict[str, Any],
) -> int:
    now = utc_now()
    existing = conn.execute(
        "SELECT id FROM project_files WHERE project_id = ? AND file_path = ?",
        (project_id, file_path),
    ).fetchone()
    if existing:
        file_id = int(existing["id"])
        conn.execute(
            """
            UPDATE project_files
            SET file_name = ?, suffix = ?, role = ?, confidence = ?, metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (file_name, suffix, role, confidence, _json_dump(metadata), now, file_id),
        )
        return file_id
    cur = conn.execute(
        """
        INSERT INTO project_files (
            project_id, file_path, file_name, suffix, role, confidence,
            metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            file_path,
            file_name,
            suffix,
            role,
            confidence,
            _json_dump(metadata),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def create_layout_profile(
    conn: sqlite3.Connection,
    *,
    source_path: str,
    source_kind: str,
    provider: str,
    model: str,
    status: str,
    profile: dict[str, Any],
    render: dict[str, Any],
) -> int:
    cur = conn.execute(
        """
        INSERT INTO layout_profiles (
            source_path, source_kind, provider, model, status,
            profile_json, render_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_path,
            source_kind,
            provider,
            model,
            status,
            _json_dump(profile),
            _json_dump(render),
            utc_now(),
        ),
    )
    return int(cur.lastrowid)


def get_layout_profile(conn: sqlite3.Connection, layout_profile_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM layout_profiles WHERE id = ?", (layout_profile_id,)).fetchone()
    return row_to_dict(row)


def latest_layout_profile_for_source(conn: sqlite3.Connection, source_path: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM layout_profiles WHERE source_path = ? ORDER BY id DESC LIMIT 1",
        (source_path,),
    ).fetchone()
    return row_to_dict(row)


def create_visual_analysis(
    conn: sqlite3.Connection,
    *,
    target_path: str,
    analysis_type: str,
    provider: str,
    model: str,
    status: str,
    analysis: dict[str, Any],
    render: dict[str, Any],
) -> int:
    cur = conn.execute(
        """
        INSERT INTO visual_analyses (
            target_path, analysis_type, provider, model, status,
            analysis_json, render_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target_path,
            analysis_type,
            provider,
            model,
            status,
            _json_dump(analysis),
            _json_dump(render),
            utc_now(),
        ),
    )
    return int(cur.lastrowid)
