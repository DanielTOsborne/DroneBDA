"""Read/write repo-root ``system_state.txt`` (shared with non-server components)."""

from __future__ import annotations

from pathlib import Path

from Server.config import get_system_state_path

DEFAULT_CURRENT = "standby"
DEFAULT_RESTART = False
DEFAULT_START_POSITION = ""
KEY_START_POSITION = "start position"


def _parse_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes")


def read_state(path: Path | None = None) -> tuple[str, bool, str]:
    """Return ``(current_state, restart_state, start_position_value)``. Missing file → defaults."""
    p = path or get_system_state_path()
    if not p.is_file():
        return DEFAULT_CURRENT, DEFAULT_RESTART, DEFAULT_START_POSITION
    current = DEFAULT_CURRENT
    restart = DEFAULT_RESTART
    start_position = DEFAULT_START_POSITION
    for raw in p.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, _, val = raw.partition("=")
        k = key.strip()
        v = val
        if k == "current state":
            current = v.strip()
        elif k.lower() == "restartstate":
            restart = _parse_bool(v)
        elif k == KEY_START_POSITION:
            start_position = v.strip()
    return current, restart, start_position


def write_state(
    current: str,
    *,
    restart: bool | None = None,
    start_position: str | None = None,
    path: Path | None = None,
) -> None:
    """
    Write three-line state file (``current state``, ``restartState``, ``start position``).

    If ``restart`` or ``start_position`` is None, the previous value from disk is kept.
    """
    p = path or get_system_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = read_state(p)
    if restart is None:
        restart = prev[1]
    if start_position is None:
        start_position = prev[2]
    text = (
        f"current state={current}\n"
        f"restartState={'true' if restart else 'false'}\n"
        f"{KEY_START_POSITION}={start_position}\n"
    )
    p.write_text(text, encoding="utf-8", newline="\n")


def ensure_default_state_file(path: Path | None = None) -> None:
    """Create file with defaults if it does not exist."""
    p = path or get_system_state_path()
    if not p.is_file():
        write_state(
            DEFAULT_CURRENT,
            restart=DEFAULT_RESTART,
            start_position=DEFAULT_START_POSITION,
            path=p,
        )


def reset_to_standby_preserving_restart(path: Path | None = None) -> None:
    """Set ``current state`` to ``standby``; keep ``restartState`` and ``start position``."""
    _, restart, start_position = read_state(path)
    write_state(
        DEFAULT_CURRENT,
        restart=restart,
        start_position=start_position,
        path=path,
    )
