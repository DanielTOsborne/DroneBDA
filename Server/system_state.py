"""Read/write repo-root ``system_state.txt`` (shared with non-server components)."""

from __future__ import annotations

from pathlib import Path

from Server.config import get_system_state_path

DEFAULT_CURRENT = "standby"
DEFAULT_RESTART = False


def _parse_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes")


def read_state(path: Path | None = None) -> tuple[str, bool]:
    """Return ``(current_state, restart_state)``. Missing file → defaults."""
    p = path or get_system_state_path()
    if not p.is_file():
        return DEFAULT_CURRENT, DEFAULT_RESTART
    current = DEFAULT_CURRENT
    restart = DEFAULT_RESTART
    for raw in p.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, _, val = raw.partition("=")
        k = key.strip()
        v = val.strip()
        if k == "current state":
            current = v
        elif k.lower() == "restartstate":
            restart = _parse_bool(v)
    return current, restart


def write_state(
    current: str,
    *,
    restart: bool | None = None,
    path: Path | None = None,
) -> None:
    """Write two-line state file. If ``restart`` is None, preserve the previous value."""
    p = path or get_system_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if restart is None:
        _, restart = read_state(p)
    text = f"current state={current}\nrestartState={'true' if restart else 'false'}\n"
    p.write_text(text, encoding="utf-8", newline="\n")


def ensure_default_state_file(path: Path | None = None) -> None:
    """Create file with defaults if it does not exist."""
    p = path or get_system_state_path()
    if not p.is_file():
        write_state(DEFAULT_CURRENT, restart=DEFAULT_RESTART, path=p)


def reset_to_standby_preserving_restart(path: Path | None = None) -> None:
    """Set ``current state`` to ``standby``; keep existing ``restartState``."""
    _, restart = read_state(path)
    write_state(DEFAULT_CURRENT, restart=restart, path=path)
