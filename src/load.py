"""Stage 3 — LOAD.

Write the modeled tables to a SQLite analytical database and add the indexes
an analyst would actually query on. Isolating persistence here is what makes
the storage engine swappable: point `create_connection` at PostgreSQL and the
rest of the pipeline is untouched.
"""

import sqlite3
from pathlib import Path

import pandas as pd

import config
from src.utils import fmt_int, get_logger

log = get_logger("load")

# Indexes on the fact table's foreign keys and common filter columns.
INDEXES = {
    "fact_orders": [
        ("idx_fact_customer", "order_customer_id"),
        ("idx_fact_product", "product_id"),
        ("idx_fact_late", "is_late_delivery"),
    ],
}


def create_connection(db_path: Path = config.DATABASE_PATH) -> sqlite3.Connection:
    """Open a SQLite connection, creating the parent directory if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def load(tables: dict[str, pd.DataFrame], db_path: Path = config.DATABASE_PATH) -> None:
    """Persist each table to SQLite (replacing any prior run) and index it."""
    with create_connection(db_path) as conn:
        for name, frame in tables.items():
            frame.to_sql(name, conn, if_exists="replace", index=False)
            log.info("Wrote table '%s' (%s rows)", name, fmt_int(len(frame)))

        cur = conn.cursor()
        for table, indexes in INDEXES.items():
            if table not in tables:
                continue
            for idx_name, column in indexes:
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} "
                    f"ON {table} ({column})"
                )
        conn.commit()

    log.info("Database written to %s", db_path)
