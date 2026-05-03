"""Run the hub server: ``python -m Server.run`` from the repo root."""

from __future__ import annotations

import os


def main() -> None:
    from Server.app import create_app

    app = create_app()
    host = os.environ.get("DRONEBDA_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("DRONEBDA_SERVER_PORT", "8000"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    from Server import venv_bootstrap

    venv_bootstrap.ensure_venv()
    venv_bootstrap.ensure_requirements()
    main()
