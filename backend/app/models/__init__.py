"""Importing this package registers every table with SQLAlchemy (needed by Alembic)."""
from app.models import ar, sap  # noqa: F401
