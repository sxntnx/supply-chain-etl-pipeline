"""Stage 3 — LOAD.

Write the modeled tables to an analytical database and add the indexes an
analyst would actually query on.

Two backends are supported behind one interface:

    sqlite   — a local file, zero setup, good for a quick reproducible run
    postgres — managed PostgreSQL (Neon), so the star schema lives in the
               cloud and any SQL client, BI tool or agent can query it

Selected by the DB_BACKEND environment variable; the extract and transform
stages are identical either way.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import Date, Engine, Float, Integer, Text, create_engine, text

import config
from src.utils import fmt_int, get_logger

log = get_logger("load")

# Indexes on the fact table's foreign keys and common filter columns.
INDEXES = {
    "fact_orders": [
        ("idx_fact_customer", "order_customer_id"),
        ("idx_fact_product", "product_id"),
        ("idx_fact_late", "is_late_delivery"),
        ("idx_fact_order_date", "order_date"),
    ],
}

# Explicit column types for PostgreSQL. Without these, pandas infers TEXT for
# the ISO date strings and BIGINT/DOUBLE for everything numeric — queryable,
# but not the schema an analyst wants to inherit.
POSTGRES_DTYPES = {
    "fact_orders": {
        "order_item_id": Integer,
        "order_id": Integer,
        "order_customer_id": Integer,
        "product_id": Integer,
        "order_date": Date,
        "ship_date": Date,
        "quantity": Integer,
        "sales": Float,
        "order_profit": Float,
        "delivery_delay_days": Integer,
        "is_late_delivery": Integer,
        "delivery_status": Text,
        "shipping_mode": Text,
        "market": Text,
        "order_region": Text,
    },
    "dim_customers": {
        "customer_id": Integer,
        "segment": Text,
        "city": Text,
        "state": Text,
        "country": Text,
        "zipcode": Integer,
    },
    "dim_products": {
        "product_id": Integer,
        "product_name": Text,
        "category": Text,
        "department": Text,
        "list_price": Float,
    },
}

# Primary keys applied after load, so the schema documents its own grain.
PRIMARY_KEYS = {
    "fact_orders": "order_item_id",
    "dim_customers": "customer_id",
    "dim_products": "product_id",
}


def create_engine_for_backend(db_path: Path = config.DATABASE_PATH) -> Engine:
    """Build the SQLAlchemy engine for the configured backend.

    Raises a clear error rather than silently falling back to SQLite when
    postgres is requested without a connection string — a half-configured
    pipeline that writes to the wrong place is worse than one that stops.
    """
    if config.DB_BACKEND == "postgres":
        if not config.DATABASE_URL:
            raise RuntimeError(
                "DB_BACKEND=postgres but DATABASE_URL is empty. "
                "Copy .env.example to .env and set your connection string."
            )
        log.info("Backend: PostgreSQL")
        # pool_pre_ping keeps serverless Postgres (Neon scales to zero) from
        # handing back a connection that went away while the compute slept.
        return create_engine(config.DATABASE_URL, pool_pre_ping=True)

    log.info("Backend: SQLite (%s)", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")


def _table_dtypes(name: str) -> dict | None:
    """Column type overrides for the current backend, if any."""
    if config.DB_BACKEND == "postgres":
        return POSTGRES_DTYPES.get(name)
    return None


def _apply_constraints(engine: Engine, tables: dict[str, pd.DataFrame]) -> None:
    """Add primary keys and indexes to the freshly written tables."""
    with engine.begin() as conn:
        # Primary keys (PostgreSQL only — pandas cannot declare them itself,
        # and SQLite will not add one to an existing table).
        if config.DB_BACKEND == "postgres":
            for table, column in PRIMARY_KEYS.items():
                if table not in tables:
                    continue
                conn.execute(
                    text(
                        f"ALTER TABLE {table} "
                        f"ADD CONSTRAINT pk_{table} PRIMARY KEY ({column})"
                    )
                )
                log.info("Primary key on %s(%s)", table, column)

        for table, indexes in INDEXES.items():
            if table not in tables:
                continue
            for idx_name, column in indexes:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {idx_name} "
                        f"ON {table} ({column})"
                    )
                )
        log.info("Indexes created")


def load(tables: dict[str, pd.DataFrame], db_path: Path = config.DATABASE_PATH) -> None:
    """Persist each table (replacing any prior run), then index it."""
    engine = create_engine_for_backend(db_path)

    for name, frame in tables.items():
        frame.to_sql(
            name,
            engine,
            if_exists="replace",
            index=False,
            dtype=_table_dtypes(name),
            chunksize=config.LOAD_CHUNK_SIZE,
            method="multi",
        )
        log.info("Wrote table '%s' (%s rows)", name, fmt_int(len(frame)))

    _apply_constraints(engine, tables)

    destination = "Neon PostgreSQL" if config.DB_BACKEND == "postgres" else db_path
    log.info("Database written to %s", destination)
    engine.dispose()
