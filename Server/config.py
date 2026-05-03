"""Server configuration (paths, env overrides)."""

from __future__ import annotations

import os
from pathlib import Path


def get_repo_root() -> Path:
    """DroneBDA repository root (parent of ``Server/``).

    Set ``DRONEBDA_REPO_ROOT`` on the Pi (or any host) if the app must resolve data files
    against a checkout that is not next to this ``Server/`` tree.
    """
    raw = os.environ.get("DRONEBDA_REPO_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def resolve_annotated_map_png() -> Path | None:
    """
    Annotated map shown in ``cameraComplete``.

    Resolution order:

    1. ``DRONEBDA_ANNOTATED_MAP`` — absolute path to a ``.png`` if set and the file exists.
    2. ``<repo>/camera/map/annotated_map.png`` (canonical).
    3. ``<repo>/map/annotated_map.png`` — legacy output when ``camera/find_craters.py`` ran with
       cwd at repo root (``cv2.imwrite("map/annotated_map.png", ...)``).
    """
    env = os.environ.get("DRONEBDA_ANNOTATED_MAP", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_file() else None
    root = get_repo_root()
    for rel in (
        Path("camera") / "map" / "annotated_map.png",
        Path("map") / "annotated_map.png",
    ):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def resolve_crater_offset_csv() -> Path | None:
    """
    CSV of crater offsets from the camera pipeline (``cameraComplete`` table).

    Resolution order:

    1. ``DRONEBDA_COORDINATES_CSV`` — absolute path if set and the file exists.
    2. ``DRONEBDA_CRATER_OFFSET_CSV`` — same (older name), if set and the file exists.
    3. ``<repo>/camera/coordinates.csv`` (canonical; lives in ``camera/``, not ``camera/map/``).
    """
    for key in ("DRONEBDA_COORDINATES_CSV", "DRONEBDA_CRATER_OFFSET_CSV"):
        raw = os.environ.get(key, "").strip()
        if raw:
            p = Path(raw).expanduser().resolve()
            if p.is_file():
                return p
    root = get_repo_root()
    p = root / "camera" / "coordinates.csv"
    return p if p.is_file() else None


def get_reports_dir() -> Path:
    """BoM markdown + DD2768 PDFs: ``Output Reporting/Reports`` under repo root."""
    return get_repo_root() / "Output Reporting" / "Reports"


def get_system_state_path() -> Path:
    """Cross-subsystem state file at repo root (``system_state.txt``)."""
    return get_repo_root() / "system_state.txt"


def get_filesystem_root() -> Path:
    """Directory exposed by the Filesystem browser. Override with DRONEBDA_SERVER_ROOT."""
    raw = os.environ.get("DRONEBDA_SERVER_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()
