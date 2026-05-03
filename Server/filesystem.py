"""Directory listing and file download (debug-style browser)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, abort, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from Server.config import get_filesystem_root

bp = Blueprint("filesystem", __name__, url_prefix="/filesystem")


def _under_root(root: Path, rel: str) -> Path | None:
    """Resolve rel under root; return None if path escapes root (incl. symlinks)."""
    root = root.resolve()
    if rel in ("", "."):
        candidate = root
    else:
        if ".." in Path(rel).parts:
            return None
        candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n / (1024 * 1024):.1f} MiB"


def _fmt_mtime(st: os.stat_result) -> str:
    ts = getattr(st, "st_mtime", 0.0)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M")


@bp.route("/", defaults={"rel_path": ""})
@bp.route("/<path:rel_path>")
def browse(rel_path: str):
    root = get_filesystem_root()
    target = _under_root(root, rel_path)
    if target is None:
        abort(404)

    if not target.exists():
        abort(404)

    if target.is_file():
        download = request.args.get("download", "").lower() in ("1", "true", "yes")
        return send_file(
            target,
            as_attachment=download,
            download_name=secure_filename(target.name) or "file",
        )

    entries: list[dict] = []
    try:
        names = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        abort(403)

    parent_rel = ""
    if target != root:
        parent_rel = str(target.parent.relative_to(root))
        if parent_rel == ".":
            parent_rel = ""

    for child in names:
        name = child.name
        if name.startswith("."):
            continue
        rel = str(child.relative_to(root)).replace("\\", "/")
        try:
            st = child.stat()
        except OSError:
            continue
        if child.is_dir():
            entries.append(
                {
                    "name": name + "/",
                    "href": url_for("filesystem.browse", rel_path=rel),
                    "size": "—",
                    "mtime": _fmt_mtime(st),
                    "is_dir": True,
                }
            )
        else:
            entries.append(
                {
                    "name": name,
                    "href": url_for("filesystem.browse", rel_path=rel),
                    "dl_href": url_for("filesystem.browse", rel_path=rel) + "?download=1",
                    "size": _fmt_size(st.st_size),
                    "mtime": _fmt_mtime(st),
                    "is_dir": False,
                }
            )

    display_path = "/" + rel_path.replace("\\", "/").strip("/") if rel_path else "/"
    return render_template(
        "filesystem_list.html",
        root=str(root),
        display_path=display_path,
        parent_href=url_for("filesystem.browse", rel_path=parent_rel) if target != root else None,
        entries=entries,
    )
