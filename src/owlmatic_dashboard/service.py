"""Application services; the repository commits before acknowledgement."""

from dataclasses import dataclass

from .domain import LegacySourcePage, Receipt, SourcePage
from .ports import SnapshotRepository
from .wire import Snapshot, StatisticsSnapshot


@dataclass(frozen=True)
class ReceiverService:
    repository: SnapshotRepository

    def ingest(self, snapshot: Snapshot) -> Receipt:
        return self.repository.accept(snapshot)

    def sources(self, cursor: str | None = None, limit: int = 100) -> SourcePage:
        return self.repository.page(cursor, limit)

    def legacy_sources(self, cursor: str | None = None, limit: int = 100) -> LegacySourcePage:
        page = self.sources(cursor, limit)
        return LegacySourcePage(
            sources=tuple(
                StatisticsSnapshot(
                    snapshot_id=s.snapshot_id,
                    source_id=s.source_id,
                    sequence=s.sequence,
                    generated_at=s.generated_at,
                    since=s.since,
                    days=s.days,
                    shared=s.shared,
                    usage=s.usage,
                    savings=s.savings,
                    daily=s.daily,
                    workflows=s.workflows,
                )
                for s in page.sources
            ),
            next_cursor=page.next_cursor,
        )
