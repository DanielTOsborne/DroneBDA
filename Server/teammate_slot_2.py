"""Reserved route for teammate functionality."""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("teammate_slot_2", __name__, url_prefix="/slot2")


@bp.route("/")
def index():
    return render_template("teammate_slot.html", slot_title="TBD", slot_number=2)
