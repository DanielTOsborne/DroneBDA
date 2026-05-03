"""Start BDA: camera scan flow through move and cloud scan (``cameraScan`` … ``moveToPoint`` → ``cloudScan``)."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, send_file, url_for

from Server.config import get_repo_root
from Server.system_state import DEFAULT_CURRENT, read_state, write_state

STATE_SCAN = "cameraScan"
STATE_COMPLETE = "cameraComplete"
STATE_MOVE = "moveToPoint"
STATE_CLOUD = "cloudScan"
STATE_CLOUD_COMPLETE = "cloudComplete"
STATE_DATA_COMPLETE = "dataComplete"

# Temporary testing: simulate teammate transitions (remove when pipeline drives state).
# Includes ``standby`` → ``cameraScan`` so the admin row appears without posting ``Start BDA`` first.
_ADMIN_SIMULATE_NEXT: dict[str, str] = {
    DEFAULT_CURRENT: STATE_SCAN,
    STATE_SCAN: STATE_COMPLETE,
    STATE_COMPLETE: STATE_MOVE,
    STATE_MOVE: STATE_CLOUD,
    STATE_CLOUD: STATE_CLOUD_COMPLETE,
    STATE_CLOUD_COMPLETE: STATE_DATA_COMPLETE,
    STATE_DATA_COMPLETE: DEFAULT_CURRENT,
}

_FIRST_PASS_NAMES = ("firstPass.jpg", "firstPass.jpeg", "firstPass.png")

bp = Blueprint("start_bda", __name__, url_prefix="/start-bda")


def find_first_pass_image() -> Path | None:
    """First existing ``firstPass.*`` under repo root (teammate pipeline output)."""
    root = get_repo_root()
    for name in _FIRST_PASS_NAMES:
        p = root / name
        if p.is_file():
            return p
    return None


def first_pass_image_url() -> str | None:
    if find_first_pass_image() is None:
        return None
    return url_for("start_bda.first_pass_image")


@bp.route("/")
def index():
    current, restart = read_state()
    scanning = current == STATE_SCAN
    complete = current == STATE_COMPLETE
    moving = current == STATE_MOVE
    cloud_scan = current == STATE_CLOUD
    cloud_complete = current == STATE_CLOUD_COMPLETE
    data_complete = current == STATE_DATA_COMPLETE
    img_url = first_pass_image_url() if complete else None
    show_start = current not in (
        STATE_SCAN,
        STATE_COMPLETE,
        STATE_MOVE,
        STATE_CLOUD,
        STATE_CLOUD_COMPLETE,
        STATE_DATA_COMPLETE,
    )
    admin_next = _ADMIN_SIMULATE_NEXT.get(current)
    return render_template(
        "start_bda.html",
        current_state=current,
        restart_state=restart,
        scanning=scanning,
        complete=complete,
        moving=moving,
        cloud_scan=cloud_scan,
        cloud_complete=cloud_complete,
        data_complete=data_complete,
        show_start=show_start,
        first_pass_url=img_url,
        first_pass_missing=complete and img_url is None,
        admin_next=admin_next,
    )


@bp.route("/first-pass-image")
def first_pass_image():
    path = find_first_pass_image()
    if path is None:
        abort(404)
    mimetype = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(path.suffix.lower(), None)
    return send_file(path, mimetype=mimetype)


@bp.route("/run", methods=["POST"])
def run():
    _, restart = read_state()
    write_state(STATE_SCAN, restart=restart)
    return redirect(url_for("start_bda.index"))


@bp.route("/admin-proceed", methods=["POST"])
def admin_proceed():
    current, restart = read_state()
    next_state = _ADMIN_SIMULATE_NEXT.get(current)
    if next_state is None:
        abort(400)
    write_state(next_state, restart=restart)
    return redirect(url_for("start_bda.index"))


@bp.route("/override-location", methods=["POST"])
def override_location():
    """Manual placement: from ``moveToPoint`` go straight to ``cloudScan`` (same as autonomous arrival)."""
    current, restart = read_state()
    if current != STATE_MOVE:
        abort(400)
    write_state(STATE_CLOUD, restart=restart)
    return redirect(url_for("start_bda.index"))


@bp.route("/done-collecting", methods=["POST"])
def done_collecting():
    """LiDAR collection finished manually; same end state as autonomous pipeline (``cloudComplete``)."""
    current, restart = read_state()
    if current != STATE_CLOUD:
        abort(400)
    write_state(STATE_CLOUD_COMPLETE, restart=restart)
    return redirect(url_for("start_bda.index"))


@bp.route("/accept", methods=["POST"])
def accept():
    current, restart = read_state()
    if current != STATE_COMPLETE:
        abort(400)
    write_state(STATE_MOVE, restart=restart)
    return redirect(url_for("start_bda.index"))
