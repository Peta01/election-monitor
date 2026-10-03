from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import ElectionSnapshot, MunicipalityRef, PartyResult, PollingProgress
from .municipalities import MunicipalityOption

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
    seats_to_elect INTEGER,
    threshold_percent INTEGER,
    lottery_required INTEGER NOT NULL DEFAULT 0,
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
    candidate_count INTEGER NOT NULL DEFAULT 0,
    constituency_id TEXT NOT NULL DEFAULT '0',
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS tracked_municipalities (
    code TEXT PRIMARY KEY,
    council_name TEXT NOT NULL,
    municipality_name TEXT NOT NULL,
    region_code TEXT NOT NULL,
    region_name TEXT NOT NULL,
    district_code TEXT NOT NULL,
    district_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_attempt_at TEXT,
    last_success_at TEXT,
    last_error TEXT
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
            self._ensure_column(conn, "snapshots", "seats_to_elect", "INTEGER")
            self._ensure_column(conn, "snapshots", "threshold_percent", "INTEGER")
            self._ensure_column(
                conn, "snapshots", "lottery_required", "INTEGER NOT NULL DEFAULT 0"
            )
            self._ensure_column(conn, "snapshots", "allocation_error", "TEXT")
            self._ensure_column(
                conn, "party_results", "candidate_count", "INTEGER NOT NULL DEFAULT 0"
            )
            self._ensure_column(
                conn, "party_results", "constituency_id", "TEXT NOT NULL DEFAULT '0'"
            )

    def save_snapshot(self, snapshot: ElectionSnapshot) -> int:
        with self._connect() as conn:
            municipality_id = self._upsert_municipality(
                conn, snapshot.municipality.code, snapshot.municipality.name
            )
            latest = conn.execute(
                """
                SELECT id, fetched_at, processed_districts, total_districts,
                       turnout_percent, seats_to_elect, threshold_percent,
                       lottery_required, allocation_error
                FROM snapshots
                WHERE municipality_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (municipality_id,),
            ).fetchone()
            # Ukládá se jen při změně počtu zpracovaných okrsků (nebo identifikace listin).
            if latest is not None and (
                int(latest["processed_districts"]),
                int(latest["total_districts"]),
                self._list_keys(conn, int(latest["id"])),
            ) == (
                snapshot.progress.processed_districts,
                snapshot.progress.total_districts,
                sorted((r.constituency_id, r.list_id) for r in snapshot.party_results),
            ):
                return int(latest["id"])

            cur = conn.execute(
                """
                INSERT INTO snapshots (
                    municipality_id, fetched_at, source_url, source_hash,
                    processed_districts, total_districts, turnout_percent, seats_to_elect,
                    threshold_percent, lottery_required, allocation_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    municipality_id,
                    snapshot.fetched_at.isoformat(),
                    snapshot.source_url,
                    snapshot.source_hash,
                    snapshot.progress.processed_districts,
                    snapshot.progress.total_districts,
                    snapshot.progress.turnout_percent,
                    snapshot.seats_to_elect,
                    snapshot.threshold_percent,
                    int(snapshot.lottery_required),
                    snapshot.allocation_error,
                ),
            )
            snapshot_id = int(cur.lastrowid)
            for result in snapshot.party_results:
                conn.execute(
                    """
                    INSERT INTO party_results (
                        snapshot_id, list_id, name, votes, percent, mandates_virtual,
                        candidate_count, constituency_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        result.list_id,
                        result.name,
                        result.votes,
                        result.percent,
                        result.mandates_virtual,
                        result.candidate_count,
                        result.constituency_id,
                    ),
                )
            return snapshot_id

    @staticmethod
    def _list_keys(conn: sqlite3.Connection, snapshot_id: int) -> list[tuple[str, str]]:
        rows = conn.execute(
            "SELECT constituency_id, list_id FROM party_results WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchall()
        return sorted((row["constituency_id"], row["list_id"]) for row in rows)

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def add_tracked_municipality(self, option: MunicipalityOption) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tracked_municipalities (
                    code, council_name, municipality_name, region_code, region_name,
                    district_code, district_name, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(code) DO UPDATE SET
                    council_name = excluded.council_name,
                    municipality_name = excluded.municipality_name,
                    region_code = excluded.region_code,
                    region_name = excluded.region_name,
                    district_code = excluded.district_code,
                    district_name = excluded.district_name,
                    enabled = 1
                """,
                (
                    option.code,
                    option.council_name,
                    option.municipality_name,
                    option.region_code,
                    option.region_name,
                    option.district_code,
                    option.district_name,
                ),
            )

    def remove_tracked_municipality(self, code: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tracked_municipalities SET enabled = 0 WHERE code = ?",
                (code,),
            )

    def list_tracked_municipalities(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT code, council_name, municipality_name, region_code, region_name,
                       district_code, district_name, enabled, last_attempt_at,
                       last_success_at, last_error
                FROM tracked_municipalities
                WHERE enabled = 1
                ORDER BY region_name, district_name, municipality_name, council_name
                """
            ).fetchall()

    def update_poll_attempt(self, code: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tracked_municipalities
                SET last_attempt_at = ?, last_error = NULL
                WHERE code = ? AND enabled = 1
                """,
                (datetime.now(UTC).isoformat(), code),
            )

    def update_poll_success(self, code: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tracked_municipalities
                SET last_attempt_at = ?, last_success_at = ?, last_error = NULL
                WHERE code = ? AND enabled = 1
                """,
                (now, now, code),
            )

    def update_poll_failure(self, code: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tracked_municipalities
                SET last_attempt_at = ?, last_error = ?
                WHERE code = ? AND enabled = 1
                """,
                (datetime.now(UTC).isoformat(), error, code),
            )

    def get_latest_snapshot(self, code: str) -> ElectionSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.*, m.code, m.name
                FROM snapshots s
                JOIN municipalities m ON m.id = s.municipality_id
                WHERE m.code = ?
                ORDER BY s.id DESC LIMIT 1
                """,
                (code,),
            ).fetchone()
            if row is None:
                return None
            return self._load_snapshot(conn, row)

    def list_snapshots(self, code: str) -> list[ElectionSnapshot]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*, m.code, m.name
                FROM snapshots s
                JOIN municipalities m ON m.id = s.municipality_id
                WHERE m.code = ?
                ORDER BY s.processed_districts, s.id
                """,
                (code,),
            ).fetchall()
            return [self._load_snapshot(conn, row) for row in rows]

    @staticmethod
    def _load_snapshot(conn: sqlite3.Connection, row: sqlite3.Row) -> ElectionSnapshot:
        results = conn.execute(
            """
            SELECT list_id, name, votes, percent, mandates_virtual,
                   candidate_count, constituency_id
            FROM party_results
            WHERE snapshot_id = ?
            ORDER BY constituency_id, CAST(list_id AS INTEGER), list_id
            """,
            (row["id"],),
        ).fetchall()
        return ElectionSnapshot(
            municipality=MunicipalityRef(row["code"], row["name"]),
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            source_url=row["source_url"],
            source_hash=row["source_hash"],
            progress=PollingProgress(
                processed_districts=row["processed_districts"],
                total_districts=row["total_districts"],
                turnout_percent=row["turnout_percent"],
            ),
            party_results=[
                PartyResult(
                    list_id=result["list_id"],
                    name=result["name"],
                    votes=result["votes"],
                    percent=result["percent"],
                    mandates_virtual=result["mandates_virtual"],
                    candidate_count=result["candidate_count"],
                    constituency_id=result["constituency_id"],
                )
                for result in results
            ],
            seats_to_elect=row["seats_to_elect"],
            threshold_percent=row["threshold_percent"],
            lottery_required=bool(row["lottery_required"]),
            allocation_error=row["allocation_error"],
        )

    def get_tracking_status(self, code: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT code, council_name, municipality_name, last_attempt_at,
                       last_success_at, last_error
                FROM tracked_municipalities
                WHERE code = ? AND enabled = 1
                """,
                (code,),
            ).fetchone()

    def _upsert_municipality(
        self, conn: sqlite3.Connection, code: str, name: str
    ) -> int:
        cur = conn.execute("SELECT id FROM municipalities WHERE code = ?", (code,))
        row = cur.fetchone()
        if row is not None:
            conn.execute(
                "UPDATE municipalities SET name = ? WHERE code = ?", (name, code)
            )
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO municipalities (code, name) VALUES (?, ?)", (code, name)
        )
        return int(cur.lastrowid)
