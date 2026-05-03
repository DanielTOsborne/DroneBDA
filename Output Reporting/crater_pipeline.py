"""
Load craters for the reporting slice from a LiDAR-style point cloud CSV.

Uses ``Working_Crater_analysis.py`` at the repo root (same crater definition
as ``report.Crater``). Add the repo root to ``sys.path`` so the analysis
module can be imported from ``Output Reporting/`` without installing a package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _ensure_repo_root_on_path() -> None:
    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def load_report_craters_from_pointcloud_csv(
    csv_path: str | Path,
    *,
    runway_heading: float = 45.0,
    depth_threshold_m: float = 0.10,
    min_crater_cells: int = 9,
    grid_res_m: float = 1.0,
    closing_iters: int = 2,
) -> list:
    """
    Run the point-cloud crater pipeline and return ``report.Crater`` instances.

    Parameters mirror ``CraterAnalyzer`` / ``main()`` in ``Working_Crater_analysis.py``.
    Requires ``scipy`` (morphology on the depth grid).
    """
    _ensure_repo_root_on_path()
    import Working_Crater_analysis as wca  # noqa: E402

    from report import Crater as ReportCrater  # noqa: E402

    path = Path(csv_path)
    points = wca.load_points_from_csv(str(path))
    analyzer = wca.CraterAnalyzer(
        points=points,
        runway_heading=runway_heading,
        depth_threshold_m=depth_threshold_m,
        min_crater_cells=min_crater_cells,
        grid_res_m=grid_res_m,
        closing_iters=closing_iters,
    )
    found = analyzer.analyse()
    out = []
    for c in found:
        out.append(
            ReportCrater(
                crater_id=c.crater_id,
                ns_diameter_cm=c.ns_diameter_cm,
                ew_diameter_cm=c.ew_diameter_cm,
                max_depth_cm=c.max_depth_cm,
                latitude=c.latitude,
                longitude=c.longitude,
                image_path=c.image_path,
            )
        )
    return out
