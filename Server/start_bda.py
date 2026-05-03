"""Start BDA: camera scan flow through move and cloud scan (``cameraScan`` … ``moveToPoint`` → ``cloudScan``)."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from Server.cloud_scan_report import generate_bom_on_disk, resolve_pointcloud_csv
from Server.config import get_repo_root
from Server.system_state import DEFAULT_CURRENT, read_state, write_state

STATE_SCAN = "cameraScan"
STATE_COMPLETE = "cameraComplete"
STATE_MOVE = "moveToPoint"
STATE_CLOUD = "cloudScan"

# Old pipeline states — normalize to standby when this page loads so the flow stays coherent.
_LEGACY_STATES = frozenset({"cloudComplete", "dataComplete"})

# Temporary testing: simulate teammate transitions (remove when pipeline drives state).
# Includes ``standby`` → ``cameraScan`` so the admin row appears without posting ``Start BDA`` first.
_ADMIN_SIMULATE_NEXT: dict[str, str] = {
    DEFAULT_CURRENT: STATE_SCAN,
    STATE_SCAN: STATE_COMPLETE,
    STATE_COMPLETE: STATE_MOVE,
    STATE_MOVE: STATE_CLOUD,
    STATE_CLOUD: DEFAULT_CURRENT,
}

# Camera scan output (repo root): fixed name and folder from cameraScan → cameraComplete flow.
_ANNOTATED_MAP_REL = Path("camera") / "map" / "annotated_map.png"

bp = Blueprint("start_bda", __name__, url_prefix="/start-bda")


def find_first_pass_image() -> Path | None:
    """``camera/map/annotated_map.png`` under repo root (annotated map from camera scan)."""
    p = get_repo_root() / _ANNOTATED_MAP_REL
    return p if p.is_file() else None


def first_pass_image_url() -> str | None:
    if find_first_pass_image() is None:
        return None
    return url_for("start_bda.first_pass_image")


def _split_lat_lon(start_position: str) -> tuple[str, str]:
    s = (start_position or "").strip()
    if not s:
        return "", ""
    if "," in s:
        lat, _, rest = s.partition(",")
        return lat.strip(), rest.strip()
    return s, ""


def _finish_cloud_scan_and_report(restart: bool):
    """Generate BoM from ``pointcloud.csv`` (or demo fallback), set ``standby``, redirect to new report."""
    repo = get_repo_root()
    try:
        csv_path, source_note = resolve_pointcloud_csv(repo)
    except FileNotFoundError as err:
        write_state(DEFAULT_CURRENT, restart=restart)
        flash(str(err))
        return redirect(url_for("reports.index"))

    try:
        written = generate_bom_on_disk(repo, csv_path)
    except Exception as exc:  # noqa: BLE001 — surface any analysis / write failure
        write_state(DEFAULT_CURRENT, restart=restart)
        flash(f"BoM generation failed: {exc}")
        return redirect(url_for("reports.index"))

    write_state(DEFAULT_CURRENT, restart=restart)

    if written is None:
        flash(f"{source_note} — no Markdown file written (check report output mode).")
        return redirect(url_for("reports.index"))

    flash(f"Point cloud input: {source_note}")
    return redirect(url_for("reports.view_report", stem=written.stem))


@bp.route("/")
def index():
    current, restart, start_position = read_state()
    if current in _LEGACY_STATES:
        write_state(DEFAULT_CURRENT, restart=restart, start_position=start_position)
        current = DEFAULT_CURRENT

    scanning = current == STATE_SCAN
    complete = current == STATE_COMPLETE
    moving = current == STATE_MOVE
    cloud_scan = current == STATE_CLOUD
    img_url = first_pass_image_url() if complete else None
    show_start = current not in (
        STATE_SCAN,
        STATE_COMPLETE,
        STATE_MOVE,
        STATE_CLOUD,
    )
    admin_next = _ADMIN_SIMULATE_NEXT.get(current)
    lat_val, lon_val = _split_lat_lon(start_position)
    return render_template(
        "start_bda.html",
        current_state=current,
        restart_state=restart,
        start_position_value=start_position,
        latitude_value=lat_val,
        longitude_value=lon_val,
        scanning=scanning,
        complete=complete,
        moving=moving,
        cloud_scan=cloud_scan,
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
    _, restart, _ = read_state()
    lat = request.form.get("latitude", "").strip()
    lon = request.form.get("longitude", "").strip()
    start_position = f"{lat},{lon}" if lat and lon else ""
    write_state(STATE_SCAN, restart=restart, start_position=start_position)
    return redirect(url_for("start_bda.index"))


@bp.route("/admin-proceed", methods=["POST"])
def admin_proceed():
    current, restart, _ = read_state()
    if current == STATE_CLOUD:
        return _finish_cloud_scan_and_report(restart)
    next_state = _ADMIN_SIMULATE_NEXT.get(current)
    if next_state is None:
        abort(400)
    write_state(next_state, restart=restart)
    return redirect(url_for("start_bda.index"))


@bp.route("/override-location", methods=["POST"])
def override_location():
    """Manual placement: from ``moveToPoint`` go straight to ``cloudScan`` (same as autonomous arrival)."""
    current, restart, _ = read_state()
    if current != STATE_MOVE:
        abort(400)
    write_state(STATE_CLOUD, restart=restart)
    return redirect(url_for("start_bda.index"))


@bp.route("/done-collecting", methods=["POST"])
def done_collecting():
    """LiDAR collection finished: run BoM from point cloud CSV, set ``standby``, open the new report."""
    current, restart, _ = read_state()
    if current != STATE_CLOUD:
        abort(400)
    return _finish_cloud_scan_and_report(restart)


@bp.route("/accept", methods=["POST"])
def accept():
    current, restart, _ = read_state()
    if current != STATE_COMPLETE:
        abort(400)
    write_state(STATE_MOVE, restart=restart)
    return redirect(url_for("start_bda.index"))
