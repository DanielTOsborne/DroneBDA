"""Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, render_template

from Server.clear_reports import bp as clear_reports_bp
from Server.filesystem import bp as filesystem_bp
from Server.reports import bp as reports_bp
from Server.start_bda import bp as start_bda_bp
from Server.system_state import ensure_default_state_file, reset_to_standby_preserving_restart
from Server.teammate_slot_2 import bp as slot2_bp
from Server.test_report import bp as test_report_bp


def create_app() -> Flask:
    here = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(here / "templates"),
        static_folder=str(here / "static"),
    )
    # Needed for ``flash()`` after BoM generation (override in production).
    app.secret_key = os.environ.get("DRONEBDA_FLASK_SECRET", "dronebda-demo-not-for-production")

    ensure_default_state_file()

    app.register_blueprint(reports_bp)
    app.register_blueprint(start_bda_bp)
    app.register_blueprint(slot2_bp)
    app.register_blueprint(test_report_bp)
    app.register_blueprint(clear_reports_bp)
    app.register_blueprint(filesystem_bp)

    @app.route("/")
    def home():
        reset_to_standby_preserving_restart()
        return render_template("home.html")

    @app.route("/__dronebda_ping")
    def dronebda_ping():
        """Plain-text probe so you can tell this Flask app owns the port (vs stray servers on :8000)."""
        return "DroneBDA hub OK\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    return app
