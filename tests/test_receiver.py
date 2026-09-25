from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest
from starlette.testclient import TestClient

from owlmatic_dashboard.http import create_app
from owlmatic_dashboard.security import Credentials
from owlmatic_dashboard.service import ReceiverService
from owlmatic_dashboard.storage import SqliteSnapshots
from owlmatic_dashboard.wire import ExportScope, StatisticsSnapshot, UsageMetrics

AUTH = Credentials("ingest-fixture-" + "a" * 32, "read-fixture-" + "b" * 32)


def snapshot(index: int = 1, sequence: int = 1, source: int = 1) -> StatisticsSnapshot:
    return StatisticsSnapshot(
        snapshot_id=f"{index:032x}",
        source_id=f"{source:032x}",
        sequence=sequence,
        generated_at="2026-09-25T12:00:00+00:00",
        since="2026-09-25T00:00:00+00:00",
        days=1,
        shared=ExportScope(),
        usage=UsageMetrics(runs=1, terminal=1, verified=1, execution_errors=0, running=0, duration_ms=1000),
    )


def client(root: Path) -> TestClient:
    return TestClient(create_app(ReceiverService(SqliteSnapshots(root)), AUTH))


def post(client: TestClient, value: StatisticsSnapshot, credential: str = AUTH.ingest) -> int:
    return cast(
        int,
        client.post(
            "/api/v1/snapshots",
            content=value.model_dump_json(exclude_none=True),
            headers={
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
                "Idempotency-Key": value.snapshot_id,
            },
        ).status_code,
    )


def test_auth_roles_and_public_assets(tmp_path: Path) -> None:
    with client(tmp_path) as api:
        assert api.get("/").status_code == 200
        assert "Content-Security-Policy" in api.get("/").headers
        assert api.get("/assets/app.js").status_code == 200
        assert api.get("/assets/dashboard.sqlite").status_code == 404
        assert api.get("/api/v1/sources").status_code == 401
        assert (
            api.get("/api/v1/sources", headers={"Authorization": f"Bearer {AUTH.ingest}"}).status_code == 401
        )
        assert post(api, snapshot(), AUTH.read) == 401
        assert post(api, snapshot()) == 200
        response = api.get("/api/v1/sources", headers={"Authorization": f"Bearer {AUTH.read}"})
        assert response.status_code == 200 and len(response.json()["sources"]) == 1


def test_idempotency_ordering_conflicts_and_restart(tmp_path: Path) -> None:
    store = SqliteSnapshots(tmp_path)
    assert store.accept(snapshot(1, 1)).status == "accepted"
    assert store.accept(snapshot(1, 1)).status == "duplicate"
    assert store.accept(snapshot(3, 3)).status == "accepted"
    assert store.accept(snapshot(2, 2)).status == "stale"
    restarted = SqliteSnapshots(tmp_path)
    assert restarted.page(None, 100).sources[0].sequence == 3
    with client(tmp_path) as api:
        assert post(api, snapshot(1, 9)) == 409
        assert post(api, snapshot(4, 3)) == 409
    assert restarted.page(None, 100).sources[0].usage.runs == 1


def test_concurrent_duplicates_commit_once(tmp_path: Path) -> None:
    store = SqliteSnapshots(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: store.accept(snapshot()).status, range(8)))
    assert statuses.count("accepted") == 1 and statuses.count("duplicate") == 7


def test_bounded_decoding_schema_and_idempotency_key(tmp_path: Path) -> None:
    headers = {"Authorization": f"Bearer {AUTH.ingest}", "Content-Type": "application/json"}
    with client(tmp_path) as api:
        assert api.post("/api/v1/snapshots", content="x" * 1048577, headers=headers).status_code == 413
        response = api.post("/api/v1/snapshots", content='{"secret":"SHOULD_NOT_ECHO"}', headers=headers)
        assert response.status_code == 400 and "SHOULD_NOT_ECHO" not in response.text
        assert (
            api.post("/api/v1/snapshots", content=snapshot().model_dump_json(), headers=headers).status_code
            == 400
        )
        response = api.get("/api/v1/sources?cursor=invalid", headers={"Authorization": f"Bearer {AUTH.read}"})
        assert response.status_code == 400


def test_cursor_pagination_has_no_overlap(tmp_path: Path) -> None:
    store = SqliteSnapshots(tmp_path)
    for i in range(1, 104):
        store.accept(snapshot(i, 1, i))
    first = store.page(None, 100)
    second = store.page(first.next_cursor, 100)
    assert len(first.sources) == 100 and len(second.sources) == 3 and second.next_cursor is None
    assert not {x.source_id for x in first.sources} & {x.source_id for x in second.sources}


def test_credentials_must_be_distinct() -> None:
    with pytest.raises(ValueError):
        Credentials("same" * 8, "same" * 8)


def test_public_schema_matches_vendored_types() -> None:
    import json

    path = Path(__file__).resolve().parents[1] / "contracts/statistics-snapshot-v1.schema.json"
    assert json.loads(path.read_text()) == StatisticsSnapshot.model_json_schema()


def test_no_core_dependency_or_any() -> None:
    import ast

    root = Path(__file__).resolve().parents[1] / "src/owlmatic_dashboard"
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            assert not (isinstance(node, ast.Name) and node.id == "Any"), str(path)
            if isinstance(node, ast.ImportFrom):
                assert node.module != "owlmatic" and not (node.module or "").startswith("owlmatic.")
