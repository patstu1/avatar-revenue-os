"""Create all database tables from SQLAlchemy models. Bypasses Alembic."""
import os
from packages.db.base import Base
import packages.db.models  # noqa: F401
from sqlalchemy import create_engine

url = os.environ.get("DATABASE_URL_SYNC", "postgresql://avataros:changeme_in_production@postgres:5432/avatar_revenue_os")
engine = create_engine(url)
Base.metadata.create_all(bind=engine)
print(f"SUCCESS: Created {len(Base.metadata.tables)} tables")
