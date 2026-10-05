"""Web dashboard package — Flask app with live monitoring."""
from .app import create_app, run_dashboard

__all__ = ["create_app", "run_dashboard"]
