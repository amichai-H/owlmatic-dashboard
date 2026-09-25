import json
import sqlite3
from pathlib import Path

from test_receiver import AUTH, client, snapshot

from owlmatic_dashboard.storage import SqliteSnapshots
from owlmatic_dashboard.wire import StatisticsSnapshotV2


def measurement_snapshot() -> StatisticsSnapshotV2:
    data = snapshot().model_dump()
    data.update(
        {
            "schema_version": "2",
            "source_label": "Measured deployment",
            "measurements_shared": True,
            "measurements": {
                "observed_tasks": 1,
                "measured_tasks": 1,
                "unattributed_tasks": 0,
                "measured_agent_tokens": 100,
                "estimated_operational_savings": -20,
            },
        }
    )
    return StatisticsSnapshotV2.model_validate(data)


def test_v2_receiver_retains_negative_estimates_and_v1_compatibility(tmp_path: Path) -> None:
    value = measurement_snapshot()
    headers = {
        "Authorization": f"Bearer {AUTH.ingest}",
        "Content-Type": "application/json",
        "Idempotency-Key": value.snapshot_id,
    }
    with client(tmp_path) as api:
        assert (
            api.post("/api/v1/snapshots", content=value.model_dump_json(), headers=headers).status_code == 400
        )
        assert (
            api.post("/api/v2/snapshots", content=value.model_dump_json(), headers=headers).status_code == 200
        )
        assert (
            api.post("/api/v2/snapshots", content=value.model_dump_json(), headers=headers).json()["status"]
            == "duplicate"
        )
        read = {"Authorization": f"Bearer {AUTH.read}"}
        page = api.get("/api/v2/sources", headers=read).json()
        assert page["sources"][0]["measurements"]["estimated_operational_savings"] == -20
        assert "estimated_net_savings" not in page["sources"][0]["measurements"]
        assert page["receipts"][0]["received_at"]
        old_page = api.get("/api/v1/sources", headers=read).json()
        assert old_page["sources"][0]["schema_version"] == "1"
        assert "measurements" not in old_page["sources"][0] and "receipts" not in old_page


def test_v1_database_migration_preserves_snapshot_and_has_unknown_receipt(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "dashboard.sqlite") as db:
        db.execute("CREATE TABLE sources(id TEXT PRIMARY KEY,sequence INTEGER NOT NULL,body TEXT NOT NULL)")
        db.execute("CREATE TABLE receipts(id TEXT PRIMARY KEY,digest TEXT NOT NULL)")
        db.execute(
            "INSERT INTO sources VALUES(?,?,?)", (snapshot().source_id, 1, snapshot().model_dump_json())
        )
        db.execute("PRAGMA user_version=1")
    page = SqliteSnapshots(tmp_path).page(None, 100)
    assert page.sources == (snapshot(),) and page.receipts[0].received_at is None


def test_v2_contract_is_published() -> None:
    path = Path(__file__).resolve().parents[1] / "contracts/statistics-snapshot-v2.schema.json"
    assert json.loads(path.read_text()) == StatisticsSnapshotV2.model_json_schema()
