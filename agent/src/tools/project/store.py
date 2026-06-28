"""项目 / 里程碑 Section / 每日总结存储（project.db）。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra.config import get_data_dir
from infra.sqlite_store import ReusableSqliteStore

INBOX_PROJECT_NAME = "Inbox"
VALID_PROJECT_STATUS = ("planning", "active", "on_hold", "completed", "archived")
VALID_SECTION_STATUS = ("planning", "active", "on_hold", "completed", "archived")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active',
    start_at    TEXT,
    end_at      TEXT,
    owner       TEXT,
    remind_at   TEXT,
    is_inbox    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_inbox ON projects(is_inbox) WHERE is_inbox = 1;

CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    name        TEXT NOT NULL,
    start_at    TEXT,
    end_at      TEXT,
    owner       TEXT,
    goals       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sections_project ON sections(project_id);

CREATE TABLE IF NOT EXISTS section_daily_summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id   INTEGER NOT NULL,
    summary_date TEXT NOT NULL,
    progress     TEXT NOT NULL DEFAULT '',
    risks        TEXT NOT NULL DEFAULT '',
    challenges   TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE(section_id, summary_date)
);
CREATE INDEX IF NOT EXISTS idx_section_summaries_section ON section_daily_summaries(section_id);

CREATE TABLE IF NOT EXISTS project_docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    title       TEXT NOT NULL,
    file_path   TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);
"""


@dataclass
class ProjectRow:
    id: int
    name: str
    description: str
    status: str
    start_at: str | None
    end_at: str | None
    owner: str | None
    remind_at: str | None
    is_inbox: bool
    created_at: str
    updated_at: str


@dataclass
class SectionRow:
    id: int
    project_id: int
    name: str
    start_at: str | None
    end_at: str | None
    owner: str | None
    goals: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class SectionDailySummaryRow:
    id: int
    section_id: int
    summary_date: str
    progress: str
    risks: str
    challenges: str
    notes: str
    created_at: str
    updated_at: str


class ProjectStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or get_data_dir() / "project.db")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _project_from_db(row: sqlite3.Row) -> ProjectRow:
        return ProjectRow(
            id=int(row["id"]),
            name=row["name"],
            description=row["description"] or "",
            status=row["status"] or "active",
            start_at=row["start_at"],
            end_at=row["end_at"],
            owner=row["owner"],
            remind_at=row["remind_at"],
            is_inbox=bool(row["is_inbox"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _section_from_db(row: sqlite3.Row) -> SectionRow:
        return SectionRow(
            id=int(row["id"]),
            project_id=int(row["project_id"]),
            name=row["name"],
            start_at=row["start_at"],
            end_at=row["end_at"],
            owner=row["owner"],
            goals=row["goals"] or "",
            status=row["status"] or "active",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _summary_from_db(row: sqlite3.Row) -> SectionDailySummaryRow:
        return SectionDailySummaryRow(
            id=int(row["id"]),
            section_id=int(row["section_id"]),
            summary_date=row["summary_date"],
            progress=row["progress"] or "",
            risks=row["risks"] or "",
            challenges=row["challenges"] or "",
            notes=row["notes"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def ensure_inbox(self) -> ProjectRow:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE is_inbox = 1 LIMIT 1"
            ).fetchone()
            if row:
                return self._project_from_db(row)
            now = self._now()
            cur = conn.execute(
                """
                INSERT INTO projects
                    (name, description, status, is_inbox, created_at, updated_at)
                VALUES (?, ?, 'active', 1, ?, ?)
                """,
                (INBOX_PROJECT_NAME, "临时任务收件箱", now, now),
            )
            pid = int(cur.lastrowid)
        project = self.get_project(pid)
        assert project is not None
        return project

    def add_project(
        self,
        name: str,
        *,
        description: str = "",
        status: str = "active",
        start_at: str | None = None,
        end_at: str | None = None,
        owner: str | None = None,
        remind_at: str | None = None,
    ) -> ProjectRow:
        name = (name or "").strip()
        if not name:
            raise ValueError("项目名不能为空")
        if name == INBOX_PROJECT_NAME:
            raise ValueError("Inbox 为系统保留项目名")
        status = status if status in VALID_PROJECT_STATUS else "active"
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects
                    (name, description, status, start_at, end_at, owner, remind_at,
                     is_inbox, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (name, description, status, start_at, end_at, owner, remind_at, now, now),
            )
            pid = int(cur.lastrowid)
        row = self.get_project(pid)
        assert row is not None
        return row

    def get_project(self, project_id: int) -> ProjectRow | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._project_from_db(row) if row else None

    def list_projects(self, status: str = "", *, include_inbox: bool = True) -> list[ProjectRow]:
        clauses: list[str] = []
        params: list[Any] = []
        if status and status in VALID_PROJECT_STATUS:
            clauses.append("status = ?")
            params.append(status)
        else:
            clauses.append("status != 'archived'")
        if not include_inbox:
            clauses.append("is_inbox = 0")
        where = " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM projects WHERE {where} ORDER BY is_inbox DESC, id DESC",
                params,
            ).fetchall()
        return [self._project_from_db(r) for r in rows]

    def update_project(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        owner: str | None = None,
        remind_at: str | None = None,
        clear_reminder: bool = False,
    ) -> ProjectRow | None:
        row = self.get_project(project_id)
        if not row:
            return None
        if row.is_inbox and name and name.strip() != INBOX_PROJECT_NAME:
            raise ValueError("Inbox 项目不可重命名")
        fields: dict[str, Any] = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("项目名不能为空")
            fields["name"] = name
        if description is not None:
            fields["description"] = description
        if status is not None:
            if status not in VALID_PROJECT_STATUS:
                raise ValueError(f"无效状态：{status}")
            fields["status"] = status
        if start_at is not None:
            fields["start_at"] = start_at
        if end_at is not None:
            fields["end_at"] = end_at
        if owner is not None:
            fields["owner"] = owner
        if clear_reminder:
            fields["remind_at"] = None
        elif remind_at is not None:
            fields["remind_at"] = remind_at
        if not fields:
            return row
        fields["updated_at"] = self._now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE projects SET {sets} WHERE id = ?", [*fields.values(), project_id])
        return self.get_project(project_id)

    def add_section(
        self,
        project_id: int,
        name: str,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        owner: str | None = None,
        goals: str = "",
        status: str = "active",
    ) -> SectionRow:
        if not self.get_project(project_id):
            raise ValueError(f"项目 #{project_id} 不存在")
        name = (name or "").strip()
        if not name:
            raise ValueError("Section 名称不能为空")
        status = status if status in VALID_SECTION_STATUS else "active"
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sections
                    (project_id, name, start_at, end_at, owner, goals, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, name, start_at, end_at, owner, goals, status, now, now),
            )
            sid = int(cur.lastrowid)
        row = self.get_section(sid)
        assert row is not None
        return row

    def get_section(self, section_id: int) -> SectionRow | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
        return self._section_from_db(row) if row else None

    def list_sections(self, project_id: int, status: str = "") -> list[SectionRow]:
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        if status and status in VALID_SECTION_STATUS:
            clauses.append("status = ?")
            params.append(status)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM sections WHERE {where} ORDER BY start_at IS NULL, start_at, id",
                params,
            ).fetchall()
        return [self._section_from_db(r) for r in rows]

    def update_section(
        self,
        section_id: int,
        *,
        name: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        owner: str | None = None,
        goals: str | None = None,
        status: str | None = None,
    ) -> SectionRow | None:
        row = self.get_section(section_id)
        if not row:
            return None
        fields: dict[str, Any] = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Section 名称不能为空")
            fields["name"] = name
        if start_at is not None:
            fields["start_at"] = start_at
        if end_at is not None:
            fields["end_at"] = end_at
        if owner is not None:
            fields["owner"] = owner
        if goals is not None:
            fields["goals"] = goals
        if status is not None:
            if status not in VALID_SECTION_STATUS:
                raise ValueError(f"无效状态：{status}")
            fields["status"] = status
        if not fields:
            return row
        fields["updated_at"] = self._now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as conn:
            conn.execute(f"UPDATE sections SET {sets} WHERE id = ?", [*fields.values(), section_id])
        return self.get_section(section_id)

    def upsert_daily_summary(
        self,
        section_id: int,
        summary_date: str,
        *,
        progress: str = "",
        risks: str = "",
        challenges: str = "",
        notes: str = "",
    ) -> SectionDailySummaryRow:
        if not self.get_section(section_id):
            raise ValueError(f"Section #{section_id} 不存在")
        date = (summary_date or "").strip()
        if not date:
            raise ValueError("总结日期不能为空")
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO section_daily_summaries
                    (section_id, summary_date, progress, risks, challenges, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(section_id, summary_date) DO UPDATE SET
                    progress = excluded.progress,
                    risks = excluded.risks,
                    challenges = excluded.challenges,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (section_id, date, progress, risks, challenges, notes, now, now),
            )
            row = conn.execute(
                """
                SELECT * FROM section_daily_summaries
                WHERE section_id = ? AND summary_date = ?
                """,
                (section_id, date),
            ).fetchone()
        assert row is not None
        return self._summary_from_db(row)

    def get_daily_summary(self, section_id: int, summary_date: str) -> SectionDailySummaryRow | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM section_daily_summaries
                WHERE section_id = ? AND summary_date = ?
                """,
                (section_id, summary_date),
            ).fetchone()
        return self._summary_from_db(row) if row else None

    def list_daily_summaries(self, section_id: int) -> list[SectionDailySummaryRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM section_daily_summaries
                WHERE section_id = ?
                ORDER BY summary_date
                """,
                (section_id,),
            ).fetchall()
        return [self._summary_from_db(r) for r in rows]

    def add_doc(
        self,
        project_id: int,
        title: str,
        file_path: str = "",
        note: str = "",
    ) -> dict[str, Any] | None:
        if not self.get_project(project_id):
            return None
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO project_docs (project_id, title, file_path, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, title, file_path, note, now),
            )
            return {
                "id": int(cur.lastrowid),
                "project_id": project_id,
                "title": title,
                "file_path": file_path,
                "note": note,
            }

    def list_docs(self, project_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM project_docs WHERE project_id = ? ORDER BY id DESC",
                (project_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "project_id": row["project_id"],
                "title": row["title"],
                "file_path": row["file_path"],
                "note": row["note"],
            }
            for row in rows
        ]

    def delete_section(self, section_id: int) -> bool:
        if not self.get_section(section_id):
            return False
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM section_daily_summaries WHERE section_id = ?",
                (section_id,),
            )
            conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
        return True

    def delete_project(self, project_id: int) -> bool:
        row = self.get_project(project_id)
        if not row or row.is_inbox:
            return False
        with self._connect() as conn:
            section_ids = [
                int(r[0])
                for r in conn.execute(
                    "SELECT id FROM sections WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            ]
            for sid in section_ids:
                conn.execute(
                    "DELETE FROM section_daily_summaries WHERE section_id = ?",
                    (sid,),
                )
            conn.execute("DELETE FROM sections WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM project_docs WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return True


def project_to_dict(row: ProjectRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "status": row.status,
        "start_at": row.start_at or "",
        "end_at": row.end_at or "",
        "due_date": row.end_at or "",
        "owner": row.owner or "",
        "remind_at": row.remind_at or "",
        "is_inbox": row.is_inbox,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def section_to_dict(row: SectionRow, *, stats: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "project_id": row.project_id,
        "name": row.name,
        "start_at": row.start_at or "",
        "end_at": row.end_at or "",
        "owner": row.owner or "",
        "goals": row.goals,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if stats is not None:
        data["stats"] = stats
    return data


def summary_to_dict(row: SectionDailySummaryRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "section_id": row.section_id,
        "summary_date": row.summary_date,
        "progress": row.progress,
        "risks": row.risks,
        "challenges": row.challenges,
        "notes": row.notes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
