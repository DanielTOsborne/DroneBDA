"""Delete generated BoM artifacts (``bom*`` files) from ``Output Reporting/Reports/``."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, render_template

from Server.config import get_reports_dir

bp = Blueprint("clear_reports", __name__, url_prefix="/clear-reports")


def _bom_files_in_reports() -> list[Path]:
    root = get_reports_dir()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.iterdir():
        if p.is_file() and p.name.startswith("bom"):
            out.append(p)
    return sorted(out, key=lambda x: x.name.lower())


@bp.route("/")
def index():
    paths = _bom_files_in_reports()
    return render_template(
        "clear_reports.html",
        reports_dir=get_reports_dir().as_posix(),
        files=paths,
        count=len(paths),
    )


@bp.route("/run", methods=["POST"])
def run():
    deleted: list[str] = []
    errors: list[str] = []
    for p in _bom_files_in_reports():
        try:
            p.unlink()
            deleted.append(p.name)
        except OSError as exc:
            errors.append(f"{p.name}: {exc}")
    return render_template(
        "clear_reports_result.html",
        deleted=deleted,
        errors=errors,
        reports_dir=get_reports_dir().as_posix(),
    )
