"""Generate a synthetic sample dataset matching the DataCo schema.

The real pipeline is built for the public *DataCo Smart Supply Chain* dataset
on Kaggle. To let anyone run the pipeline end-to-end without that download,
this script fabricates a statistically plausible sample with the same column
names, dtypes and quirks (latin-1 encoding, PII columns, nullable fields,
duplicate rows). It is NOT real data — it exists purely so the ETL is
reproducible and testable.

Two properties are deliberate, because an earlier version of this script drew
name, category, department and price independently per row and produced a
warehouse that could not be aggregated:

1. A product is one entity. The catalog below is the single source of truth:
   a product name appears exactly once, carries exactly one category, and the
   category fixes the department. A line's selling price derives from that
   product's list price, so `dim_products` has one row per real product and a
   category rollup can never disagree with a department rollup.

2. The dimensions carry signal. Shipping mode drives the scheduled days and
   the probability of missing them; margin varies by category and by region.
   The noise is wide enough that no cut separates perfectly — but a cut that
   should discriminate now does.

Usage:
    python scripts/generate_sample_data.py            # 20,000 rows (default)
    python scripts/generate_sample_data.py --rows 50000
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running as a standalone script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

RNG = np.random.default_rng(42)

SEGMENTS = ["Consumer", "Corporate", "Home Office"]
MARKETS = ["LATAM", "Europe", "Pacific Asia", "USCA", "Africa"]
REGIONS = {
    "LATAM": ["South America", "Central America", "Caribbean"],
    "Europe": ["Western Europe", "Southern Europe", "Northern Europe"],
    "Pacific Asia": ["Southeast Asia", "South Asia", "Oceania", "East Asia"],
    "USCA": ["US Center", "West of USA", "East of USA", "Canada"],
    "Africa": ["West Africa", "North Africa", "East Africa"],
}

# --------------------------------------------------------------------------- #
# Product catalog — the single source of truth for the product dimension
# --------------------------------------------------------------------------- #
# Each category belongs to exactly one department. Reading the hierarchy from
# one place is what keeps "Cleats" from showing up under seven departments.
CATEGORY_DEPARTMENT = {
    "Cleats": "Footwear",
    "Men's Footwear": "Footwear",
    "Cardio Equipment": "Fitness",
    "Women's Apparel": "Apparel",
    "Shop": "Golf",
    "Camping & Hiking": "Outdoors",
    "Electronics": "Technology",
    "Accessories": "Pet Shop",
}
CATEGORIES = list(CATEGORY_DEPARTMENT)
DEPARTMENTS = sorted(set(CATEGORY_DEPARTMENT.values()))

# (product name, category, list price). Names are unique; the category
# determines the department, so every product resolves to one hierarchy path.
CATALOG: list[tuple[str, str, float]] = [
    # Footwear / Cleats
    ("Nike Mercurial Vapor Cleats", "Cleats", 129.99),
    ("Adidas Copa Sense Cleats", "Cleats", 99.99),
    ("Puma Future Match Cleats", "Cleats", 74.99),
    ("Under Armour Spotlight Cleats", "Cleats", 84.99),
    ("New Balance Furon Dispatch Cleats", "Cleats", 64.99),
    # Footwear / Men's Footwear
    ("Nike Air Zoom Pegasus Running Shoe", "Men's Footwear", 119.99),
    ("Brooks Ghost Running Shoe", "Men's Footwear", 129.99),
    ("Merrell Moab Hiking Shoe", "Men's Footwear", 109.99),
    ("Sperry Authentic Original Boat Shoe", "Men's Footwear", 94.99),
    ("Crocs Classic Clog", "Men's Footwear", 44.99),
    # Fitness / Cardio Equipment
    ("Sole Folding Treadmill", "Cardio Equipment", 899.99),
    ("Schwinn Indoor Cycling Bike", "Cardio Equipment", 749.99),
    ("Stamina Elite Rowing Machine", "Cardio Equipment", 549.99),
    ("Bowflex Adjustable Dumbbell Set", "Cardio Equipment", 349.99),
    ("Perfect Fitness Perfect Rip Deck", "Cardio Equipment", 59.99),
    # Apparel / Women's Apparel
    ("Nike Women's Dri Fit Running Tee", "Women's Apparel", 34.99),
    ("Lululemon Align High Rise Legging", "Women's Apparel", 98.00),
    ("The North Face Resolve Rain Jacket", "Women's Apparel", 89.95),
    ("Adidas Essentials Fleece Hoodie", "Women's Apparel", 54.99),
    ("Columbia Benton Springs Fleece Jacket", "Women's Apparel", 44.99),
    # Golf / Shop
    ("Taylormade Stealth Driver", "Shop", 429.99),
    ("Callaway Rogue Iron Set", "Shop", 799.99),
    ("Odyssey White Hot Putter", "Shop", 199.99),
    ("Bushnell Tour Laser Rangefinder", "Shop", 299.99),
    ("Titleist Pro V1 Golf Balls", "Shop", 54.99),
    ("Footjoy Weathersof Golf Glove", "Shop", 21.99),
    # Outdoors / Camping & Hiking
    ("Field & Stream Sportsman Gun Safe", "Camping & Hiking", 399.99),
    ("Pelican Maxim Sit In Kayak", "Camping & Hiking", 349.99),
    ("O'Brien Sequence Wakeboard", "Camping & Hiking", 269.99),
    ("Osprey Atmos Hiking Backpack", "Camping & Hiking", 279.95),
    ("Coleman Sundome 4 Person Tent", "Camping & Hiking", 89.99),
    ("Primus Classic Camp Stove", "Camping & Hiking", 49.95),
    # Technology / Electronics
    ("Gopro Hero Action Camera", "Electronics", 399.99),
    ("Garmin Forerunner Running Watch", "Electronics", 299.99),
    ("Bose Soundlink Bluetooth Speaker", "Electronics", 149.00),
    ("Jabra Elite Active Earbuds", "Electronics", 119.99),
    ("Anker Powercore Portable Charger", "Electronics", 49.99),
    # Pet Shop / Accessories
    ("Furhaven Orthopedic Pet Bed", "Accessories", 59.99),
    ("Frisco Elevated Dog Bowl", "Accessories", 34.99),
    ("Petsafe Retractable Dog Leash", "Accessories", 24.99),
    ("Chuckit Ultra Ball Launcher", "Accessories", 15.99),
    ("Kong Classic Dog Toy", "Accessories", 12.99),
]

# --------------------------------------------------------------------------- #
# Business rules the dimensions are supposed to explain
# --------------------------------------------------------------------------- #
# Shipping mode -> (share of order lines, scheduled days, P(misses schedule)).
# A premium service level promises less time and keeps that promise more often;
# Standard Class is the one with a delivery problem.
SHIPPING_MODES = {
    "Standard Class": (0.58, 4, 0.62),
    "Second Class": (0.20, 2, 0.44),
    "First Class": (0.14, 1, 0.28),
    "Same Day": (0.08, 0, 0.11),
}
# How badly a late line runs over, by mode (inclusive day range).
LATE_OVERRUN_DAYS = {
    "Standard Class": (1, 4),
    "Second Class": (1, 3),
    "First Class": (1, 3),
    "Same Day": (1, 2),
}

# Baseline gross margin by category: commodity electronics are thin, pet
# accessories are fat.
CATEGORY_MARGIN = {
    "Electronics": 0.05,
    "Cardio Equipment": 0.09,
    "Men's Footwear": 0.12,
    "Cleats": 0.13,
    "Camping & Hiking": 0.15,
    "Shop": 0.17,
    "Women's Apparel": 0.21,
    "Accessories": 0.26,
}
# Margin lost or gained to landed cost and local pricing power, by region.
# The African regions and the Caribbean sit far enough below the rest to end
# the year underwater once the category mix is applied.
REGION_MARGIN_ADJ = {
    "South America": 0.02,
    "Central America": -0.04,
    "Caribbean": -0.11,
    "Western Europe": 0.05,
    "Southern Europe": -0.01,
    "Northern Europe": 0.06,
    "Southeast Asia": 0.01,
    "South Asia": -0.09,
    "Oceania": 0.03,
    "East Asia": 0.02,
    "US Center": 0.04,
    "West of USA": 0.03,
    "East of USA": 0.05,
    "Canada": 0.02,
    "West Africa": -0.16,
    "North Africa": -0.12,
    "East Africa": -0.18,
}

DELIVERY_STATUS_CANCELED = "Shipping canceled"
CITIES = ["Caguas", "Chicago", "Los Angeles", "New York City", "Tegucigalpa",
          "San Salvador", "Managua", "Santo Domingo", "Bogota", "Mexico City"]
COUNTRIES = ["EE. UU.", "Puerto Rico", "Honduras", "El Salvador", "Nicaragua",
             "Mexico", "Colombia", "Brasil", "Francia", "Alemania"]


def build_catalog() -> pd.DataFrame:
    """Materialize the catalog with its surrogate keys."""
    products = pd.DataFrame(CATALOG, columns=["product_name", "category", "list_price"])
    products["department"] = products["category"].map(CATEGORY_DEPARTMENT)
    products["category_id"] = products["category"].map(
        {name: i + 1 for i, name in enumerate(CATEGORIES)}
    )
    products["department_id"] = products["department"].map(
        {name: i + 1 for i, name in enumerate(DEPARTMENTS)}
    )
    products["product_card_id"] = 1000 + np.arange(len(products))
    return products


def popularity_weights(list_prices: np.ndarray) -> np.ndarray:
    """Unit volume, skewed toward the cheap end of the catalog.

    Sampling products uniformly makes a "top 10 by revenue" ranking pure
    noise. Letting a $900 treadmill sell as briskly as a $13 dog toy is the
    opposite failure: two big-ticket SKUs swallow the whole revenue chart.
    Cheap things move more units, and a lognormal factor keeps the ranking
    from collapsing into a straight price sort.
    """
    weights = list_prices ** -0.45 * RNG.lognormal(0.0, 0.45, size=len(list_prices))
    return weights / weights.sum()


def draw_shipping(rows: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (mode, scheduled days, real days) with mode-dependent lateness."""
    modes = np.array(list(SHIPPING_MODES))
    shares = np.array([SHIPPING_MODES[m][0] for m in modes])
    mode = RNG.choice(modes, size=rows, p=shares / shares.sum())

    scheduled = np.empty(rows, dtype=np.int64)
    real = np.empty(rows, dtype=np.int64)
    for name in modes:
        picked = mode == name
        n = int(picked.sum())
        if not n:
            continue
        _, sched_days, late_prob = SHIPPING_MODES[name]
        low, high = LATE_OVERRUN_DAYS[name]

        is_late = RNG.random(n) < late_prob
        overrun = RNG.integers(low, high + 1, size=n)
        # On-time lines land on the promise or, occasionally, a day early.
        early = RNG.integers(0, min(sched_days, 2) + 1, size=n)
        days = np.where(is_late, sched_days + overrun, sched_days - early)

        scheduled[picked] = sched_days
        real[picked] = np.clip(days, 0, None)
    return mode, scheduled, real


def generate(rows: int) -> pd.DataFrame:
    catalog = build_catalog()
    n_customers = max(rows // 8, 1)

    customer_ids = RNG.integers(1, n_customers + 1, size=rows)
    weights = popularity_weights(catalog["list_price"].to_numpy())
    product_idx = RNG.choice(len(catalog), size=rows, p=weights)
    picked = catalog.iloc[product_idx].reset_index(drop=True)

    base_date = datetime(2015, 1, 1)
    order_offsets = RNG.integers(0, 1400, size=rows)
    order_dates = [base_date + timedelta(days=int(o)) for o in order_offsets]

    shipping_mode, scheduled, real_days = draw_shipping(rows)
    ship_dates = [d + timedelta(days=int(r)) for d, r in zip(order_dates, real_days)]

    delay = real_days - scheduled
    delivery_status = np.where(
        delay < 0, "Advance shipping",
        np.where(delay == 0, "Shipping on time", "Late delivery"),
    )
    # A few lines never ship at all, independent of the service level.
    delivery_status = np.where(
        RNG.random(rows) < 0.04, DELIVERY_STATUS_CANCELED, delivery_status
    )

    market = RNG.choice(MARKETS, size=rows)
    region = np.array([RNG.choice(REGIONS[m]) for m in market])

    # Price paid derives from the product's list price: same product, same
    # ballpark, with the small variation a discount or FX move would produce.
    quantity = RNG.integers(1, 6, size=rows)
    list_price = picked["list_price"].to_numpy()
    unit_price = np.round(list_price * RNG.uniform(0.95, 1.05, size=rows), 2)
    sales = np.round(unit_price * quantity, 2)

    margin = (
        picked["category"].map(CATEGORY_MARGIN).to_numpy()
        + np.array([REGION_MARGIN_ADJ[r] for r in region])
        + RNG.normal(0, 0.10, size=rows)
    ).clip(-0.5, 0.6)
    profit = np.round(sales * margin, 2)

    discount_rate = np.round(RNG.uniform(0, 0.25, size=rows), 2)

    df = pd.DataFrame(
        {
            "Type": RNG.choice(["DEBIT", "TRANSFER", "PAYMENT", "CASH"], size=rows),
            "Days for shipping (real)": real_days,
            "Days for shipment (scheduled)": scheduled,
            "Benefit per order": profit,
            "Sales per customer": sales,
            "Delivery Status": delivery_status,
            "Late_delivery_risk": (real_days > scheduled).astype(int),
            "Category Id": picked["category_id"],
            "Category Name": picked["category"],
            "Customer City": RNG.choice(CITIES, size=rows),
            "Customer Country": RNG.choice(COUNTRIES, size=rows),
            "Customer Email": "XXXXXXXXX",            # PII placeholder, as in source
            "Customer Fname": RNG.choice(["Mary", "Jose", "Ana", "Luis", "Sofia"], size=rows),
            "Customer Id": customer_ids,
            "Customer Lname": RNG.choice(["Smith", "Garcia", "Lopez", "Ruiz", "Diaz"], size=rows),
            "Customer Password": "XXXXXXXXX",          # PII placeholder
            "Customer Segment": RNG.choice(SEGMENTS, size=rows),
            "Customer State": RNG.choice(["PR", "IL", "CA", "NY", "TX"], size=rows),
            "Customer Street": "XXXXXXXXX",            # PII placeholder
            "Customer Zipcode": RNG.choice(
                np.append(RNG.integers(600, 99999, size=200), [np.nan]), size=rows
            ),
            "Department Id": picked["department_id"],
            "Department Name": picked["department"],
            "Market": market,
            "Order City": RNG.choice(CITIES, size=rows),
            "Order Country": RNG.choice(COUNTRIES, size=rows),
            "Order Customer Id": customer_ids,
            "order date (DateOrders)": [d.strftime("%m/%d/%Y %H:%M") for d in order_dates],
            "Order Id": RNG.integers(1, rows * 2, size=rows),
            "Order Item Cardprod Id": picked["product_card_id"],
            "Order Item Discount": np.round(sales * discount_rate, 2),
            "Order Item Discount Rate": discount_rate,
            "Order Item Id": np.arange(1, rows + 1),
            "Order Item Product Price": unit_price,
            "Order Item Profit Ratio": np.round(margin, 2),
            "Order Item Quantity": quantity,
            "Sales": sales,
            "Order Item Total": sales,
            "Order Profit Per Order": np.where(
                RNG.random(rows) < 0.02, np.nan, profit  # ~2% nulls, as in source
            ),
            "Order Region": region,
            "Order State": RNG.choice(["PR", "Santa Fe", "California", "Texas"], size=rows),
            "Order Status": RNG.choice(["COMPLETE", "PENDING", "CLOSED", "PROCESSING"], size=rows),
            "Product Card Id": picked["product_card_id"],
            "Product Category Id": picked["category_id"],
            "Product Description": "",
            "Product Image": "http://images.example.com/img.jpg",
            "Product Name": picked["product_name"],
            # List price, not the price paid — this is what lands in dim_products.
            "Product Price": list_price,
            "Product Status": 0,
            "shipping date (DateOrders)": [d.strftime("%m/%d/%Y %H:%M") for d in ship_dates],
            "Shipping Mode": shipping_mode,
        }
    )

    # Inject a handful of exact duplicate rows so the dedup step has work to do.
    dup_count = max(rows // 1000, 1)
    duplicates = df.sample(dup_count, random_state=42)
    df = pd.concat([df, duplicates], ignore_index=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic DataCo-style sample data.")
    parser.add_argument("--rows", type=int, default=20_000, help="Number of base rows to generate.")
    args = parser.parse_args()

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    df = generate(args.rows)
    df.to_csv(config.RAW_CSV_PATH, index=False, encoding=config.RAW_CSV_ENCODING)
    print(f"Wrote {len(df):,} rows x {df.shape[1]} columns -> {config.RAW_CSV_PATH}")
    print(f"Catalog: {len(CATALOG)} products, {len(CATEGORIES)} categories, "
          f"{len(DEPARTMENTS)} departments")


if __name__ == "__main__":
    main()
