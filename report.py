"""BoM-style report template. Design stack uses hackathon defaults (see constants)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
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


# Single knob for the hackathon demo; adjust before generating a report.
ACTIVE_RUNWAY_REPAIR_TIER = RepairTier.TIER_2

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
        "_Stack math: geocell courses are 8 in each; cap uses 4 in (within 3-6 in rule); "
        "FRP thickness ignored in depth._",
        "",
    ]


@dataclass
class Crater:
    """One crater after sensor/analysis processing. Linear sensor inputs are centimeters."""

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
        "_Sensor linear inputs are centimeters; report uses inches. Areas in sq ft; volumes in cu ft._",
        "",
    ]
    lines += _repair_tier_banner(tier)

    sum_geo_agg = 0.0
    sum_agg_cap = 0.0
    sum_concrete = 0.0
    sum_mortar_bags = 0
    sum_fabric = 0.0
    sum_design_vol = 0.0

    for c in craters:
        mgrs = lat_lon_to_mgrs(c.latitude, c.longitude)
        ns_in = cm_to_inches(c.ns_diameter_cm)
        ew_in = cm_to_inches(c.ew_diameter_cm)
        depth_in = cm_to_inches(c.max_depth_cm)
        area_sq_ft = cut_surface_area_sq_ft(ns_in, ew_in)
        vol_nom = nominal_prism_volume_cu_ft(area_sq_ft, depth_in)
        des = design_excavation_stack(tier, depth_in, area_sq_ft)

        sum_geo_agg += des.geocell_aggregate_cu_ft
        sum_agg_cap += des.aggregate_cap_cu_ft
        sum_concrete += des.concrete_cap_cu_ft
        sum_mortar_bags += mortar_bags_needed(des.concrete_cap_cu_ft)
        sum_fabric += des.geotextile_sq_ft
        sum_design_vol += des.design_volume_cu_ft

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
            lines.append("- **FRP matting (FOD cover):** TBD units _(mat spec — separate function later)_")
        else:
            lines.append("- **FRP matting:** n/a")

        if c.image_path:
            lines.append(f"- **Image:** `{c.image_path}`")
        lines.append("")

    fabric_rolls = geotextile_rolls_needed(sum_fabric)
    lines += [
        "## Totals (all craters)",
        f"- **Crater count:** {len(craters)}",
        f"- **Runway tier:** {tier.name} ({int(tier)})",
        f"- **Geotextile fabric:** {fabric_rolls} rolls, {disp_ceil(sum_fabric)} sq ft",
        f"- **Aggregate (geocell + FLS caps):** {disp_ceil(sum_geo_agg + sum_agg_cap)} cu ft",
        (
            f"- **Rapid-set mortar:** {sum_mortar_bags} bags, {disp_ceil(sum_concrete)} cu ft"
        )
        if sum_concrete > 0
        else "- **Rapid-set mortar:** n/a (Tier 3)",
        f"- **Design excavated volume (sum):** {disp_ceil(sum_design_vol)} cu ft",
    ]
    if tier is RepairTier.TIER_1:
        lines.append("- **FRP matting:** TBD units")

    return "\n".join(lines)


if __name__ == "__main__":
    sample = [
        Crater("001", 800.0, 750.0, 120.0, 37.7962, -122.3942),
        Crater("002", 500.0, 500.0, 40.0, 37.7970, -122.3950, image_path=None),
    ]
    print(render_report(sample))
