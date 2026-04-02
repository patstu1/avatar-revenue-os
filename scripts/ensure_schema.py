"""Ensure all database tables exist — safe to run on any DB state.

Uses SQLAlchemy create_all(checkfirst=True) which:
  - Creates tables that don't exist
  - Skips tables that already exist
  - Never fails on duplicates
Then applies any missing columns on existing tables.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text

DATABASE_URL = os.environ.get("DATABASE_URL_SYNC", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL_SYNC not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

print("Loading all models ...")
from packages.db.base import Base  # noqa: E402
import packages.db.models  # noqa: E402, F401

print(f"Models define {len(Base.metadata.tables)} tables.")

print("Creating missing tables (checkfirst=True) ...")
Base.metadata.create_all(engine, checkfirst=True)

inspector = inspect(engine)
existing_tables = set(inspector.get_table_names())
print(f"Database now has {len(existing_tables)} tables.")

COLUMN_ADDITIONS = [
    ("content_items", "offer_stack", "JSONB"),
    ("content_items", "cta_type", "VARCHAR(60)"),
    ("content_items", "offer_angle", "VARCHAR(60)"),
    ("content_items", "hook_type", "VARCHAR(60)"),
    ("content_items", "creative_structure", "VARCHAR(60)"),
    ("content_items", "audience_response_profile", "JSONB"),
    ("content_items", "monetization_density_score", "FLOAT DEFAULT 0.0"),
    ("creator_accounts", "scale_role", "VARCHAR(32)"),
    ("paid_amplification_jobs", "is_candidate", "BOOLEAN DEFAULT false"),
    ("scale_recommendations", "recommendation_key", "VARCHAR(80) DEFAULT ''"),
    ("scale_recommendations", "scale_readiness_score", "FLOAT DEFAULT 0.0"),
    ("scale_recommendations", "cannibalization_risk_score", "FLOAT DEFAULT 0.0"),
    ("scale_recommendations", "audience_segment_separation", "FLOAT DEFAULT 0.0"),
    ("scale_recommendations", "expansion_confidence", "FLOAT DEFAULT 0.0"),
    ("scale_recommendations", "recommended_account_count", "INTEGER DEFAULT 0"),
    ("scale_recommendations", "weekly_action_plan", "JSONB"),
    ("scale_recommendations", "best_next_account", "JSONB"),
]

print("Adding any missing columns to existing tables ...")
with engine.connect() as conn:
    for table, column, col_type in COLUMN_ADDITIONS:
        if table not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing_cols:
            print(f"  Adding {table}.{column} ({col_type})")
            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'))
            conn.commit()

    # Stamp alembic to head
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL
        )
    """))
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text("INSERT INTO alembic_version VALUES ('b6587e9c03b5')"))
    conn.commit()
    print("Alembic stamped to head (b6587e9c03b5).")

print("Schema sync complete.")
