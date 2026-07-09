"""One-command DB rebuild + seed.

Usage:  cd backend && python reset_db.py

Drops all tables, recreates the schema from schema.sql, then seeds demo data.
"""
import pathlib

from sqlalchemy import text

from app.core.db import engine
from seed import seed

SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


def apply_schema():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("Schema applied from schema.sql")


def main():
    apply_schema()
    seed()


if __name__ == "__main__":
    main()
