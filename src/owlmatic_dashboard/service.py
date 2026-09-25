"""Application services; the repository commits before acknowledgement."""

from dataclasses import dataclass

from .domain import Receipt, SourcePage
from .ports import SnapshotRepository
from .wire import StatisticsSnapshot


@dataclass(frozen=True)
class ReceiverService:
    repository: SnapshotRepository

    def ingest(self, snapshot: StatisticsSnapshot) -> Receipt:
        return self.repository.accept(snapshot)

    def sources(self, cursor: str | None = None, limit: int = 100) -> SourcePage:
        return self.repository.page(cursor, limit)
