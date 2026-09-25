import argparse
from pathlib import Path

import uvicorn

from .bootstrap import application
from .config import load


def main() -> None:
    parser = argparse.ArgumentParser(prog="owlmatic-dashboard")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        configuration = load(args.config)
        app = application(configuration, args.config.absolute().parent)
    except (ValueError, OSError):
        parser.exit(
            2,
            "Invalid server configuration or credentials; check the YAML and token environment variables.\n",
        )
    uvicorn.run(app, host=configuration.host, port=configuration.port, access_log=False)


if __name__ == "__main__":
    main()
