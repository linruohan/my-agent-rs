from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from infra.config import get_data_dir
from infra.user_settings import get_memory_settings

_RECALL_SKIP_PATTERNS = (
    r"重新",
    r"再查",
    r"再搜",
    r"刷新",
    r"最新",
    r"不要缓存",
    r"别用历史",
    r"ignore cache",
    r"refresh",
)


def normalize_question(text: str) -> str:
    raw = (text or "").strip()
    raw = re.sub(r"\n\n\[当前时间[^\]]*\]", "", raw)
    raw = re.sub(r"\s+", " ", raw.lower())
    raw = re.sub(r"[^\w\s\u4e00-\u9fff]", "", raw)
    return raw.strip()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", text.lower()) if len(t) > 1}


def question_similarity(a: str, b: str) -> float:
    na = normalize_question(a)
    nb = normalize_question(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = _tokenize(na), _tokenize(nb)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def should_skip_history_recall(text: str, *, has_attachments: bool = False) -> bool:
    """Only skip recall when user explicitly wants a fresh run or input is invalid.

    Do NOT skip for 'fresh info' heuristics (e.g. 新特性 / python 3.14) — if the user
    already got an answer, repeating the same question should reuse history.
    """
    if has_attachments:
        return True
    stripped = (text or "").strip()
    if len(stripped) < 4:
        return True
    if stripped.startswith("/"):
        return True
    lower = stripped.lower()
    return any(re.search(p, lower, re.I) for p in _RECALL_SKIP_PATTERNS)


class ChatHistoryStore:
    """Cross-session Q&A index for similar-question recall."""

    def __init__(self, db_path=None):
        self.db_path = db_path or (get_data_dir() / "chat_history.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    question_norm TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_norm ON chat_history(question_norm)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(created_at DESC)"
            )
            conn.commit()

    def record(
        self,
        thread_id: str,
        question: str,
        answer: str,
        *,
        skip_if_duplicate: bool = True,
    ) -> int | None:
        q = (question or "").strip()
        a = (answer or "").strip()
        if len(q) < 4 or len(a) < 8:
            return None
        norm = normalize_question(q)
        if not norm:
            return None

        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            if skip_if_duplicate:
                row = conn.execute(
                    """
                    SELECT id FROM chat_history
                    WHERE question_norm = ? AND answer = ?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (norm, a),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE chat_history SET created_at = ?, thread_id = ? WHERE id = ?",
                        (now, thread_id, row[0]),
                    )
                    conn.commit()
                    return int(row[0])

            cur = conn.execute(
                """
                INSERT INTO chat_history (thread_id, question, question_norm, answer, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (thread_id, q, norm, a, now),
            )
            conn.commit()
            return int(cur.lastrowid)

    def find_similar(
        self,
        question: str,
        *,
        limit: int = 200,
    ) -> dict[str, Any] | None:
        cfg = get_memory_settings()
        if not cfg.get("history_recall", True):
            return None

        min_score = float(cfg.get("history_similarity_min", 0.72))
        max_age_days = int(cfg.get("history_max_age_days", 90))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()

        q = (question or "").strip()
        norm = normalize_question(q)
        if not norm:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            exact = conn.execute(
                """
                SELECT id, thread_id, question, answer, created_at, hit_count
                FROM chat_history
                WHERE question_norm = ? AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (norm, cutoff),
            ).fetchone()
            if exact:
                return {
                    "id": exact["id"],
                    "thread_id": exact["thread_id"],
                    "question": exact["question"],
                    "answer": exact["answer"],
                    "created_at": exact["created_at"],
                    "hit_count": exact["hit_count"],
                    "similarity": 1.0,
                }

            rows = conn.execute(
                """
                SELECT id, thread_id, question, answer, created_at, hit_count
                FROM chat_history
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()

        best: dict[str, Any] | None = None
        best_score = 0.0
        for row in rows:
            score = question_similarity(q, row["question"])
            if score >= min_score and score > best_score:
                best_score = score
                best = {
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "created_at": row["created_at"],
                    "hit_count": row["hit_count"],
                    "similarity": round(score, 3),
                }

        if best and best_score >= min_score:
            return best
        return None

    def bump_hit(self, entry_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE chat_history SET hit_count = hit_count + 1 WHERE id = ?",
                (entry_id,),
            )
            conn.commit()

    def stats(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
            hits = conn.execute(
                "SELECT COALESCE(SUM(hit_count), 0) FROM chat_history"
            ).fetchone()[0]
        return {"total_entries": total, "total_hits": hits}


_store: ChatHistoryStore | None = None


def get_chat_history_store() -> ChatHistoryStore:
    global _store
    if _store is None:
        _store = ChatHistoryStore()
    return _store


def find_cached_answer(
    question: str,
    thread_id: str | None = None,
    *,
    has_attachments: bool = False,
) -> dict[str, Any] | None:
    del thread_id
    if should_skip_history_recall(question, has_attachments=has_attachments):
        return None
    return get_chat_history_store().find_similar(question)


def record_turn(thread_id: str, question: str, answer: str) -> int | None:
    cfg = get_memory_settings()
    if not cfg.get("history_recall", True):
        return None
    return get_chat_history_store().record(thread_id, question, answer)
