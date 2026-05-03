"""BoM-style report template. Design stack uses hackathon defaults (see constants).

Run from repo root: ``py "Output Reporting/report.py"`` (or ``cd`` here then ``py report.py``).
Generated Markdown and DD2768 PDF land in ``Output Reporting/Reports/``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Optional

import mgrs

_mgrs = mgrs.MGRS()


def lat_lon_to_mgrs(latitude: float, longitude: float) -> str:
    """WGS84 decimal degrees -> spaced MGRS string."""
    loc = _mgrs.toMGRS(latitude, longitude)
    tail = loc[5:]
    n = len(tail)
    if n % 2:
        raise ValueError(f"MGRS tail must have even length, got {n}: {loc!r}")
    h = n // 2
    return f"{loc[:3]} {loc[3:5]} {tail[:h]} {tail[h:]}"


class RepairTier(IntEnum):
    """Project-wide runway / repair mode (not per-crater). Change the active constant below."""

    TIER_1 = 1  # paved, fighter: FRP on rapid-set concrete; aggregate in geocells below
    TIER_2 = 2  # paved, cargo: rapid-set concrete cap; aggregate in geocells below
    TIER_3 = 3  # FLS: 3-6 in aggregate cap; aggregate in geocells below; no concrete cap


class ReportOutputMode(IntEnum):
    """Where to persist Markdown (PC vs Raspberry Pi on the drone, often SD-backed)."""

    FILESYSTEM = 0  # e.g. ``Output Reporting/Reports/`` on this machine or SD mounted as a drive
    EDGE_DEVICE = 1  # Pi on drone; real SD/path I/O on device (stub here on dev PC)


# Single knob for the hackathon demo; adjust before generating a report.
ACTIVE_RUNWAY_REPAIR_TIER = RepairTier.TIER_1

# Report persistence: PC output folder vs Pi edge stub (flip when running on the drone).
ACTIVE_REPORT_OUTPUT_MODE = ReportOutputMode.FILESYSTEM

# When True (and ``FILESYSTEM`` output), also write a pre-filled DD Form 2768 PDF next to the .md.
ACTIVE_AMR_PREFILL = True

# Markdown + AMR PDF output folder (sibling ``Reports/`` under ``Output Reporting/``).
_REPORTING_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = str(_REPORTING_ROOT / "Reports")

# Stacking / thickness (first-pass design — all caps must stay within 3-6 in).
GEOCELL_LAYER_HEIGHT_IN = 8.0
CONCRETE_CAP_THICKNESS_IN = 4.0  # Tier 1 & 2; must be in [3, 6]
TIER3_AGGREGATE_CAP_THICKNESS_IN = 4.0  # Tier 3 top; must be in [3, 6]
# FRP sits on concrete; treat thickness as negligible for vertical stack math.
#
# Design assumptions (locked for this prototype):
# - 4 in cap always (mortar T1/T2, aggregate T3). If a hole needs a thicker cap,
#   RADR is not the right tool anyway.
# - Geocell aggregate volume uses full footprint x height; cell-wall material is thin
#   enough that error is negligible for BoM scale.
# - Geotextile (N+1) x footprint is nominal; fabric is light/cheap—having extra on
#   hand for field preference is acceptable.
# - Rapid-set mortar: order in **bags** (0.4 cu ft placed per bag, rounded up per crater).

_CM_PER_IN = 2.54
MORTAR_PLACED_CU_FT_PER_BAG = 0.4  # placed yield; bag unit for waste handling
# Geotextile ordering (totals section only); per-crater stays sq ft.
GEOTEXTILE_ROLL_SQ_FT = 12 * 150  # 12 ft x 150 ft = 1800 sq ft per roll
_SQ_IN_PER_SQ_FT = 144.0

# FRP (Tier 1 only). Runway = North–South. Short edge along runway (NS), long edge across (EW).
# Nominal mats: full 208 x 78 in (EW x NS), half 108 x 78 in; 8 in overlap between neighbors
# (half width 108 vs 104). Net coverage for area estimates: 200 x 70 in per full, 100 x 70 per half.
FRP_FULL_EW_IN = 208.0
FRP_FULL_NS_IN = 78.0
FRP_HALF_EW_IN = 108.0
FRP_HALF_NS_IN = 78.0
FRP_CRATER_MARGIN_EACH_SIDE_IN = 6.0  # coverage must extend past crater cut EW and NS
FRP_EFFECTIVE_FULL_EW_IN = 200.0
FRP_EFFECTIVE_FULL_NS_IN = 70.0
FRP_EFFECTIVE_HALF_EW_IN = 100.0
FRP_EFFECTIVE_HALF_NS_IN = 70.0
# Anchors on lead/trail edges only (200 x 24 full, 100 x 24 half); brick mirrors 200/100 EW like mats.
FRP_ANCHOR_FULL_EW_IN = 200.0
FRP_ANCHOR_HALF_EW_IN = 100.0
FRP_ANCHOR_NS_IN = 24.0


def cm_to_inches(cm: float) -> float:
    """Sensor centimeters -> report inches."""
    return cm / _CM_PER_IN


def cut_surface_area_sq_ft(ns_diameter_in: float, ew_diameter_in: float) -> float:
    """Rectangular cut plan, square to runway: NS x EW, result in square feet."""
    area_sq_in = ns_diameter_in * ew_diameter_in
    return area_sq_in / _SQ_IN_PER_SQ_FT


def nominal_prism_volume_cu_ft(surface_sq_ft: float, depth_in: float) -> float:
    """Flat-bottom box: surface area x depth (depth inches -> feet)."""
    depth_ft = depth_in / 12.0
    return surface_sq_ft * depth_ft


def disp_ceil(x: float) -> int:
    """Smallest integer >= x — for report text only (calculations stay float)."""
    return int(math.ceil(x))


def mortar_bags_needed(placed_cu_ft: float) -> int:
    """Bags to order for one pour/placement (whole bags)."""
    if placed_cu_ft <= 0:
        return 0
    return math.ceil(placed_cu_ft / MORTAR_PLACED_CU_FT_PER_BAG)


def geotextile_rolls_needed(total_sq_ft: float) -> int:
    """Whole rolls from total plan-area sq ft (totals rollup)."""
    if total_sq_ft <= 0:
        return 0
    return math.ceil(total_sq_ft / GEOTEXTILE_ROLL_SQ_FT)


@dataclass(frozen=True)
class FRPMatPlan:
    """Tier 1 FRP over crater (inflated coverage), brick pattern; anchors on lead/trail edges."""

    cover_ns_in: float
    cover_ew_in: float
    n_courses_ns: int
    max_full_panels_across_ew: int
    full_panels: int
    half_panels: int
    anchor_full: int
    anchor_half: int
    approx_net_coverage_sq_ft: float


def _frp_row_full_half_across_ew(w_ew: float, odd_course: bool) -> tuple[int, int]:
    """One course across EW: (full_count, half_count) for mats (208 / 108 brick)."""
    if odd_course:
        interior = w_ew - 2 * FRP_HALF_EW_IN
        if interior <= 0:
            return 0, 2
        return math.ceil(interior / FRP_FULL_EW_IN), 2
    return math.ceil(w_ew / FRP_FULL_EW_IN), 0


def _frp_anchor_edge_full_half(w_ew: float, odd_course: bool) -> tuple[int, int]:
    """Anchor line on one lead or trail edge; 200 / 100 EW brick matching mat row parity."""
    if odd_course:
        interior = w_ew - 2 * FRP_ANCHOR_HALF_EW_IN
        if interior <= 0:
            return 0, 2
        return math.ceil(interior / FRP_ANCHOR_FULL_EW_IN), 2
    return math.ceil(w_ew / FRP_ANCHOR_FULL_EW_IN), 0


def frp_mat_plan(ns_cut_in: float, ew_cut_in: float) -> FRPMatPlan:
    """
    Mats: inflate cut by FRP_CRATER_MARGIN_EACH_SIDE_IN on each side (NS and EW), then
    brick-lay nominal mats. Anchors: full/half counts for lead and trail edges (first and
    last NS course only), same odd/even pattern as the mat row they attach to.
    """
    if ns_cut_in <= 0 or ew_cut_in <= 0:
        return FRPMatPlan(0.0, 0.0, 0, 0, 0, 0, 0, 0, 0.0)

    m = FRP_CRATER_MARGIN_EACH_SIDE_IN
    cover_ns = float(ns_cut_in) + 2 * m
    cover_ew = float(ew_cut_in) + 2 * m
    n_courses = math.ceil(cover_ns / FRP_FULL_NS_IN)
    max_across = math.ceil(cover_ew / FRP_FULL_EW_IN)

    total_full = 0
    total_half = 0
    for course in range(n_courses):
        f, h = _frp_row_full_half_across_ew(cover_ew, course % 2 == 1)
        total_full += f
        total_half += h

    af_s, ah_s = _frp_anchor_edge_full_half(cover_ew, 0 % 2 == 1)
    if n_courses == 1:
        anchor_full, anchor_half = 2 * af_s, 2 * ah_s
    else:
        af_n, ah_n = _frp_anchor_edge_full_half(cover_ew, (n_courses - 1) % 2 == 1)
        anchor_full, anchor_half = af_s + af_n, ah_s + ah_n

    net_sq_in = total_full * (FRP_EFFECTIVE_FULL_EW_IN * FRP_EFFECTIVE_FULL_NS_IN)
    net_sq_in += total_half * (FRP_EFFECTIVE_HALF_EW_IN * FRP_EFFECTIVE_HALF_NS_IN)
    approx_sq_ft = net_sq_in / _SQ_IN_PER_SQ_FT

    return FRPMatPlan(
        cover_ns_in=cover_ns,
        cover_ew_in=cover_ew,
        n_courses_ns=n_courses,
        max_full_panels_across_ew=max_across,
        full_panels=total_full,
        half_panels=total_half,
        anchor_full=anchor_full,
        anchor_half=anchor_half,
        approx_net_coverage_sq_ft=approx_sq_ft,
    )


@dataclass(frozen=True)
class ExcavationDesign:
    """Vertical stack: N geocell courses (8 in each) + tier cap; depth rounded up to fit."""

    n_geocell_layers: int
    cap_thickness_in: float
    design_depth_in: float
    overcut_in: float
    design_volume_cu_ft: float
    geocell_aggregate_cu_ft: float
    aggregate_cap_cu_ft: float
    concrete_cap_cu_ft: float
    geotextile_sq_ft: float


def design_excavation_stack(
    tier: RepairTier,
    measured_depth_in: float,
    area_sq_ft: float,
) -> ExcavationDesign:
    """
    First-pass stack model (philosophy you described):

    - Cap thickness: fixed nominal 4 in within your 3-6 in band (Tier 1/2 = rapid-set
      mortar flush with paved surface; Tier 3 = compacted aggregate cap only).
    - Geocell courses: each 8 in tall; count N is the smallest non-negative integer such
      that design depth D = N*8 + cap >= measured depth (over-excavation if needed).
    - Geotextile: (N + 1) plan-size sheets at full footprint — bottom, between courses
      (one sheet serves the interface above layer k and below layer k+1), and top of
      the geocell stack before the cap.
    - Volumes: footprint x height prisms (full-area aggregate in geocells; refine later
      for cell-wall void fraction if needed).
    """
    if tier in (RepairTier.TIER_1, RepairTier.TIER_2):
        cap_in = CONCRETE_CAP_THICKNESS_IN
        concrete_cu_ft = area_sq_ft * (cap_in / 12.0)
        agg_cap_cu_ft = 0.0
    else:
        cap_in = TIER3_AGGREGATE_CAP_THICKNESS_IN
        concrete_cu_ft = 0.0
        agg_cap_cu_ft = area_sq_ft * (cap_in / 12.0)

    rem = measured_depth_in - cap_in
    if rem <= 0:
        n = 0
    else:
        n = math.ceil(rem / GEOCELL_LAYER_HEIGHT_IN)

    design_depth_in = n * GEOCELL_LAYER_HEIGHT_IN + cap_in
    overcut_in = design_depth_in - measured_depth_in

    geo_height_in = n * GEOCELL_LAYER_HEIGHT_IN
    geocell_aggregate_cu_ft = area_sq_ft * (geo_height_in / 12.0)
    design_volume_cu_ft = area_sq_ft * (design_depth_in / 12.0)

    iface = n + 1
    geotextile_sq_ft = iface * area_sq_ft

    return ExcavationDesign(
        n_geocell_layers=n,
        cap_thickness_in=cap_in,
        design_depth_in=design_depth_in,
        overcut_in=overcut_in,
        design_volume_cu_ft=design_volume_cu_ft,
        geocell_aggregate_cu_ft=geocell_aggregate_cu_ft,
        aggregate_cap_cu_ft=agg_cap_cu_ft,
        concrete_cap_cu_ft=concrete_cu_ft,
        geotextile_sq_ft=geotextile_sq_ft,
    )


def _repair_tier_banner(tier: RepairTier) -> list[str]:
    if tier is RepairTier.TIER_1:
        body = (
            "**Tier 1** - Paved / improved, **fighter**: **FRP** on top of **rapid-set mortar "
            "(concrete)** flush with surface; below that, **aggregate in geocell frames** "
            "to the excavation floor."
        )
    elif tier is RepairTier.TIER_2:
        body = (
            "**Tier 2** - Paved / improved, **cargo**: **rapid-set mortar (concrete)** cap "
            "flush with surface; below that, **aggregate in geocell frames** to the floor. "
            "**No FRP** in this tier."
        )
    else:
        body = (
            "**Tier 3** - **FLS**: top **3-6 in compacted aggregate** (nominal 4 in here); "
            "below that, **aggregate in geocell frames**; **no** concrete cap or FRP."
        )
    return [
        "## Runway repair tier (project-wide)",
        "",
        body,
        "",
        "_Stack math: geocell courses are 8 in each; cap uses 4 in; "
        "FRP thickness ignored in depth. FRP: runway NS, mat brick pattern, +6 in margin "
        "each side on cut; anchors lead/trail edge only._",
        "",
    ]


@dataclass(frozen=True)
class BomRollup:
    """Aggregated BoM quantities across all craters (for AMR cargo / totals)."""

    tier: RepairTier
    sum_geo_agg: float
    sum_agg_cap: float
    sum_concrete: float
    sum_mortar_bags: int
    sum_fabric: float
    sum_design_vol: float
    sum_frp_full: int
    sum_frp_half: int
    sum_anchor_full: int
    sum_anchor_half: int


def compute_bom_rollup(craters: list["Crater"], tier: RepairTier | None = None) -> BomRollup:
    """Single pass of the same stack math as ``render_report`` totals (for AMR / exports)."""
    tr = ACTIVE_RUNWAY_REPAIR_TIER if tier is None else tier
    sum_geo_agg = 0.0
    sum_agg_cap = 0.0
    sum_concrete = 0.0
    sum_mortar_bags = 0
    sum_fabric = 0.0
    sum_design_vol = 0.0
    sum_frp_full = 0
    sum_frp_half = 0
    sum_anchor_full = 0
    sum_anchor_half = 0

    for c in craters:
        ns_in = cm_to_inches(c.ns_diameter_cm)
        ew_in = cm_to_inches(c.ew_diameter_cm)
        depth_in = cm_to_inches(c.max_depth_cm)
        area_sq_ft = cut_surface_area_sq_ft(ns_in, ew_in)
        des = design_excavation_stack(tr, depth_in, area_sq_ft)
        sum_geo_agg += des.geocell_aggregate_cu_ft
        sum_agg_cap += des.aggregate_cap_cu_ft
        sum_concrete += des.concrete_cap_cu_ft
        sum_mortar_bags += mortar_bags_needed(des.concrete_cap_cu_ft)
        sum_fabric += des.geotextile_sq_ft
        sum_design_vol += des.design_volume_cu_ft
        if tr is RepairTier.TIER_1:
            frp = frp_mat_plan(ns_in, ew_in)
            sum_frp_full += frp.full_panels
            sum_frp_half += frp.half_panels
            sum_anchor_full += frp.anchor_full
            sum_anchor_half += frp.anchor_half

    return BomRollup(
        tier=tr,
        sum_geo_agg=sum_geo_agg,
        sum_agg_cap=sum_agg_cap,
        sum_concrete=sum_concrete,
        sum_mortar_bags=sum_mortar_bags,
        sum_fabric=sum_fabric,
        sum_design_vol=sum_design_vol,
        sum_frp_full=sum_frp_full,
        sum_frp_half=sum_frp_half,
        sum_anchor_full=sum_anchor_full,
        sum_anchor_half=sum_anchor_half,
    )


@dataclass
class Crater:

    crater_id: str
    ns_diameter_cm: float
    ew_diameter_cm: float
    max_depth_cm: float
    latitude: float
    longitude: float
    image_path: Optional[str] = None


def render_report(craters: list[Crater], tier: RepairTier | None = None) -> str:
    """Return markdown text: per-crater blocks + totals."""
    tier = ACTIVE_RUNWAY_REPAIR_TIER if tier is None else tier

    lines: list[str] = [
        "# Airfield damage - bill of materials (draft)",
        "",
    ]
    lines += _repair_tier_banner(tier)

    rollup = compute_bom_rollup(craters, tier)

    for c in craters:
        mgrs = lat_lon_to_mgrs(c.latitude, c.longitude)
        ns_in = cm_to_inches(c.ns_diameter_cm)
        ew_in = cm_to_inches(c.ew_diameter_cm)
        depth_in = cm_to_inches(c.max_depth_cm)
        area_sq_ft = cut_surface_area_sq_ft(ns_in, ew_in)
        vol_nom = nominal_prism_volume_cu_ft(area_sq_ft, depth_in)
        des = design_excavation_stack(tier, depth_in, area_sq_ft)

        total_agg_cu_ft = des.geocell_aggregate_cu_ft + des.aggregate_cap_cu_ft

        lines += [
            f"## Crater {c.crater_id}",
            f"- **MGRS:** {mgrs}",
            f"- **NS diameter:** {disp_ceil(ns_in)} in _(sensor {disp_ceil(c.ns_diameter_cm)} cm)_",
            f"- **EW diameter:** {disp_ceil(ew_in)} in _(sensor {disp_ceil(c.ew_diameter_cm)} cm)_",
            f"- **Max depth (measured):** {depth_in:.1f} in _(sensor {c.max_depth_cm:.1f} cm)_",
            f"- **Cut plan surface area:** {disp_ceil(area_sq_ft)} sq ft (NS x EW, rectangular flat bottom)",
            f"- **Nominal prism volume (measured depth):** {disp_ceil(vol_nom)} cu ft",
            f"- **Design excavation depth:** {disp_ceil(des.design_depth_in)} in "
            f"_(measured {depth_in:.1f} in; over-cut {disp_ceil(des.overcut_in):+d} in)_",
            f"- **Design excavated volume:** {disp_ceil(des.design_volume_cu_ft)} cu ft",
            f"- **Geocell layers (8 in each):** {des.n_geocell_layers}",
            f"- **Geotextile fabric:** {disp_ceil(des.geotextile_sq_ft)} sq ft",
            f"- **Aggregate (geocell fill + any FLS cap):** {disp_ceil(total_agg_cu_ft)} cu ft",
        ]

        if tier in (RepairTier.TIER_1, RepairTier.TIER_2):
            bags = mortar_bags_needed(des.concrete_cap_cu_ft)
            lines.append(
                f"- **Rapid-set mortar (concrete cap, {disp_ceil(CONCRETE_CAP_THICKNESS_IN)} in nominal):** "
                f"{bags} bags, {disp_ceil(des.concrete_cap_cu_ft)} cu ft"
            )
        else:
            lines.append(
                f"- **Rapid-set mortar (concrete cap):** n/a (Tier 3 — cap is aggregate only)"
            )

        if tier is RepairTier.TIER_1:
            frp = frp_mat_plan(ns_in, ew_in)
            lines.append(
                f"- **FRP assembly layout:** {frp.n_courses_ns} rows NS, "
                f"{frp.max_full_panels_across_ew} panels across EW"
            )
            lines.append(
                f"- **FRP matting (FOD cover):** {frp.full_panels} full panels (208 x 78 in), "
                f"{frp.half_panels} half panels (108 x 78 in)"
            )
            lines.append(
                f"- **FRP net coverage (approx.):** {disp_ceil(frp.approx_net_coverage_sq_ft)} sq ft "
                f"_(200 x 70 in per full, 100 x 70 in per half equivalent)_"
            )
            lines.append(
                f"- **FRP anchors (lead/trail edges):** {frp.anchor_full} full (200 x {int(FRP_ANCHOR_NS_IN)} in), "
                f"{frp.anchor_half} half (100 x {int(FRP_ANCHOR_NS_IN)} in)"
            )
        else:
            lines.append("- **FRP matting:** n/a")

        if c.image_path:
            lines.append(f"- **Image:** `{c.image_path}`")
        lines.append("")

    fabric_rolls = geotextile_rolls_needed(rollup.sum_fabric)
    agg_total = rollup.sum_geo_agg + rollup.sum_agg_cap
    lines += [
        "## Totals (all craters)",
        f"- **Crater count:** {len(craters)}",
        f"- **Geotextile fabric:** {fabric_rolls} rolls, {disp_ceil(rollup.sum_fabric)} sq ft",
        f"- **Aggregate (geocell + FLS caps):** {disp_ceil(agg_total)} cu ft",
        (
            f"- **Rapid-set mortar:** {rollup.sum_mortar_bags} bags, {disp_ceil(rollup.sum_concrete)} cu ft"
        )
        if rollup.sum_concrete > 0
        else "- **Rapid-set mortar:** n/a (Tier 3)",
        f"- **Design excavated volume (sum):** {disp_ceil(rollup.sum_design_vol)} cu ft",
    ]
    if tier is RepairTier.TIER_1:
        lines.append(
            f"- **FRP matting:** {rollup.sum_frp_full} full panels, {rollup.sum_frp_half} half panels"
        )
        lines.append(
            f"- **FRP anchors (lead/trail edges):** {rollup.sum_anchor_full} full, {rollup.sum_anchor_half} half"
        )

    return "\n".join(lines)


def default_report_markdown_path(when: datetime | None = None) -> Path:
    """``Reports/bom_YYYY-MM-DD_HHMMSS.md`` under this module (short timestamp, unique per second)."""
    stamp = (when or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    return Path(REPORTS_DIR) / f"bom_{stamp}.md"


def default_report_markdown_filename(when: datetime | None = None) -> str:
    """Filename only (for edge-device / SD naming)."""
    return default_report_markdown_path(when).name


def _edge_device_report_stub(markdown: str, filename: str) -> None:
    """Placeholder for Raspberry Pi SD write; replace with on-device path (e.g. ``open`` on mount)."""
    n_bytes = len(markdown.encode("utf-8"))
    print(f"[EDGE_DEVICE / Pi stub] would write {n_bytes} UTF-8 bytes to SD as {filename!r}")


def write_report_markdown(
    craters: list[Crater],
    path: str | Path | None = None,
    tier: RepairTier | None = None,
    output_mode: ReportOutputMode | None = None,
) -> Path | None:
    """
    Persist BoM markdown.

    ``FILESYSTEM``: UTF-8 file under the module's ``Reports/`` folder (default path) or ``path`` if given.
    ``EDGE_DEVICE``: no host file; call stub (future: SD or mount on the Pi). Returns ``None``.
    """
    text = render_report(craters, tier)
    mode = ACTIVE_REPORT_OUTPUT_MODE if output_mode is None else output_mode
    if mode == ReportOutputMode.EDGE_DEVICE:
        name = Path(path).name if path is not None else default_report_markdown_filename()
        _edge_device_report_stub(text, name)
        return None
    out = Path(path) if path is not None else default_report_markdown_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")

    if ACTIVE_AMR_PREFILL:
        import warnings

        import amr

        tr = ACTIVE_RUNWAY_REPAIR_TIER if tier is None else tier
        rollup = compute_bom_rollup(craters, tr)
        try:
            amr_pdf = amr.write_prefilled_dd2768(out, craters, tr, rollup)
            if amr_pdf is None:
                warnings.warn("AMR export skipped (blank DD2768 PDF missing).")
        except Exception as exc:
            warnings.warn(f"AMR export failed: {exc}")

    return out


if __name__ == "__main__":
    sample = [
        Crater("001", 193.0, 176.5, 70.0, 37.7962, -122.3942),
        Crater("002", 170.2, 167.6, 73.7, 37.7970, -122.3950, image_path=None),
    ]
    out = render_report(sample)
    print(out)
    written = write_report_markdown(sample)
    if written is not None:
        print(f"\nWrote {written.as_posix()}")
        amr_pdf = written.with_name(f"{written.stem}_DD2768.pdf")
        if amr_pdf.is_file():
            print(f"Wrote {amr_pdf.as_posix()}")
    else:
        print("\nReport output mode: EDGE_DEVICE (no file on this host; see stub line above).")
