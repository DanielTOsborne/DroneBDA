"""Resolve LiDAR CSV at repo root and run BoM generation (``Output Reporting/report.py``)."""

from __future__ import annotations

import sys
from pathlib import Path


def resolve_pointcloud_csv(repo_root: Path) -> tuple[Path, str]:
    """
    Prefer ``pointcloud.csv`` at repo root; else ``scenario_B_points.csv``.

    Returns ``(absolute_csv_path, short description for operator / flash message)``.
    """
    root = repo_root.resolve()
    primary = root / "pointcloud.csv"
    if primary.is_file():
        return primary, "pointcloud.csv at repo root (cloud scan output)"
    fallback = root / "scenario_B_points.csv"
    if fallback.is_file():
        return (
            fallback,
            "scenario_B_points.csv — pointcloud.csv not found at repo root; using demo fallback",
        )
    raise FileNotFoundError(
        "No point cloud CSV at repo root: need pointcloud.csv or scenario_B_points.csv."
    )


def generate_bom_on_disk(repo_root: Path, csv_path: Path) -> Path | None:
    """
    Import ``report`` from ``Output Reporting/`` and call ``generate_bom_from_pointcloud_csv``.

    Inserts ``Output Reporting`` at the front of ``sys.path`` once per process if needed.
    """
    reporting = (repo_root / "Output Reporting").resolve()
    script = reporting / "report.py"
    if not script.is_file():
        raise FileNotFoundError(f"Missing BoM module: {script.as_posix()}")
    rs = str(reporting)
    if rs not in sys.path:
        sys.path.insert(0, rs)
    import report as bom_report  # noqa: WPS433 — local ``Output Reporting/report.py``

    return bom_report.generate_bom_from_pointcloud_csv(csv_path)
