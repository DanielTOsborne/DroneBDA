"""DD Form 2768 (AMR) — optional pre-fill from BoM run data.

Lives in ``Output Reporting/`` with ``report.py``. The blank PDF ships in-repo (unclassified public form). Filled output is written next to
the Markdown BoM using ``pypdf`` AcroForm updates.

Demo behavior:
- Block 11 (remarks): BoM / crater summary.
- Block 8 (cargo): narrative + dimensions / weights / totals derived from ``BomRollup``.
- Other blocks: optional ``amr_operator.txt`` (key=value) beside this file maps preset
  admin / itinerary / POC text into known AcroForm fields. Missing file → cargo + remarks only.
- Block 4a–4d (senior traveler) are copied from block 14a–14d (same person); set ``fourteenA``–``fourteenD`` only.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

_BLANK_PDF = Path(__file__).resolve().parent / "DD2768 AMR - Blank.pdf"
_OPERATOR_TXT = Path(__file__).resolve().parent / "amr_operator.txt"

_FIELD_REMARKS = "form1[0].P2[0].eleven[0]"
_REMARKS_MAX_CHARS = 12000

# AcroForm keys (from ``PdfReader.get_fields()`` on the blank).
_PRIORITY_FIELDS = (
    "form1[0].P1[0].one[0].one_priority1[0]",
    "form1[0].P1[0].one[0].one_priority2[0]",
    "form1[0].P1[0].one[0].one_priority3[0]",
)

# Logical keys in ``amr_operator.txt`` → full PDF field names (text fields).
_PROFILE_TEXT_ALIASES: dict[str, str] = {
    "twoA": "form1[0].P1[0].two_three[0].twoA[0]",
    "twoB": "form1[0].P1[0].two_three[0].twoB[0]",
    "threeA": "form1[0].P1[0].two_three[0].threeA[0]",
    "threeB": "form1[0].P1[0].two_three[0].threeB[0]",
    "six_leg1_A": "form1[0].P1[0].six[0].six_leg1_A[0]",
    "six_leg1_B": "form1[0].P1[0].six[0].six_leg1_B[0]",
    "six_leg1_C": "form1[0].P1[0].six[0].six_leg1_C[0]",
    "six_leg1_D": "form1[0].P1[0].six[0].six_leg1_D[0]",
    "six_leg2_A": "form1[0].P1[0].six[0].six_leg2_A[0]",
    "six_leg2_B": "form1[0].P1[0].six[0].six_leg2_B[0]",
    "six_leg2_C": "form1[0].P1[0].six[0].six_leg2_C[0]",
    "six_leg2_D": "form1[0].P1[0].six[0].six_leg2_D[0]",
    "six_leg3_A": "form1[0].P1[0].six[0].six_leg3_A[0]",
    "six_leg3_B": "form1[0].P1[0].six[0].six_leg3_B[0]",
    "six_leg3_C": "form1[0].P1[0].six[0].six_leg3_C[0]",
    "six_leg3_D": "form1[0].P1[0].six[0].six_leg3_D[0]",
    "seven_leg1": "form1[0].P1[0].seven[0].seven_leg1[0]",
    "seven_leg2": "form1[0].P1[0].seven[0].seven_leg2[0]",
    "seven_leg3": "form1[0].P1[0].seven[0].seven_leg3[0]",
    "seven_passengers": "form1[0].P1[0].seven[0].seven_passengers[0]",
    "seven_total": "form1[0].P1[0].seven[0].seven_total[0]",
    "nine_departure_A": "form1[0].P2[0].nine[0].nine_departure_A[0]",
    "nine_departure_B": "form1[0].P2[0].nine[0].nine_departure_B[0]",
    "nine_departure_C": "form1[0].P2[0].nine[0].nine_departure_C[0]",
    "nine_departure_D": "form1[0].P2[0].nine[0].nine_departure_D[0]",
    "nine_arrival_A": "form1[0].P2[0].nine[0].nine_arrival_A[0]",
    "nine_arrival_B": "form1[0].P2[0].nine[0].nine_arrival_B[0]",
    "nine_arrival_C": "form1[0].P2[0].nine[0].nine_arrival_C[0]",
    "nine_arrival_D": "form1[0].P2[0].nine[0].nine_arrival_D[0]",
    "tenA_line1": "form1[0].P2[0].ten[0].tenA_line1[0]",
    "tenB_line1": "form1[0].P2[0].ten[0].tenB_line1[0]",
    "tenC_line1": "form1[0].P2[0].ten[0].tenC_line1[0]",
    "tenD_line1": "form1[0].P2[0].ten[0].tenD_line1[0]",
    "twelveA": "form1[0].P2[0].twelve[0].twelveA[0]",
    "twelveB": "form1[0].P2[0].twelve[0].twelveB[0]",
    "twelveC": "form1[0].P2[0].twelve[0].twelveC[0]",
    "twelveD": "form1[0].P2[0].twelve[0].twelveD[0]",
    "twelveE": "form1[0].P2[0].twelve[0].twelveE[0]",
    "twelveG": "form1[0].P2[0].twelve[0].twelveG[0]",
    "twelveH": "form1[0].P2[0].twelve[0].twelveH[0]",
    "thirteenA": "form1[0].P2[0].thirteen[0].thirteenA[0]",
    "thirteenB": "form1[0].P2[0].thirteen[0].thirteenB[0]",
    "thirteenC": "form1[0].P2[0].thirteen[0].thirteenC[0]",
    "thirteenD": "form1[0].P2[0].thirteen[0].thirteenD[0]",
    "thirteenE": "form1[0].P2[0].thirteen[0].thirteenE[0]",
    "thirteenG": "form1[0].P2[0].thirteen[0].thirteenG[0]",
    "fourteenA": "form1[0].P2[0].fourteen[0].fourteenA[0]",
    "fourteenB": "form1[0].P2[0].fourteen[0].fourteenB[0]",
    "fourteenC": "form1[0].P2[0].fourteen[0].fourteenC[0]",
    "fourteenD": "form1[0].P2[0].fourteen[0].fourteenD[0]",
    "fourteenE": "form1[0].P2[0].fourteen[0].fourteenE[0]",
    "fourteenG": "form1[0].P2[0].fourteen[0].fourteenG[0]",
}

# Senior traveler block 4 = fourteen a–d (profile keys are lowercased on load).
_FOUR_ABCD_FROM_FOURTEEN: tuple[tuple[str, str], ...] = (
    ("fourteena", "form1[0].P1[0].four[0].fourA[0]"),
    ("fourteenb", "form1[0].P1[0].four[0].fourB[0]"),
    ("fourteenc", "form1[0].P1[0].four[0].fourC[0]"),
    ("fourteend", "form1[0].P1[0].four[0].fourD[0]"),
)

_FIELD_EIGHT_A = "form1[0].P1[0].eight[0].eightA[0]"
_FIELD_EIGHT_B = "form1[0].P1[0].eight[0].eightB[0]"
_FIELD_EIGHT_C = "form1[0].P1[0].eight[0].eightC[0]"
_FIELD_EIGHT_D = "form1[0].P1[0].eight[0].eightD[0]"
_FIELD_EIGHT_E = "form1[0].P1[0].eight[0].eightE[0]"
_FIELD_EIGHT_F = "form1[0].P1[0].eight[0].eightF[0]"

# Demo shipping constants (not certified logistics).
_MORTAR_LB_PER_BAG = 50.0
_AGGREGATE_LB_PER_CU_FT = 88.0
_FRP_FULL_PANEL_LB = 82.0
_FRP_HALF_PANEL_LB = 46.0
_FRP_FULL_SHIP_CU_FT = 6.0
_FRP_HALF_SHIP_CU_FT = 3.5
_GEOTEXTILE_ROLL_SHIP_LB = 125.0
_GEOTEXTILE_ROLL_SHIP_CU_FT = 11.0
_ANCHOR_LB_EACH = 0.35

# Block 8: keep text short so it fits the PDF layout (brevity, not hard validation).
_EIGHT_A_LINE_MAX = 50
_EIGHT_B_MAX = 30
_EIGHT_C_MAX = 25
_EIGHT_D_MAX = 25


def _clip_field(s: str, max_len: int) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    if max_len <= 3:
        return s[:max_len]
    return s[: max_len - 3].rstrip() + "..."


def _remarks_from_craters(craters: list[Any], tier: Any) -> str:
    """BoM-derived text for block 11 (remarks). Same crater list as the paired Markdown BoM."""
    from report import RepairTier as RT, lat_lon_to_mgrs

    name = tier.name if isinstance(tier, RT) else str(tier)
    lines = [
        "EXERCISE EXERCISE EXERCISE //  DroneBDA / airfield damage BoM attachment (Demo: not for official filing).",
        f"Runway repair tier: {name}",
        f"Crater count: {len(craters)}",
        "Crater MGRS:",
    ]
    for c in craters:
        mgrs = lat_lon_to_mgrs(c.latitude, c.longitude)
        lines.append(f"{c.crater_id}: {mgrs}")
    text = "\n".join(lines)
    return text[:_REMARKS_MAX_CHARS]


def _load_operator_profile(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip().lower()
        if not key:
            continue
        out[key] = v.strip()
    return out


def _priority_checkbox_updates(priority: str) -> dict[str, str]:
    """Blank PDF uses export state ``/1`` vs ``/Off`` for travel-priority radio group."""
    p = priority.strip()
    if p not in ("1", "2", "3"):
        return {}
    idx = int(p) - 1
    u: dict[str, str] = {}
    for i, fname in enumerate(_PRIORITY_FIELDS):
        u[fname] = "/1" if i == idx else "/Off"
    return u


def _profile_pdf_updates(profile: dict[str, str]) -> dict[str, str]:
    u: dict[str, str] = {}
    pr = profile.get("priority") or profile.get("one_priority")
    if pr:
        u.update(_priority_checkbox_updates(pr))

    for alias, fname in _PROFILE_TEXT_ALIASES.items():
        val = profile.get(alias.lower())
        if val:
            u[fname] = val

    for src_key, four_field in _FOUR_ABCD_FROM_FOURTEEN:
        val = profile.get(src_key)
        if val:
            u[four_field] = val
    return u


def _is_bom_rollup(obj: Any) -> bool:
    """True if ``obj`` looks like ``report.BomRollup`` (duck-type: ``py report.py`` uses ``__main__``)."""
    return hasattr(obj, "tier") and hasattr(obj, "sum_fabric") and hasattr(obj, "sum_mortar_bags")


def _repair_tier_num(tier: Any) -> int:
    """1–3 regardless of whether ``tier`` came from ``report`` or ``__main__`` (separate Enum classes)."""
    if isinstance(tier, int):
        return tier
    v = getattr(tier, "value", None)
    if v is not None:
        return int(v)
    return int(tier)


def _cargo_updates(rollup: Any) -> dict[str, str]:
    """Block 8 from ``BomRollup`` (imported lazily)."""
    from report import (
        CONCRETE_CAP_THICKNESS_IN,
        FRP_FULL_EW_IN,
        FRP_FULL_NS_IN,
        FRP_HALF_EW_IN,
        FRP_HALF_NS_IN,
        GEOTEXTILE_ROLL_SQ_FT,
        geotextile_rolls_needed,
    )

    if not _is_bom_rollup(rollup):
        return {}

    r = rollup
    rolls = geotextile_rolls_needed(r.sum_fabric)
    agg_cu = r.sum_geo_agg + r.sum_agg_cap
    tier_n = _repair_tier_num(r.tier)

    def _eight_a_line(body: str) -> str:
        return _clip_field(f"o {body}", _EIGHT_A_LINE_MAX)

    lines_a = [
        _eight_a_line("Matl est from BoM (illustrative NSN/demo SKU)"),
        _eight_a_line(
            f"Geotextile: {rolls} rl, ~{round(r.sum_fabric)} sf plan"
        ),
        _eight_a_line(f"Aggregate cls II/III: ~{round(agg_cu)} cf"),
    ]
    if r.sum_mortar_bags:
        lines_a.append(
            _eight_a_line(f"R/S mortar: {r.sum_mortar_bags} bg @ {CONCRETE_CAP_THICKNESS_IN:.0f}in cap")
        )
    if tier_n == 1 and (r.sum_frp_full or r.sum_frp_half):
        lines_a.append(
            _eight_a_line(
                f"FRP: {r.sum_frp_full}F/{r.sum_frp_half}H; anc {r.sum_anchor_full}F/{r.sum_anchor_half}H"
            )
        )
    elif tier_n != 1:
        lines_a.append(_eight_a_line("FRP: n/a (tier)"))

    eight_a = "\n".join(lines_a)

    # 8b — largest item dimensions only: ##x##x## in (no EW/NS labels).
    roll_lwh = (144, 48, 48)
    if r.sum_frp_full:
        frp_lwh = (int(FRP_FULL_EW_IN), int(FRP_FULL_NS_IN), 3)
    elif r.sum_frp_half:
        frp_lwh = (int(FRP_HALF_EW_IN), int(FRP_HALF_NS_IN), 3)
    else:
        frp_lwh = (int(FRP_FULL_EW_IN), int(FRP_FULL_NS_IN), 3)
    if tier_n == 1 and (r.sum_frp_full or r.sum_frp_half):
        eight_b = _clip_field(f"{frp_lwh[0]}x{frp_lwh[1]}x{frp_lwh[2]} in", _EIGHT_B_MAX)
    elif rolls:
        eight_b = _clip_field(f"{roll_lwh[0]}x{roll_lwh[1]}x{roll_lwh[2]} in", _EIGHT_B_MAX)
    else:
        eight_b = _clip_field("bulk agg / line haul", _EIGHT_B_MAX)

    frp_heavy_lb = _FRP_FULL_PANEL_LB if (tier_n == 1 and r.sum_frp_full) else (
        _FRP_HALF_PANEL_LB if (tier_n == 1 and r.sum_frp_half) else 0.0
    )
    one_roll_lb = _GEOTEXTILE_ROLL_SHIP_LB if rolls else 0.0
    one_bag_lb = _MORTAR_LB_PER_BAG if r.sum_mortar_bags else 0.0

    roll_dim_s = f"{roll_lwh[0]}x{roll_lwh[1]}x{roll_lwh[2]}in"
    frp_dim_s = f"{frp_lwh[0]}x{frp_lwh[1]}x{frp_lwh[2]}in"
    frp_piece_lb = _FRP_FULL_PANEL_LB if (tier_n == 1 and r.sum_frp_full) else _FRP_HALF_PANEL_LB

    if one_roll_lb >= frp_heavy_lb and one_roll_lb >= one_bag_lb and rolls:
        eight_c = _clip_field(f"{roll_dim_s} {one_roll_lb:.0f}lb", _EIGHT_C_MAX)
    elif frp_heavy_lb >= one_bag_lb and (r.sum_frp_full or r.sum_frp_half):
        eight_c = _clip_field(f"{frp_dim_s} {frp_piece_lb:.0f}lb", _EIGHT_C_MAX)
    elif r.sum_mortar_bags:
        eight_c = _clip_field(f"50lb bag x{r.sum_mortar_bags}", _EIGHT_C_MAX)
    else:
        eight_c = _clip_field("bulk agg max pc", _EIGHT_C_MAX)

    mortar_lb = _MORTAR_LB_PER_BAG * r.sum_mortar_bags
    agg_lb = _AGGREGATE_LB_PER_CU_FT * agg_cu
    frp_lb = _FRP_FULL_PANEL_LB * r.sum_frp_full + _FRP_HALF_PANEL_LB * r.sum_frp_half
    roll_lb_tot = _GEOTEXTILE_ROLL_SHIP_LB * rolls
    anchor_lb = _ANCHOR_LB_EACH * (r.sum_anchor_full + r.sum_anchor_half)
    total_lb = mortar_lb + agg_lb + frp_lb + roll_lb_tot + anchor_lb
    if total_lb >= 10_000:
        eight_d = _clip_field(f"~{total_lb / 1000:.1f}k lb", _EIGHT_D_MAX)
    else:
        eight_d = _clip_field(f"~{total_lb:.0f} lb", _EIGHT_D_MAX)

    bulk_cu = r.sum_concrete + agg_cu
    frp_ship_cu = _FRP_FULL_SHIP_CU_FT * r.sum_frp_full + _FRP_HALF_SHIP_CU_FT * r.sum_frp_half
    roll_cu = _GEOTEXTILE_ROLL_SHIP_CU_FT * rolls
    total_cu = bulk_cu + frp_ship_cu + roll_cu
    eight_e = _clip_field(f"~{total_cu:.0f} cf tot est", 40)

    eight_f = _clip_field(
        "FOD-sensitive; forklift/K-loader/D6L; keep dry.", 80
    )

    return {
        _FIELD_EIGHT_A: eight_a,
        _FIELD_EIGHT_B: eight_b,
        _FIELD_EIGHT_C: eight_c,
        _FIELD_EIGHT_D: eight_d,
        _FIELD_EIGHT_E: eight_e,
        _FIELD_EIGHT_F: eight_f,
    }


def write_prefilled_dd2768(
    markdown_sidecar: Path,
    craters: list[Any],
    tier: Any,
    rollup: Any | None = None,
) -> Path | None:
    """
    Copy the blank DD 2768, pre-fill known fields, write ``<stem>_DD2768.pdf`` beside the
    Markdown sidecar. Returns the PDF path, or ``None`` if the blank template is missing.
    """
    if not _BLANK_PDF.is_file():
        warnings.warn(f"AMR blank PDF not found at {_BLANK_PDF}; skip AMR export.")
        return None

    from report import compute_bom_rollup

    r_up = rollup if rollup is not None else compute_bom_rollup(craters, tier)

    remarks = _remarks_from_craters(craters, tier)
    updates: dict[str, str | None] = {_FIELD_REMARKS: remarks}
    updates.update(_cargo_updates(r_up))

    profile = _load_operator_profile(_OPERATOR_TXT)
    if profile:
        updates.update(_profile_pdf_updates(profile))

    # Block 11 must always reflect this run's crater list (never overridden by profile keys).
    updates[_FIELD_REMARKS] = remarks

    reader = PdfReader(_BLANK_PDF)
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, updates)

    pdf_out = markdown_sidecar.with_name(f"{markdown_sidecar.stem}_DD2768.pdf")
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    writer.write(pdf_out)
    return pdf_out
