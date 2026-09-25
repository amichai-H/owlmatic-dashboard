"""Receiver contracts independent of HTTP and SQLite."""

from typing import Literal

from .wire import Contract, Snapshot, StatisticsSnapshot


class Receipt(Contract):
    status: Literal["accepted", "duplicate", "stale"]
    snapshot_id: str


class SourceReceipt(Contract):
    source_id: str
    received_at: str | None = None


class SourcePage(Contract):
    sources: tuple[Snapshot, ...]
    receipts: tuple[SourceReceipt, ...] = ()
    next_cursor: str | None = None


class LegacySourcePage(Contract):
    sources: tuple[StatisticsSnapshot, ...]
    next_cursor: str | None = None


class ReceiverError(Exception):
    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
