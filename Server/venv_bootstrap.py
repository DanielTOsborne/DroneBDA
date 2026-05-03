"""
Ensure a repo-local .venv, run inside it, then sync requirements (PEP 668 / Raspberry Pi OS).

Set DRONEBDA_SERVER_SKIP_VENV=1 to disable (you manage Python and packages yourself).
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _venv_python(repo: Path) -> Path:
    if sys.platform == "win32":
        return repo / ".venv" / "Scripts" / "python.exe"
    return repo / ".venv" / "bin" / "python"


def _skip_bootstrap() -> bool:
    return os.environ.get("DRONEBDA_SERVER_SKIP_VENV", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def ensure_venv() -> None:
    """Create ``.venv`` if missing; re-exec this module under the venv interpreter if needed."""
    if _skip_bootstrap():
        return

    root = _repo_root()
    vpy = _venv_python(root)

    if not vpy.is_file():
        print("DroneBDA server: creating .venv in repo root…", file=sys.stderr)
        subprocess.run(
            [sys.executable, "-m", "venv", str(root / ".venv")],
            check=True,
        )

    if not vpy.is_file():
        print(f"DroneBDA server: expected venv python at {vpy}", file=sys.stderr)
        sys.exit(1)

    try:
        here = Path(sys.executable).resolve()
        there = vpy.resolve()
    except OSError:
        there = vpy

    if here != there:
        # Preserve CLI args after ``python -m Server.run`` (if any).
        if len(sys.argv) >= 3 and sys.argv[1] == "-m":
            extra = sys.argv[3:]
        else:
            extra = []
        argv = [str(vpy), "-m", "Server.run", *extra]
        # Use subprocess (not os.execv): paths with spaces on Windows break execv argv handling.
        code = subprocess.call(argv)
        raise SystemExit(code)


def ensure_requirements() -> None:
    """``pip install -r requirements.txt`` using the current interpreter (should be .venv)."""
    if _skip_bootstrap():
        return

    req = _repo_root() / "requirements.txt"
    if not req.is_file():
        return

    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "pip install failed\n")
        sys.exit(proc.returncode)
