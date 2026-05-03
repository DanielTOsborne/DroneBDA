"""Run ``report.py`` the same way as a manual test: cwd = ``Output Reporting/`` so ``import amr`` works."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from flask import Blueprint, render_template

bp = Blueprint("test_report", __name__, url_prefix="/test-report")


def _reporting_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "Output Reporting"


def run_sample_report_subprocess() -> tuple[int, str, str]:
    """
    Run ``python report.py`` with working directory ``Output Reporting/``.

    Returns (returncode, stdout, stderr). returncode -1 if the script file is missing.
    """
    reporting = _reporting_dir()
    script = reporting / "report.py"
    if not script.is_file():
        return -1, "", f"Missing: {script.as_posix()}"

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(reporting),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


@bp.route("/")
def index():
    return render_template("test_report.html", reporting_dir=_reporting_dir().as_posix())


@bp.route("/run", methods=["POST"])
def run():
    code, out, err = run_sample_report_subprocess()
    return render_template(
        "test_report_result.html",
        returncode=code,
        stdout=out,
        stderr=err,
        reporting_dir=_reporting_dir().as_posix(),
    )
