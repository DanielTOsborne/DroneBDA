"""Flask application factory."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template

from Server.clear_reports import bp as clear_reports_bp
from Server.filesystem import bp as filesystem_bp
from Server.reports import bp as reports_bp
from Server.teammate_slot_1 import bp as slot1_bp
from Server.teammate_slot_2 import bp as slot2_bp
from Server.test_report import bp as test_report_bp


def create_app() -> Flask:
    here = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(here / "templates"),
        static_folder=str(here / "static"),
    )

    app.register_blueprint(reports_bp)
    app.register_blueprint(slot1_bp)
    app.register_blueprint(slot2_bp)
    app.register_blueprint(test_report_bp)
    app.register_blueprint(clear_reports_bp)
    app.register_blueprint(filesystem_bp)

    @app.route("/")
    def home():
        return render_template("home.html")

    return app
