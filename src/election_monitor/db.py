from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import ElectionSnapshot


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS municipalities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipality_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    processed_districts INTEGER NOT NULL,
    total_districts INTEGER NOT NULL,
    turnout_percent REAL,
    FOREIGN KEY (municipality_id) REFERENCES municipalities(id)
);

CREATE TABLE IF NOT EXISTS party_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    list_id TEXT NOT NULL,
    name TEXT NOT NULL,
    votes INTEGER NOT NULL,
    percent REAL,
    mandates_virtual INTEGER,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);
"""


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def save_snapshot(self, snapshot: ElectionSnapshot) -> int:
        with self._connect() as conn:
            municipality_id = self._upsert_municipality(conn, snapshot.municipality.code, snapshot.municipality.name)
            cur = conn.execute(
                """
                INSERT INTO snapshots (
                    municipality_id, fetched_at, source_url, source_hash,
                    processed_districts, total_districts, turnout_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    municipality_id,
                    snapshot.fetched_at.isoformat(),
                    snapshot.source_url,
                    snapshot.source_hash,
                    snapshot.progress.processed_districts,
                    snapshot.progress.total_districts,
                    snapshot.progress.turnout_percent,
                ),
            )
            snapshot_id = int(cur.lastrowid)
            for result in snapshot.party_results:
                conn.execute(
                    """
                    INSERT INTO party_results (
                        snapshot_id, list_id, name, votes, percent, mandates_virtual
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        result.list_id,
                        result.name,
                        result.votes,
                        result.percent,
                        result.mandates_virtual,
                    ),
                )
            return snapshot_id

    def _upsert_municipality(self, conn: sqlite3.Connection, code: str, name: str) -> int:
        cur = conn.execute("SELECT id FROM municipalities WHERE code = ?", (code,))
        row = cur.fetchone()
        if row is not None:
            conn.execute("UPDATE municipalities SET name = ? WHERE code = ?", (name, code))
            return int(row["id"])
        cur = conn.execute("INSERT INTO municipalities (code, name) VALUES (?, ?)", (code, name))
        return int(cur.lastrowid)
