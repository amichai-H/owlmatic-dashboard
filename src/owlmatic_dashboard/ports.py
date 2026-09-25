from typing import Protocol

from .domain import Receipt, SourcePage
from .wire import Snapshot


class SnapshotRepository(Protocol):
    def accept(self, snapshot: Snapshot) -> Receipt: ...
    def page(self, cursor: str | None, limit: int) -> SourcePage: ...
