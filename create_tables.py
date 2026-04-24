"""Create all database tables from SQLAlchemy models. Bypasses Alembic."""
import os

from sqlalchemy import create_engine

import packages.db.models  # noqa: F401
from packages.db.base import Base

url = os.environ.get("DATABASE_URL_SYNC", "postgresql://avataros:changeme_in_production@postgres:5432/avatar_revenue_os")
engine = create_engine(url)
Base.metadata.create_all(bind=engine)
print(f"SUCCESS: Created {len(Base.metadata.tables)} tables")
