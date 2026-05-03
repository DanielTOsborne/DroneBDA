"""Reports hub — list BoM .md + DD2768 pairs, render markdown, download PDF."""

from __future__ import annotations

import re
from pathlib import Path

import markdown
from flask import Blueprint, abort, render_template, send_file, url_for
from werkzeug.utils import secure_filename

from Server.config import get_reports_dir

bp = Blueprint("reports", __name__, url_prefix="/reports")
_STEM_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")
# "extra" includes tables, fenced code, footnotes, etc.
_MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]


def _reports_dir() -> Path:
    return get_reports_dir()


def _resolve_stem(stem: str) -> tuple[Path, Path] | None:
    if not stem or not _STEM_SAFE.match(stem):
        return None
    root = _reports_dir().resolve()
    md = (root / f"{stem}.md").resolve()
    pdf = (root / f"{stem}_DD2768.pdf").resolve()
    try:
        md.relative_to(root)
        pdf.relative_to(root)
    except ValueError:
        return None
    if not md.is_file() or not pdf.is_file():
        return None
    return md, pdf


def list_report_pairs() -> list[dict]:
    """Each dict: stem, label (stem), md Path, pdf Path — only complete pairs, newest first."""
    root = _reports_dir()
    if not root.is_dir():
        return []

    pairs: list[dict] = []
    root_res = root.resolve()
    for md_path in root.glob("*.md"):
        if not md_path.is_file():
            continue
        stem = md_path.stem
        pdf_path = root / f"{stem}_DD2768.pdf"
        if not pdf_path.is_file():
            continue
        try:
            md_path.resolve().relative_to(root_res)
            pdf_path.resolve().relative_to(root_res)
        except ValueError:
            continue
        mtime = max(md_path.stat().st_mtime, pdf_path.stat().st_mtime)
        pairs.append(
            {
                "stem": stem,
                "label": stem,
                "mtime": mtime,
            }
        )

    pairs.sort(key=lambda p: p["mtime"], reverse=True)
    return pairs


@bp.route("/")
def index():
    pairs = list_report_pairs()
    return render_template("reports.html", pairs=pairs, has_pairs=bool(pairs))


@bp.route("/view/<stem>")
def view_report(stem: str):
    resolved = _resolve_stem(stem)
    if resolved is None:
        abort(404)
    md_path, pdf_path = resolved
    text = md_path.read_text(encoding="utf-8", errors="replace")
    html = markdown.markdown(text, extensions=_MD_EXTENSIONS)
    dl_url = url_for("reports.download_dd2768", stem=stem)
    return render_template(
        "report_view.html",
        stem=stem,
        label=stem,
        content_html=html,
        download_url=dl_url,
    )


@bp.route("/dd2768/<stem>")
def download_dd2768(stem: str):
    resolved = _resolve_stem(stem)
    if resolved is None:
        abort(404)
    _md_path, pdf_path = resolved
    name = secure_filename(f"{stem}_DD2768.pdf") or "DD2768.pdf"
    return send_file(pdf_path, as_attachment=True, download_name=name)
