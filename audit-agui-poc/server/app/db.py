import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "poc.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT,
              type TEXT,
              payload TEXT,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sources (
              id TEXT PRIMARY KEY,
              tenant_id TEXT,
              kind TEXT, -- enterprise|customer
              title TEXT,
              meta TEXT
            );
            CREATE TABLE IF NOT EXISTS chunks (
              id TEXT PRIMARY KEY,
              source_id TEXT,
              order_no INTEGER,
              text TEXT,
              meta TEXT
            );
            CREATE TABLE IF NOT EXISTS context_packs (
              id TEXT PRIMARY KEY,
              tenant_id TEXT,
              task TEXT,
              filters TEXT,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS context_pack_items (
              pack_id TEXT,
              chunk_id TEXT,
              score REAL,
              PRIMARY KEY (pack_id, chunk_id)
            );
            CREATE TABLE IF NOT EXISTS questions (
              id TEXT PRIMARY KEY,
              session_id TEXT,
              text TEXT,
              citations TEXT,
              required INTEGER,
              category TEXT
            );
            CREATE TABLE IF NOT EXISTS answers (
              question_id TEXT PRIMARY KEY,
              session_id TEXT,
              answer TEXT,
              meta TEXT
            );
            CREATE TABLE IF NOT EXISTS workflows (
              id TEXT PRIMARY KEY,
              session_id TEXT,
              workflow_json TEXT,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()


def persist_event(session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (session_id, type, payload) VALUES (?, ?, ?)",
            (session_id, event_type, json.dumps(payload)),
        )
        conn.commit()


def upsert_source(source_id: str, tenant_id: str, kind: str, title: str, meta: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sources (id, tenant_id, kind, title, meta) VALUES (?, ?, ?, ?, ?)",
            (source_id, tenant_id, kind, title, json.dumps(meta)),
        )
        conn.commit()


def insert_chunks(source_id: str, chunks: List[Tuple[str, int, str, Dict[str, Any]]]) -> None:
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO chunks (id, source_id, order_no, text, meta) VALUES (?, ?, ?, ?, ?)",
            [(cid, source_id, order_no, text, json.dumps(meta)) for cid, order_no, text, meta in chunks],
        )
        conn.commit()


def simple_retrieve(tenant_id: str, query: str, kinds: List[str], top_k: int = 10) -> List[sqlite3.Row]:
    like = f"%{query.lower()}%"
    kinds_tuple = tuple(kinds)
    sql = (
        "SELECT c.*, s.kind FROM chunks c JOIN sources s ON s.id = c.source_id "
        "WHERE lower(c.text) LIKE ? AND s.tenant_id = ? AND s.kind IN (%s) "
        "ORDER BY c.order_no ASC LIMIT ?" % (",".join(["?"] * len(kinds_tuple)))
    )
    params = [like, tenant_id, *kinds_tuple, top_k]
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def create_context_pack(pack_id: str, tenant_id: str, task: str, filters: Dict[str, Any], items: List[Tuple[str, float]]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO context_packs (id, tenant_id, task, filters) VALUES (?, ?, ?, ?)",
            (pack_id, tenant_id, task, json.dumps(filters)),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO context_pack_items (pack_id, chunk_id, score) VALUES (?, ?, ?)",
            [(pack_id, chunk_id, score) for chunk_id, score in items],
        )
        conn.commit()


def save_questions(session_id: str, questions: List[Dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO questions (id, session_id, text, citations, required, category) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    q["id"],
                    session_id,
                    q.get("text"),
                    json.dumps(q.get("citations", [])),
                    1 if q.get("required") else 0,
                    q.get("category"),
                )
                for q in questions
            ],
        )
        conn.commit()


def save_answer(session_id: str, question_id: str, answer: str, meta: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO answers (question_id, session_id, answer, meta) VALUES (?, ?, ?, ?)",
            (question_id, session_id, answer, json.dumps(meta)),
        )
        conn.commit()


def save_workflow(session_id: str, workflow_id: str, workflow: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO workflows (id, session_id, workflow_json) VALUES (?, ?, ?)",
            (workflow_id, session_id, json.dumps(workflow)),
        )
        conn.commit()

