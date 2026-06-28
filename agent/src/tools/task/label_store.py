"""任务标签（Label）元数据存储：名称与颜色。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from infra.config import get_data_dir
from infra.sqlite_store import ReusableSqliteStore

DEFAULT_LABEL_COLOR = "#93c5fd"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_labels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color       TEXT NOT NULL DEFAULT '#93c5fd',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_labels_name ON task_labels(name);
"""


@dataclass
class LabelRow:
    id: int
    name: str
    color: str
    created_at: str
    updated_at: str


class LabelStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or get_data_dir() / "task.db")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_from_db(row) -> LabelRow:
        return LabelRow(
            id=int(row["id"]),
            name=row["name"],
            color=row["color"] or DEFAULT_LABEL_COLOR,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_all(self) -> list[LabelRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_labels ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def get_by_name(self, name: str) -> LabelRow | None:
        name = (name or "").strip()
        if not name:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_labels WHERE name = ? COLLATE NOCASE",
                (name,),
            ).fetchone()
        return self._row_from_db(row) if row else None

    def get_by_id(self, label_id: int) -> LabelRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_labels WHERE id = ?",
                (label_id,),
            ).fetchone()
        return self._row_from_db(row) if row else None

    def create(self, name: str, color: str = DEFAULT_LABEL_COLOR) -> LabelRow:
        name = (name or "").strip()
        if not name:
            raise ValueError("标签名称不能为空")
        if self.get_by_name(name):
            raise ValueError(f"标签「{name}」已存在")
        color = (color or DEFAULT_LABEL_COLOR).strip() or DEFAULT_LABEL_COLOR
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO task_labels (name, color, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, color, now, now),
            )
            label_id = int(cur.lastrowid)
        row = self.get_by_id(label_id)
        assert row is not None
        return row

    def update(
        self,
        label_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
    ) -> LabelRow | None:
        row = self.get_by_id(label_id)
        if not row:
            return None
        new_name = (name or row.name).strip()
        if not new_name:
            raise ValueError("标签名称不能为空")
        new_color = (color or row.color).strip() or DEFAULT_LABEL_COLOR
        if new_name.lower() != row.name.lower():
            existing = self.get_by_name(new_name)
            if existing and existing.id != label_id:
                raise ValueError(f"标签「{new_name}」已存在")
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE task_labels SET name = ?, color = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_name, new_color, now, label_id),
            )
        return self.get_by_id(label_id)

    def delete(self, label_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM task_labels WHERE id = ?", (label_id,))
            return cur.rowcount > 0


def _replace_tag_on_all_tasks(old_name: str, new_name: str) -> int:
    from tools.task.store import TaskStore

    store = TaskStore()
    updated = 0
    for row in store.list_all(include_done=True):
        if old_name not in row.tags:
            continue
        new_tags = [new_name if t == old_name else t for t in row.tags]
        store.update(row.id, tags=new_tags)
        updated += 1
    return updated


def _remove_tag_from_all_tasks(name: str) -> int:
    from tools.task.store import TaskStore

    store = TaskStore()
    updated = 0
    for row in store.list_all(include_done=True):
        if name not in row.tags:
            continue
        new_tags = [t for t in row.tags if t != name]
        store.update(row.id, tags=new_tags)
        updated += 1
    return updated


def label_to_dict(row: LabelRow) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "color": row.color,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_label_records() -> list[dict]:
    return [label_to_dict(r) for r in LabelStore().list_all()]


def create_label_record(name: str, color: str = DEFAULT_LABEL_COLOR) -> dict:
    row = LabelStore().create(name, color)
    return label_to_dict(row)


def update_label_record(
    label_id: int,
    *,
    name: str | None = None,
    color: str | None = None,
) -> dict | None:
    store = LabelStore()
    old = store.get_by_id(label_id)
    if not old:
        return None
    if name is not None and name.strip() and name.strip() != old.name:
        _replace_tag_on_all_tasks(old.name, name.strip())
    updated = store.update(label_id, name=name, color=color)
    return label_to_dict(updated) if updated else None


def delete_label_record(label_id: int) -> bool:
    store = LabelStore()
    row = store.get_by_id(label_id)
    if not row:
        return False
    _remove_tag_from_all_tasks(row.name)
    return store.delete(label_id)
