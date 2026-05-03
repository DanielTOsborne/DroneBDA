"""Server configuration (paths, env overrides)."""

from __future__ import annotations

import os
from pathlib import Path


def get_reports_dir() -> Path:
    """BoM markdown + DD2768 PDFs: ``Output Reporting/Reports`` under repo root."""
    return Path(__file__).resolve().parent.parent / "Output Reporting" / "Reports"


def get_filesystem_root() -> Path:
    """Directory exposed by the Filesystem browser. Override with DRONEBDA_SERVER_ROOT."""
    raw = os.environ.get("DRONEBDA_SERVER_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()
