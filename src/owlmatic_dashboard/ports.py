from typing import Protocol

from .domain import Receipt, SourcePage
from .wire import StatisticsSnapshot


class SnapshotRepository(Protocol):
    def accept(self, snapshot: StatisticsSnapshot) -> Receipt: ...
    def page(self, cursor: str | None, limit: int) -> SourcePage: ...
