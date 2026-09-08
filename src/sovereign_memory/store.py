from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from .models import ParsedSession


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sessions (
    vendor TEXT NOT NULL,
    source_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    message_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    PRIMARY KEY (vendor, source_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    vendor TEXT NOT NULL,
    source_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    timestamp TEXT,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (vendor, source_id)
        REFERENCES sessions(vendor, source_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS messages_session_idx
    ON messages(vendor, session_id);
CREATE INDEX IF NOT EXISTS messages_source_idx
    ON messages(vendor, source_id);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text,
    content='messages',
    content_rowid='rowid',
    tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text)
        VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text)
        VALUES ('delete', old.rowid, old.text);
    INSERT INTO messages_fts(rowid, text) VALUES (new.rowid, new.text);
END;
"""


class MemoryStore:
    def __init__(self, private_root: Path):
        self.private_root = private_root
        self.db_path = private_root / "index.sqlite3"
        self.normalized_root = private_root / "normalized"

    def initialize(self) -> None:
        self.private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.private_root, 0o700)
        with closing(self.connect()) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(sessions)")
            }
            if columns and "source_id" not in columns:
                raise ValueError("Unsupported legacy index schema; choose a new SAM_PRIVATE_DIR. Existing data was preserved.")
            connection.executescript(SCHEMA)
            connection.commit()
        os.chmod(self.db_path, 0o600)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def ingest(self, session: ParsedSession) -> None:
        self.initialize()
        imported_at = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    "DELETE FROM sessions WHERE vendor = ? AND source_id = ?",
                    (session.vendor, session.source_id),
                )
                connection.execute(
                    """
                    INSERT INTO sessions(
                        vendor, source_id, session_id, source_ref, source_sha256,
                        metadata_json, message_count, warning_count, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.vendor,
                        session.source_id,
                        session.session_id,
                        session.source_ref,
                        session.source_sha256,
                        json.dumps(session.metadata, ensure_ascii=False, sort_keys=True),
                        len(session.messages),
                        len(session.warnings),
                        imported_at,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO messages(
                        id, vendor, source_id, session_id, timestamp, role, text,
                        source_ref, source_sha256, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            message.id,
                            message.vendor,
                            message.source_id,
                            message.session_id,
                            message.timestamp,
                            message.role,
                            message.text,
                            message.source_ref,
                            message.source_sha256,
                            json.dumps(
                                message.metadata, ensure_ascii=False, sort_keys=True
                            ),
                        )
                        for message in session.messages
                    ],
                )
        self.write_normalized(session)

    def write_normalized(self, session: ParsedSession) -> Path:
        destination_dir = self.normalized_root / session.vendor
        destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = destination_dir / f"{session.source_id}.jsonl"
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=destination_dir,
            prefix=f".{session.source_id}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            for message in session.messages:
                handle.write(
                    json.dumps(message.to_dict(), ensure_ascii=False, sort_keys=True)
                )
                handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        return destination

    def prune_normalized(self, vendor: str, valid_source_ids: set[str]) -> int:
        vendor_dir = self.normalized_root / vendor
        if not vendor_dir.exists():
            return 0
        removed = 0
        for path in vendor_dir.glob("*.jsonl"):
            if path.stem not in valid_source_ids:
                path.unlink()
                removed += 1
        return removed

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        terms = [part for part in query.strip().split() if part]
        fts_query = " OR ".join(f'"{part.replace(chr(34), chr(34) * 2)}"' for part in terms)
        rows: list[sqlite3.Row] = []
        fetch_limit = max(limit * 20, limit)
        if fts_query:
            try:
                with closing(self.connect()) as connection:
                    rows = connection.execute(
                        """
                        SELECT m.*, bm25(messages_fts) AS rank
                        FROM messages_fts
                        JOIN messages AS m ON m.rowid = messages_fts.rowid
                        WHERE messages_fts MATCH ?
                        ORDER BY rank, COALESCE(m.timestamp, '') DESC
                        LIMIT ?
                        """,
                        (fts_query, fetch_limit),
                    ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        if not rows:
            with closing(self.connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT m.*, 0.0 AS rank
                    FROM messages AS m
                    WHERE instr(lower(m.text), lower(?)) > 0
                    ORDER BY COALESCE(m.timestamp, '') DESC
                    LIMIT ?
                    """,
                    (query.strip(), fetch_limit),
                ).fetchall()
        results: list[dict[str, Any]] = []
        seen_text: set[str] = set()
        for row in rows:
            result = dict(row)
            dedupe_key = " ".join(result["text"].split())
            if dedupe_key in seen_text:
                continue
            seen_text.add(dedupe_key)
            results.append(result)
            if len(results) >= limit:
                break
        return results

    def counts(self) -> dict[str, int]:
        if not self.db_path.exists():
            return {"sessions": 0, "messages": 0}
        with closing(self.connect()) as connection:
            sessions = connection.execute("SELECT count(*) FROM sessions").fetchone()[0]
            messages = connection.execute("SELECT count(*) FROM messages").fetchone()[0]
        return {"sessions": sessions, "messages": messages}
