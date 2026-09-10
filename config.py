"""
Central configuration for the Supply Chain ETL pipeline.

Keeping paths and settings in one place means no module hard-codes a
filesystem location. The storage engine is selected here too: the pipeline
loads into SQLite for a zero-setup local run, or into PostgreSQL (Neon) when
a connection string is supplied. Nothing upstream of `load.py` changes.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Read a local .env if present. Never commit that file — see .env.example.
load_dotenv()

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DATABASE_DIR = BASE_DIR / "database"

# Source file. The public DataCo dataset ships as latin-1 encoded CSV.
RAW_CSV_PATH = RAW_DIR / "DataCoSupplyChainDataset.csv"
RAW_CSV_ENCODING = "latin-1"

# Destination analytical database (SQLite backend).
DATABASE_PATH = DATABASE_DIR / "supply_chain.db"

# --------------------------------------------------------------------------- #
# Storage backend
# --------------------------------------------------------------------------- #
# "sqlite"   -> local file at DATABASE_PATH (default, no setup required)
# "postgres" -> managed PostgreSQL (Neon) via DATABASE_URL
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()

# SQLAlchemy URL for the PostgreSQL backend, e.g.
#   postgresql+psycopg2://user:password@host/dbname?sslmode=require
# Supplied through the environment so credentials never live in the repo.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Rows per INSERT batch when loading to PostgreSQL over the network.
LOAD_CHUNK_SIZE = int(os.getenv("LOAD_CHUNK_SIZE", "10000"))

# --------------------------------------------------------------------------- #
# Columns considered Personally Identifiable Information (dropped on ingest)
# --------------------------------------------------------------------------- #
PII_COLUMNS = [
    "Customer Email",
    "Customer Password",
    "Customer Street",
    "Customer Fname",
    "Customer Lname",
    "Product Description",
    "Product Image",
]

# --------------------------------------------------------------------------- #
# Date columns to parse
# --------------------------------------------------------------------------- #
ORDER_DATE_COL = "order date (DateOrders)"
SHIP_DATE_COL = "shipping date (DateOrders)"

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-9s | %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
