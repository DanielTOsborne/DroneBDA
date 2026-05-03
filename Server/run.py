"""Run the hub server: ``python -m Server.run`` from the repo root."""

from __future__ import annotations

import os


def main() -> None:
    import sys

    from Server.app import create_app
    from Server.system_state import reset_to_standby_preserving_restart

    app = create_app()
    reset_to_standby_preserving_restart()
    host = os.environ.get("DRONEBDA_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("DRONEBDA_SERVER_PORT", "8000"))
    bind = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(
        f"[DroneBDA] Hub PID {os.getpid()} — open http://{bind}:{port}/ "
        f"(if you see 500 in the browser on :8000, another process may already be using that port; "
        f"try {bind}:{port}/__dronebda_ping or set DRONEBDA_SERVER_PORT).",
        file=sys.stderr,
    )
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    from Server import venv_bootstrap

    venv_bootstrap.ensure_venv()
    venv_bootstrap.ensure_requirements()
    main()
