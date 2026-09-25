import os
from pathlib import Path

from starlette.applications import Starlette

from .config import ServerConfiguration
from .http import create_app
from .security import Credentials
from .service import ReceiverService
from .storage import SqliteSnapshots


def application(configuration: ServerConfiguration, directory: Path) -> Starlette:
    credentials = Credentials(
        os.environ.get(configuration.ingest_token_env, ""), os.environ.get(configuration.read_token_env, "")
    )
    path = configuration.data_directory
    root = path if path.is_absolute() else directory / path
    return create_app(ReceiverService(SqliteSnapshots(root)), credentials)
