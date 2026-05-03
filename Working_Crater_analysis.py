"""
crater_analysis.py  -  Python 3.11
------------------------------------
Analyzes LiDAR elevation point clouds from a drone survey to characterise
runway craters.

Required outputs per crater
  1. Approximate GPS coordinates (lat, lon)
  2. Maximum depth  (centimetres below surrounding runway surface)
  3. N-S diameter   (longest dimension parallel to the runway axis, cm)
  4. E-W diameter   (longest dimension perpendicular to the runway axis, cm)

Coordinate convention
  The runway has a compass heading (0 = North, 90 = East, ...).
  "N-S / parallel" means along-runway; "E-W / perpendicular" means cross-runway.

Units
  TFmini-S LiDAR outputs distance in centimetres by default.
  Convert to metres on ingestion.  Internal maths uses metres; outputs are cm.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ElevationPoint:
    """A single geo-referenced LiDAR return over the runway."""
    lat: float          # decimal degrees
    lon: float          # decimal degrees
    elevation_m: float  # metres (convert from cm on ingestion if using TFmini-S)


@dataclass
class Crater:
    crater_id: str
    ns_diameter_cm: float      # longest dim parallel to runway
    ew_diameter_cm: float      # longest dim perpendicular to runway
    max_depth_cm: float
    latitude: float
    longitude: float
    image_path: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"  {self.crater_id}\n"
            f"    Latitude                  : {self.latitude:.7f} N\n"
            f"    Longitude                 : {self.longitude:.7f} E\n"
            f"    Max depth                 : {self.max_depth_cm:.1f} cm\n"
            f"    N-S diameter (parallel)   : {self.ns_diameter_cm:.1f} cm\n"
            f"    E-W diameter (perp)       : {self.ew_diameter_cm:.1f} cm\n"
            + (f"    Image                     : {self.image_path}\n"
               if self.image_path else "")
        )


# ---------------------------------------------------------------------------
# Geodetic helpers
# ---------------------------------------------------------------------------

_R = 6_371_000.0   # mean Earth radius, metres


def latlon_to_xy(lat: float, lon: float,
                 ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """
    Project (lat, lon) into a local East-North frame (metres).
    Valid for areas < ~10 km; no significant curvature error.
    """
    cos_lat = math.cos(math.radians(ref_lat))
    x = math.radians(lon - ref_lon) * _R * cos_lat   # East  (+ve = East)
    y = math.radians(lat - ref_lat) * _R              # North (+ve = North)
    return x, y


def xy_to_latlon(x: float, y: float,
                 ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """Inverse of latlon_to_xy."""
    cos_lat = math.cos(math.radians(ref_lat))
    lat = ref_lat + math.degrees(y / _R)
    lon = ref_lon + math.degrees(x / (_R * cos_lat))
    return lat, lon


def runway_axes(heading_deg: float) -> Tuple[Tuple[float, float],
                                              Tuple[float, float]]:
    """
    Return unit vectors (parallel, perpendicular) in the East-North frame.

    parallel      - along runway in the stated heading direction
    perpendicular - 90 degrees clockwise from parallel (right side of runway)
    """
    h = math.radians(heading_deg)
    par  = ( math.sin(h),  math.cos(h))   # (East, North) components
    perp = ( math.cos(h), -math.sin(h))
    return par, perp


# ---------------------------------------------------------------------------
# Core analyser
# ---------------------------------------------------------------------------

class CraterAnalyzer:
    """
    Detect and characterise craters in a geo-referenced elevation point cloud.

    Parameters
    ----------
    points            : list[ElevationPoint]
    runway_heading    : compass bearing of the runway, degrees (0-360)
    depth_threshold_m : a cell must be at least this deep below baseline to be
                        considered part of a crater  (default 0.10 m = 10 cm)
    min_crater_cells  : minimum grid cells in a connected region to be classed
                        as a real crater rather than noise  (default 9)
    grid_res_m        : grid cell size for rasterisation, metres  (default 1.0)
    closing_iters     : morphological closing iterations applied to the crater
                        mask before connected-component labelling.  Bridges
                        small gaps caused by sparse point clouds.
    """

    def __init__(
        self,
        points: List[ElevationPoint],
        runway_heading: float = 90.0,
        depth_threshold_m: float = 0.10,
        min_crater_cells: int = 9,
        grid_res_m: float = 1.0,
        closing_iters: int = 2,
    ):
        self.points = points
        self.heading = runway_heading
        self.depth_threshold_m = depth_threshold_m
        self.min_crater_cells = min_crater_cells
        self.grid_res_m = grid_res_m
        self.closing_iters = closing_iters

        # Survey centroid used as the local XY origin
        self.ref_lat = float(np.mean([p.lat for p in points]))
        self.ref_lon = float(np.mean([p.lon for p in points]))

        self._par, self._perp = runway_axes(runway_heading)

        # Lazily built
        self._grid_elev:  Optional[np.ndarray] = None
        self._depth_grid: Optional[np.ndarray] = None
        self._baseline:   Optional[np.ndarray] = None
        self._cx: Optional[np.ndarray] = None   # cell-centre x (East), metres
        self._cy: Optional[np.ndarray] = None   # cell-centre y (North), metres

    # ------------------------------------------------------------------
    # Grid construction
    # ------------------------------------------------------------------

    def _build_grid(self) -> None:
        res = self.grid_res_m

        # Project all points into local East-North metres
        xy = np.array([
            latlon_to_xy(p.lat, p.lon, self.ref_lat, self.ref_lon)
            for p in self.points
        ])
        xs, ys = xy[:, 0], xy[:, 1]
        zs = np.array([p.elevation_m for p in self.points])

        # Snap to grid origin at a round-number multiple of res to avoid
        # floating-point edge effects in the binning step.
        x0 = math.floor(xs.min() / res) * res
        y0 = math.floor(ys.min() / res) * res

        x_edges = np.arange(x0, xs.max() + res * 1.5, res)
        y_edges = np.arange(y0, ys.max() + res * 1.5, res)
        nx, ny  = len(x_edges) - 1, len(y_edges) - 1

        # Bin points into grid cells using ROUNDING (not truncation) so that
        # floating-point offsets of +/-e don't cause systematic index shifts.
        xi = np.clip(np.round((xs - x0) / res).astype(int), 0, nx - 1)
        yi = np.clip(np.round((ys - y0) / res).astype(int), 0, ny - 1)

        # Mean elevation per cell
        grid_sum   = np.zeros((ny, nx))
        grid_count = np.zeros((ny, nx), dtype=int)
        np.add.at(grid_sum,   (yi, xi), zs)
        np.add.at(grid_count, (yi, xi), 1)

        with np.errstate(invalid="ignore"):
            grid_elev = np.where(grid_count > 0,
                                 grid_sum / grid_count,
                                 np.nan)

        # ---- Baseline estimation (histogram peak) ------------------------
        # Find the elevation value where the most points cluster.
        # Robust to flight paths that spend a lot of time over craters:
        # the intact runway surface is the largest flat area so it always
        # produces the tallest histogram peak, regardless of how many
        # crater points are in the dataset.
        valid      = grid_elev[~np.isnan(grid_elev)]
        elev_range = float(valid.max() - valid.min())
        SLOPE_THRESHOLD_M = 0.30

        if elev_range > SLOPE_THRESHOLD_M:
            # Sloped runway: large median filter follows the grade locally.
            # Kernel diameter >> widest expected crater so the filter sees
            # mostly intact surface, not crater interior.
            kernel_cells = max(31, int(20.0 / res) | 1)   # must be odd
            filled   = _fill_nan_nearest(grid_elev)
            baseline = ndimage.median_filter(filled, size=kernel_cells,
                                             mode="nearest")
        else:
            # Flat runway: find the dominant peak in the elevation histogram.
            # 200 bins over the full range gives ~1-2 mm per bin at typical
            # LiDAR noise levels, which is more than fine enough.
            bin_count         = 200
            counts, bin_edges = np.histogram(valid, bins=bin_count)

            # Smooth slightly so sensor noise spikes don't beat the real peak.
            smoothed     = ndimage.gaussian_filter1d(counts.astype(float), sigma=1)
            peak_bin     = int(np.argmax(smoothed))
            baseline_val = float(bin_edges[peak_bin] + bin_edges[peak_bin + 1]) / 2.0
            baseline     = np.full_like(grid_elev, baseline_val)

        # NOTE: the next five lines are outside both if/else branches.
        # They must always run regardless of which baseline method was used.
        self._baseline = baseline
        depth_grid = np.where(
            ~np.isnan(grid_elev),
            baseline - grid_elev,
            np.nan,
        )
        self._grid_elev  = grid_elev
        self._depth_grid = depth_grid
        self._cx = x_edges[:-1] + res / 2.0   # cell-centre coordinates
        self._cy = y_edges[:-1] + res / 2.0

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyse(self) -> List[Crater]:
        """Detect all craters and return one Crater per crater found."""
        if self._grid_elev is None:
            self._build_grid()

        depth = self._depth_grid  # (ny, nx)  positive = below baseline

        # Raw binary mask: cells deeper than the threshold
        raw_mask = np.nan_to_num(depth) > self.depth_threshold_m

        # Morphological closing with 8-connectivity to bridge gaps in
        # sparse point clouds (e.g. 1 m point spacing on 1 m grid)
        struct      = ndimage.generate_binary_structure(2, 2)
        closed_mask = ndimage.binary_closing(raw_mask,
                                             structure=struct,
                                             iterations=self.closing_iters)

        # Label connected regions
        labeled, n_labels = ndimage.label(closed_mask, structure=struct)

        results: List[Crater] = []
        crater_id = 0

        for lv in range(1, n_labels + 1):
            blob_mask  = labeled == lv
            real_cells = int((blob_mask & raw_mask).sum())
            if real_cells < self.min_crater_cells:
                continue

            crater_id += 1

            # 1. Maximum depth
            max_depth = float(np.nanmax(
                np.where(blob_mask & ~np.isnan(depth), depth, 0.0)
            ))

            # 2. GPS coordinates - depth-weighted centroid
            gy, gx  = np.indices(blob_mask.shape)
            w       = np.where(blob_mask, np.nan_to_num(depth), 0.0)
            w_total = float(w.sum()) or 1.0
            cx_idx  = float((w * gx).sum() / w_total)
            cy_idx  = float((w * gy).sum() / w_total)

            cx_m = float(np.interp(cx_idx, np.arange(len(self._cx)), self._cx))
            cy_m = float(np.interp(cy_idx, np.arange(len(self._cy)), self._cy))
            c_lat, c_lon = xy_to_latlon(cx_m, cy_m, self.ref_lat, self.ref_lon)

            # 3. Parallel and perpendicular extents
            gy_pts = gy[blob_mask]
            gx_pts = gx[blob_mask]
            x_pts  = self._cx[gx_pts]
            y_pts  = self._cy[gy_pts]

            par_proj  = x_pts * self._par[0]  + y_pts * self._par[1]
            perp_proj = x_pts * self._perp[0] + y_pts * self._perp[1]

            dim_par  = float(par_proj.max()  - par_proj.min())
            dim_perp = float(perp_proj.max() - perp_proj.min())

            results.append(Crater(
                crater_id=f"crater {crater_id:03d}",
                ns_diameter_cm=round(dim_par  * 100, 1),
                ew_diameter_cm=round(dim_perp * 100, 1),
                max_depth_cm=round(max_depth  * 100, 1),
                latitude=c_lat,
                longitude=c_lon,
            ))

        return results


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _fill_nan_nearest(arr: np.ndarray) -> np.ndarray:
    """Fill NaN cells with the value of the nearest non-NaN neighbour."""
    mask = np.isnan(arr)
    if not mask.any():
        return arr.copy()
    indices = ndimage.distance_transform_edt(
        mask, return_distances=False, return_indices=True
    )
    return arr[tuple(indices)]


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_points_from_csv(filepath: str) -> List[ElevationPoint]:
    """
    Load elevation points from a CSV file.

    Expected columns (header row required):
      lat          - decimal degrees
      lon          - decimal degrees
      elevation_m  - metres  (if your source gives centimetres, divide by 100)
    """
    points = []
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(ElevationPoint(
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                elevation_m=float(row["elevation_m"]),
            ))
    print(f"Loaded {len(points):,} points from {filepath}")
    return points


# ---------------------------------------------------------------------------
# Synthetic test data generator
# ---------------------------------------------------------------------------

def make_synthetic_runway(
    origin_lat: float = 34.9000,
    origin_lon: float = -117.8000,
    runway_heading: float = 90.0,
    runway_length_m: float = 800.0,
    runway_width_m: float = 30.0,
    point_spacing_m: float = 1.0,
    surface_elevation_m: float = 695.0,
    noise_std_m: float = 0.3,
    seed: int = 42,
) -> List[ElevationPoint]:
    """
    Generate a flat synthetic runway elevation grid with two known craters.

    Crater definitions  (par, perp, radius, depth) - all in metres:
      A  - 200 m along runway, centred on runway,    r = 4 m, depth = 0.75 m
      B  - 600 m along runway, 5 m right of centre,  r = 3 m, depth = 0.55 m
    """
    cos_ref   = math.cos(math.radians(origin_lat))
    par_vec, perp_vec = runway_axes(runway_heading)

    CRATERS = [
        dict(par=200.0, perp=3.0, radius=4.0, depth=0.75, label="C"),
        dict(par=600.0, perp=5.0, radius=3.0, depth=0.55, label="D"),
    ]

    rng    = np.random.default_rng(seed)
    points: List[ElevationPoint] = []

    par_vals  = np.arange(0.0, runway_length_m  + 1e-9, point_spacing_m)
    perp_vals = np.arange(-runway_width_m / 2, runway_width_m / 2 + 1e-9,
                           point_spacing_m)

    for par in par_vals:
        for perp in perp_vals:
            east  = par * par_vec[0]  + perp * perp_vec[0]
            north = par * par_vec[1]  + perp * perp_vec[1]
            lat   = origin_lat + math.degrees(north / _R)
            lon   = origin_lon + math.degrees(east  / (_R * cos_ref))
            elev  = surface_elevation_m + rng.normal(0.0, noise_std_m)

            for c in CRATERS:
                d = math.hypot(par - c["par"], perp - c["perp"])
                if d < c["radius"]:
                    elev -= c["depth"] * (1.0 - (d / c["radius"]) ** 2)

            points.append(ElevationPoint(lat=lat, lon=lon, elevation_m=elev))

    print(f"Synthetic runway: {len(points):,} points | "
          f"{runway_length_m:.0f} m x {runway_width_m:.0f} m | "
          f"heading {runway_heading} deg")
    print("Planted craters (ground truth):")
    for c in CRATERS:
        print(f"  [{c['label']}] par={c['par']:.0f} m | perp={c['perp']:.0f} m | "
              f"r={c['radius']:.0f} m | depth={c['depth']:.2f} m")
    print()
    return points


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    RUNWAY_HEADING = 45.0   # <- update to match real runway

    # Swap these two lines depending on whether you are using real or synthetic data:
    points = load_points_from_csv(r"C:\Users\canfi\Downloads\Hackethon\scenario_B_points.csv")
    #points = make_synthetic_runway(runway_heading=RUNWAY_HEADING)

    analyzer = CraterAnalyzer(
        points=points,
        runway_heading=RUNWAY_HEADING,
        depth_threshold_m=0.10,
        min_crater_cells=9,
        grid_res_m=1.0,
        closing_iters=2,
    )

    print("Analysing ...\n")
    results = analyzer.analyse()

    # Report the runway surface elevation used as baseline
    baseline = analyzer._baseline
    if float(np.std(baseline)) < 0.001:
        # Flat runway - histogram found a single peak value
        print(f"  Runway surface elevation : {float(np.mean(baseline)):.4f} m "
              f"({float(np.mean(baseline)) * 100:.1f} cm)")
    else:
        # Sloped runway - median filter produced a varying surface
        print(f"  Runway surface elevation : {float(np.min(baseline)):.4f} m min, "
              f"{float(np.max(baseline)):.4f} m max  (sloped - median filter applied)")
    print()

    if not results:
        print("No craters detected.")
        return

    print(f"{'=' * 54}")
    print(f"  {len(results)} crater(s) detected")
    print(f"{'=' * 54}\n")

    # Detailed per-crater block
    for r in results:
        print(r)

    # Compact summary table
    header = (f"{'ID':>12}  {'Lat':>11}  {'Lon':>12}  "
              f"{'Depth cm':>9}  {'N-S cm':>7}  {'E-W cm':>7}")
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r.crater_id:>12}  {r.latitude:>11.6f}  {r.longitude:>12.6f}  "
              f"{r.max_depth_cm:>9.1f}  {r.ns_diameter_cm:>7.1f}  "
              f"{r.ew_diameter_cm:>7.1f}")


if __name__ == "__main__":
    main()