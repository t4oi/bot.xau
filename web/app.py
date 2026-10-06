"""Flask dashboard application factory."""
from __future__ import annotations
import os
from typing import Optional

from flask import Flask, jsonify, render_template_string, request

from config.settings import get_settings
from core.logging_config import get_logger

logger = get_logger("web.app")


def create_app(repository=None, scan_loop=None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["SECRET_KEY"] = os.urandom(24).hex()
    app.config["repo"] = repository
    app.config["scan_loop"] = scan_loop

    from .routes import register_routes
    register_routes(app)
    return app


def run_dashboard(repository=None, scan_loop=None, host: str = "0.0.0.0", port: int = 8080) -> None:
    settings = get_settings()
    app = create_app(repository, scan_loop)
    logger.info("Starting web dashboard on %s:%d", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False)
