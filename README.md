# Owlmatic Dashboard

Independent, self-hosted statistics receiver and dashboard for [Owlmatic](https://github.com/amichai-H/Owlmatic). Python 3.11+, strict typing, SQLite persistence, and an ASGI HTTP adapter. It consumes the versioned snapshot contract and does not import Owlmatic's implementation.

## Local quickstart

```sh
git clone https://github.com/amichai-H/owlmatic-dashboard.git
cd owlmatic-dashboard
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp dashboard.example.yaml dashboard.yaml
export OWLMATIC_DASHBOARD_INGEST_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export OWLMATIC_DASHBOARD_READ_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
owlmatic-dashboard --config dashboard.yaml
```

Open **http://127.0.0.1:8765** and enter the read token you set. Copy the ingest token into the environment of the Owlmatic client; it is the only credential the client needs. Tokens must be distinct and at least 24 printable characters. The browser keeps the read token only in page memory, with no cookies or browser storage.

In Owlmatic, copy `config/observability.example.yaml`, set `export.mode` to `manual` or `after_workflow`, select sharing options, and run:

```sh
owlmatic export configure --file observability.yaml
owlmatic export preview --json
owlmatic export push --json
```

The example client endpoint already points to this local receiver. Totals are shared by default; savings, daily data, and workflow identifiers require opting in. Configure a savings baseline in Owlmatic before expecting token estimates.

## Contract and behavior

- `POST /api/v1/snapshots`: ingest bearer token; JSON body matching [snapshot v1](contracts/statistics-snapshot-v1.schema.json); `Idempotency-Key` equal to `snapshot_id`. Maximum body: 1 MiB.
- `GET /api/v1/sources`: read bearer token; latest snapshots with source-ID cursor pagination, 100 sources per page.
- `/`: static dashboard; no metrics are included until authenticated API requests succeed.
- The server commits before acknowledging, rejects conflicting IDs/sequences, and ignores out-of-order snapshots. Sequence numbers belong to one client data directory; do not clone that directory across installations.
- Snapshots replace, never add to, the previous snapshot for their source. The dashboard deliberately shows one source/window at a time instead of summing overlapping windows or mixing unlike savings baselines.
- Savings remain user-configured estimates, not measured billing or human time saved. Each snapshot explicitly identifies its scope as retained local runs.

## Deployment and security

This alpha is a **single trusted organization receiver**, not a multi-tenant SaaS. An ingest credential can submit any source ID; per-device enrollment, tenant authorization, SSO, and scoped credentials are not implemented. Give the ingest token only to trusted clients. Use separate instances for separate trust domains.

Bind to loopback by default. For remote use, put a maintained TLS reverse proxy in front, set request/body/time limits there, and restrict network access. Do not expose plaintext bearer authentication on the public internet. No CORS is enabled; the UI and API share an origin. Redirects are not required by the client contract. There are no third-party frontend assets or telemetry.

The database directory is private to the OS user. Back up the entire directory consistently, including WAL state; stop the service for a simple file backup. Unknown schema versions fail closed. Latest snapshots and idempotency receipts are retained indefinitely in this first version; monitor disk usage. Disabling client export does not delete data already received. There is no public deletion endpoint yet; use your instance's data lifecycle procedure.

## Development

```sh
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy
python -m pytest -q
python -m build
```

The `wire.py` types are the vendored v1 public contract, not an application dependency. Contract changes require coordinated schema/fixture updates and a new schema version for breaking changes. Tests cover authentication separation, bounded input, idempotency, conflicts, out-of-order delivery, restart persistence, pagination, and architecture boundaries.

Apache-2.0. This is an initial alpha; review the limitations before enterprise deployment.

## Measurement snapshots (v2)

This receiver accepts v1 at `/api/v1/snapshots` and v2 at `/api/v2/snapshots`. The dashboard uses `/api/v2/sources`; the legacy `/api/v1/sources` response remains compatible and omits measurement data. V1 records migrate without invented receipt times. V2 provides configured source labels, receipt freshness, measured execution tokens, historical operational comparisons, context estimates, and net estimates when cost coverage is complete. Negative estimates remain negative; absent values remain unknown. Legacy configured estimates are labeled separately.

The [published v2 schema](contracts/statistics-snapshot-v2.schema.json) is vendored and does not depend on the Owlmatic package. Upgrade this receiver before configuring v2 senders. Measurement history covers retained tasks, separate from the run statistics calendar window. The browser Refresh button fetches already exported snapshots; it does not invoke agents or upload local runs. No raw prompts, histories, logs, or credentials belong in snapshots.
