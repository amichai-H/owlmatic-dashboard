"""Separate capabilities for ingestion and reading. No credentials in public config."""

import hmac
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Credentials:
    ingest: str = field(repr=False)
    read: str = field(repr=False)

    def __post_init__(self) -> None:
        for value in (self.ingest, self.read):
            if len(value) < 24 or not value.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
                raise ValueError(
                    "Dashboard tokens must be distinct printable values of at least 24 characters"
                )
        if self.ingest == self.read:
            raise ValueError("Ingest and read credentials must differ")

    def authorized(self, authorization: str, *, write: bool) -> bool:
        expected = self.ingest if write else self.read
        return hmac.compare_digest(authorization.encode(), f"Bearer {expected}".encode())
