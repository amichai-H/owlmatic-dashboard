"""Typed server YAML. Secrets are resolved only in the composition root."""

import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from .wire import Contract


class ServerConfiguration(Contract):
    version: Literal[1] = 1
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    data_directory: Path = Path(".data")
    ingest_token_env: str = "OWLMATIC_DASHBOARD_INGEST_TOKEN"
    read_token_env: str = "OWLMATIC_DASHBOARD_READ_TOKEN"


def load(path: Path) -> ServerConfiguration:
    if path.stat().st_size > 65536:
        raise ValueError("Server YAML exceeds 64 KiB")
    try:
        return ServerConfiguration.model_validate_json(json.dumps(yaml.safe_load(path.read_bytes())))
    except (yaml.YAMLError, TypeError) as error:
        raise ValueError("Invalid server YAML") from error
