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
                requirements_json TEXT NOT NULL DEFAULT '{}',
                response_matrix_json TEXT NOT NULL DEFAULT '[]',
                outline_json TEXT NOT NULL DEFAULT '[]',
                section_contents_json TEXT NOT NULL DEFAULT '{}',
                docx_path TEXT NOT NULL DEFAULT '',
                pdf_path TEXT NOT NULL DEFAULT '',
                compliance_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_case_pairs_title ON case_pairs(title);
            CREATE INDEX IF NOT EXISTS idx_case_pairs_type ON case_pairs(project_type);
            CREATE INDEX IF NOT EXISTS idx_lessons_scope ON writing_lessons(scope);
            """
        )


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
) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        INSERT INTO case_pairs (
            title, project_type, region, tags, tender_path, bid_path,
            tender_text, bid_text, outline_json, requirements_json,
            patterns_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        INSERT INTO drafts (
            title, tender_path, requirements_json, response_matrix_json,
            outline_json, section_contents_json, docx_path, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            tender_path,
            _json_dump(requirements),
            _json_dump(response_matrix),
            _json_dump(outline),
            _json_dump(section_contents),
            docx_path,
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


def get_draft_by_docx(conn: sqlite3.Connection, docx_path: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM drafts WHERE docx_path = ?", (docx_path,)).fetchone()
    return row_to_dict(row)
