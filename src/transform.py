"""Stage 2 — TRANSFORM.

Turn the raw, wide, dirty source table into a clean star schema:

    fact_orders   (transactional grain: one row per order line item)
    dim_customers (one row per customer)
    dim_products  (one row per product)

The transformations are deliberately ordered: clean first, then enrich, then
split. Each step is a small pure function so it can be reasoned about and
tested in isolation.
"""

import pandas as pd

import config
from src.utils import fmt_int, get_logger

log = get_logger("transform")


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def drop_pii(df: pd.DataFrame) -> pd.DataFrame:
    """Remove columns carrying personal data we have no business storing."""
    present = [c for c in config.PII_COLUMNS if c in df.columns]
    return df.drop(columns=present)


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the order and shipping date columns into real datetimes."""
    for col in (config.ORDER_DATE_COL, config.SHIP_DATE_COL):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def normalize_text(df: pd.DataFrame) -> pd.DataFrame:
    """Title-case and strip whitespace on the human-readable text fields."""
    text_cols = [
        "Customer City",
        "Customer State",
        "Customer Country",
        "Order City",
        "Order Country",
        "Order Region",
        "Product Name",
        "Category Name",
        "Department Name",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.title()
    return df


def fill_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Apply column-appropriate defaults to the known nullable fields."""
    if "Customer Zipcode" in df.columns:
        df["Customer Zipcode"] = df["Customer Zipcode"].fillna(0).astype("int64")
    for money_col in ("Order Profit Per Order", "Benefit per order"):
        if money_col in df.columns:
            df[money_col] = df[money_col].fillna(0.0)
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows, logging how many were removed."""
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    if removed:
        log.info("Removed %s exact duplicate rows", fmt_int(removed))
    return df


# --------------------------------------------------------------------------- #
# Enrichment
# --------------------------------------------------------------------------- #
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive analytics-ready delivery metrics.

    delivery_delay_days : actual shipping days minus scheduled days
                          (positive = late, negative = early)
    is_late_delivery    : 1 when the order shipped later than scheduled
    """
    real = "Days for shipping (real)"
    sched = "Days for shipment (scheduled)"
    if real in df.columns and sched in df.columns:
        df["delivery_delay_days"] = (df[real] - df[sched]).astype("int64")
        df["is_late_delivery"] = (df["delivery_delay_days"] > 0).astype("int64")
    return df


# --------------------------------------------------------------------------- #
# Schema split (star schema)
# --------------------------------------------------------------------------- #
def _select_rename(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Select the mapped source columns that exist and rename them.

    Keyed by name (not position), so a missing source column simply drops out
    instead of silently shifting every downstream column name.
    """
    present = {src: dst for src, dst in mapping.items() if src in df.columns}
    return df[list(present)].rename(columns=present)


def build_dim_customers(df: pd.DataFrame) -> pd.DataFrame:
    dim = _select_rename(
        df,
        {
            "Customer Id": "customer_id",
            "Customer Segment": "segment",
            "Customer City": "city",
            "Customer State": "state",
            "Customer Country": "country",
            "Customer Zipcode": "zipcode",
        },
    )
    dim = (
        dim.drop_duplicates(subset=["customer_id"])
        .sort_values("customer_id")
        .reset_index(drop=True)
    )
    log.info("dim_customers: %s unique customers", fmt_int(len(dim)))
    return dim


def build_dim_products(df: pd.DataFrame) -> pd.DataFrame:
    dim = _select_rename(
        df,
        {
            "Product Card Id": "product_id",
            "Product Name": "product_name",
            "Category Name": "category",
            "Department Name": "department",
            "Product Price": "list_price",
        },
    )
    dim = (
        dim.drop_duplicates(subset=["product_id"])
        .sort_values("product_id")
        .reset_index(drop=True)
    )
    log.info("dim_products:    %s unique products", fmt_int(len(dim)))
    return dim


def build_fact_orders(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "Order Item Id": "order_item_id",
        "Order Id": "order_id",
        "Order Customer Id": "order_customer_id",
        "Product Card Id": "product_id",
        config.ORDER_DATE_COL: "order_date",
        config.SHIP_DATE_COL: "ship_date",
        "Order Item Quantity": "quantity",
        "Sales": "sales",
        "Order Profit Per Order": "order_profit",
        "delivery_delay_days": "delivery_delay_days",
        "is_late_delivery": "is_late_delivery",
        "Delivery Status": "delivery_status",
        "Shipping Mode": "shipping_mode",
        "Market": "market",
        "Order Region": "order_region",
    }
    fact = _select_rename(df, mapping).reset_index(drop=True)

    # Dates stored as ISO 8601 text for portable SQLite storage.
    for date_col in ("order_date", "ship_date"):
        if date_col in fact.columns:
            fact[date_col] = fact[date_col].dt.strftime("%Y-%m-%d")

    log.info("fact_orders:   %s rows", fmt_int(len(fact)))
    return fact


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def transform(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Run the full transform stage and return the three modeled tables."""
    df = drop_pii(df)
    df = parse_dates(df)
    df = normalize_text(df)
    df = fill_nulls(df)
    df = deduplicate(df)
    df = engineer_features(df)

    return {
        "dim_customers": build_dim_customers(df),
        "dim_products": build_dim_products(df),
        "fact_orders": build_fact_orders(df),
    }
