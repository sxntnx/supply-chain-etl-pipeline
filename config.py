"""
Central configuration for the Supply Chain ETL pipeline.

Keeping paths and settings in one place means no module hard-codes a
filesystem location. Swapping environments (local → server) or the storage
engine (SQLite → PostgreSQL) becomes a single-file change.
"""

from pathlib import Path

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

# Destination analytical database.
DATABASE_PATH = DATABASE_DIR / "supply_chain.db"

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
