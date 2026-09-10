"""Tests for the LOAD stage against a throwaway SQLite file."""

import sqlite3

import pandas as pd
import pytest

import config
from scripts import generate_sample_data as gen
from src import load, transform


@pytest.fixture
def sqlite_backend(monkeypatch):
    """Force the SQLite path regardless of the developer's local .env."""
    monkeypatch.setattr(config, "DB_BACKEND", "sqlite")


@pytest.fixture(scope="module")
def tables() -> dict[str, pd.DataFrame]:
    return transform.transform(gen.generate(500))


def test_load_writes_every_table(sqlite_backend, tables, tmp_path):
    db = tmp_path / "warehouse.db"

    load.load(tables, db_path=db)

    with sqlite3.connect(db) as conn:
        for name, frame in tables.items():
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            assert count == len(frame)


def test_load_creates_the_fact_table_indexes(sqlite_backend, tables, tmp_path):
    db = tmp_path / "warehouse.db"

    load.load(tables, db_path=db)

    with sqlite3.connect(db) as conn:
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert {name for name, _column in load.INDEXES["fact_orders"]} <= indexes


def test_large_chunk_size_survives_sqlites_parameter_limit(
    sqlite_backend, tables, tmp_path, monkeypatch
):
    """A 10,000-row chunk of a 15-column table is 150,000 bound parameters.

    PostgreSQL swallows that; SQLite refuses it. The configured chunk size has
    to be clamped per backend, or every local run dies on `fact_orders`.
    """
    monkeypatch.setattr(config, "LOAD_CHUNK_SIZE", 10_000)

    load.load(tables, db_path=tmp_path / "warehouse.db")  # must not raise

    assert load._chunksize(tables["fact_orders"]) * len(
        tables["fact_orders"].columns
    ) <= load.SQLITE_MAX_VARIABLES


def test_load_replaces_rather_than_appends(sqlite_backend, tables, tmp_path):
    db = tmp_path / "warehouse.db"

    load.load(tables, db_path=db)
    load.load(tables, db_path=db)

    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    assert count == len(tables["fact_orders"])
