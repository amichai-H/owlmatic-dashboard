"""Transactional latest-snapshot storage and durable idempotency receipts."""

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import TypeAdapter

from .domain import Receipt, ReceiverError, SourcePage, SourceReceipt
from .wire import Snapshot


class SqliteSnapshots:
    def __init__(self, root: Path) -> None:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        self.path = root / "dashboard.sqlite"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1, 2}:
                raise ReceiverError("DATABASE_VERSION", 503)
            db.execute(
                "CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,sequence INTEGER NOT NULL,body TEXT NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,digest TEXT NOT NULL)")
            if version < 2:
                db.execute("ALTER TABLE sources ADD COLUMN received_at TEXT")
            db.execute("PRAGMA user_version=2")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            self.path.chmod(0o600)
            yield db
            db.commit()
        except sqlite3.Error as error:
            db.rollback()
            raise ReceiverError("STORAGE_UNAVAILABLE", 503) from error
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def accept(self, snapshot: Snapshot) -> Receipt:
        body = snapshot.model_dump_json(exclude_none=True)
        digest = hashlib.sha256(body.encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT digest FROM receipts WHERE id=?", (snapshot.snapshot_id,)
            ).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ReceiverError("IDEMPOTENCY_CONFLICT", 409)
                return Receipt(status="duplicate", snapshot_id=snapshot.snapshot_id)
            current = db.execute("SELECT sequence FROM sources WHERE id=?", (snapshot.source_id,)).fetchone()
            if current and current[0] == snapshot.sequence:
                raise ReceiverError("SEQUENCE_CONFLICT", 409)
            db.execute("INSERT INTO receipts(id,digest) VALUES(?,?)", (snapshot.snapshot_id, digest))
            if current and current[0] > snapshot.sequence:
                return Receipt(status="stale", snapshot_id=snapshot.snapshot_id)
            db.execute(
                "INSERT INTO sources(id,sequence,body,received_at) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET sequence=excluded.sequence,body=excluded.body,received_at=excluded.received_at",
                (snapshot.source_id, snapshot.sequence, body, datetime.now(UTC).isoformat()),
            )
        return Receipt(status="accepted", snapshot_id=snapshot.snapshot_id)

    def page(self, cursor: str | None, limit: int) -> SourcePage:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,body,received_at FROM sources WHERE id>? ORDER BY id LIMIT ?",
                (cursor or "", limit + 1),
            ).fetchall()
        return SourcePage(
            sources=tuple(TypeAdapter(Snapshot).validate_json(cast(str, row[1])) for row in rows[:limit]),
            receipts=tuple(SourceReceipt(source_id=row[0], received_at=row[2]) for row in rows[:limit]),
            next_cursor=cast(str, rows[limit - 1][0]) if len(rows) > limit else None,
        )
