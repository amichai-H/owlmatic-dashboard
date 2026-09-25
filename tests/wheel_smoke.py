import sys
import tempfile
from pathlib import Path

from starlette.testclient import TestClient

import owlmatic_dashboard
from owlmatic_dashboard.http import create_app
from owlmatic_dashboard.security import Credentials
from owlmatic_dashboard.service import ReceiverService
from owlmatic_dashboard.storage import SqliteSnapshots

assert Path(owlmatic_dashboard.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
with tempfile.TemporaryDirectory() as directory:
    app = create_app(ReceiverService(SqliteSnapshots(Path(directory))), Credentials("a" * 32, "b" * 32))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/app.css").status_code == 200
        assert client.get("/api/v1/sources").status_code == 401
print("Installed dashboard wheel: assets, API, authentication passed")
