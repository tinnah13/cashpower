"""Shared objects that other files import (kept here so files never import each other in circles)."""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(conn, _record):
    """SQLite ignores FOREIGN KEY rules unless asked. MySQL always enforces them."""
    if conn.__class__.__module__.startswith("sqlite3"):
        conn.execute("PRAGMA foreign_keys=ON")
