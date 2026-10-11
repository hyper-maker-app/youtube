"""Small, parameterised persistence layer shared by the pipeline and local MCP."""
from __future__ import annotations
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def topic_key(topic: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", topic.lower()))

def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, topic_key TEXT NOT NULL, content_type TEXT NOT NULL, timestamp TEXT NOT NULL, cost_usd REAL NOT NULL DEFAULT 0, duration_sec REAL NOT NULL DEFAULT 0, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '')""")
    # Existing repositories used a smaller `runs` table.  Additive migration keeps their
    # history intact and lets the new MCP read it without destructive schema changes.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    for name, decl in {
        "topic_key": "TEXT NOT NULL DEFAULT ''",
        "content_type": "TEXT NOT NULL DEFAULT 'factual'",
        "cost_usd": "REAL NOT NULL DEFAULT 0",
        "duration_sec": "REAL NOT NULL DEFAULT 0",
        "status": "TEXT NOT NULL DEFAULT 'completed'",
        "notes": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {decl}")
    # Version 0 used shorter `cost`/`duration` names. Preserve that history when the
    # normalized columns are introduced instead of treating legacy runs as zero-cost.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    if "cost" in columns:
        conn.execute("UPDATE runs SET cost_usd = COALESCE(cost, 0) WHERE cost_usd = 0")
    if "duration" in columns:
        conn.execute("UPDATE runs SET duration_sec = COALESCE(duration, 0) WHERE duration_sec = 0")
    for row_id, topic in conn.execute("SELECT id, topic FROM runs WHERE topic_key = '' OR topic_key IS NULL").fetchall():
        conn.execute("UPDATE runs SET topic_key = ? WHERE id = ?", (topic_key(topic), row_id))
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_topic_key ON runs(topic_key)")
    return conn

def record(path: Path, topic: str, content_type: str, status: str, duration_sec: float = 0, cost_usd: float = 0, notes: str = "") -> None:
    conn = connect(path)
    try:
        conn.execute("INSERT INTO runs(topic, topic_key, content_type, timestamp, cost_usd, duration_sec, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (topic, topic_key(topic), content_type, datetime.now(timezone.utc).isoformat(), cost_usd, duration_sec, status, notes[:500]))
        conn.commit()
    finally:
        conn.close()
