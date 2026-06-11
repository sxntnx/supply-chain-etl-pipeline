"""Generate a synthetic sample dataset matching the DataCo schema.

The real pipeline is built for the public *DataCo Smart Supply Chain* dataset
on Kaggle. To let anyone run the pipeline end-to-end without that download,
this script fabricates a statistically plausible sample with the same column
names, dtypes and quirks (latin-1 encoding, PII columns, nullable fields,
duplicate rows). It is NOT real data — it exists purely so the ETL is
reproducible and testable.

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
DEPARTMENTS = ["Fitness", "Footwear", "Apparel", "Golf", "Outdoors", "Technology", "Pet Shop"]
CATEGORIES = ["Cleats", "Shop", "Camping & Hiking", "Cardio Equipment",
              "Women's Apparel", "Men's Footwear", "Electronics", "Accessories"]
PRODUCTS = ["Field & Stream Sportsman Gun Safe", "Perfect Fitness Perfect Rip Deck",
            "Nike Men's Dri-FIT Tee", "Diamondback Bike", "O'Brien Wakeboard",
            "Pelican Kayak", "Garmin GPS Watch", "Under Armour Hoodie",
            "Adidas Soccer Ball", "TaylorMade Golf Set"]
DELIVERY_STATUS = ["Advance shipping", "Late delivery", "Shipping on time", "Shipping canceled"]
SHIPPING_MODES = ["Standard Class", "First Class", "Second Class", "Same Day"]
CITIES = ["Caguas", "Chicago", "Los Angeles", "New York City", "Tegucigalpa",
          "San Salvador", "Managua", "Santo Domingo", "Bogota", "Mexico City"]
COUNTRIES = ["EE. UU.", "Puerto Rico", "Honduras", "El Salvador", "Nicaragua",
             "Mexico", "Colombia", "Brasil", "Francia", "Alemania"]


def generate(rows: int) -> pd.DataFrame:
    n_customers = max(rows // 8, 1)
    n_products = min(len(PRODUCTS) * 40, max(rows // 50, len(PRODUCTS)))

    customer_ids = RNG.integers(1, n_customers + 1, size=rows)
    product_idx = RNG.integers(0, n_products, size=rows)
    product_card_ids = 1000 + (product_idx % n_products)

    base_date = datetime(2015, 1, 1)
    order_offsets = RNG.integers(0, 1400, size=rows)
    order_dates = [base_date + timedelta(days=int(o)) for o in order_offsets]

    scheduled = RNG.choice([1, 2, 4], size=rows, p=[0.2, 0.5, 0.3])
    # Real shipping days: usually around scheduled, sometimes late.
    real_days = np.clip(scheduled + RNG.integers(-1, 4, size=rows), 0, None)
    ship_dates = [d + timedelta(days=int(r)) for d, r in zip(order_dates, real_days)]

    market = RNG.choice(MARKETS, size=rows)
    region = [RNG.choice(REGIONS[m]) for m in market]

    quantity = RNG.integers(1, 6, size=rows)
    list_price = np.round(RNG.uniform(15, 400, size=n_products), 2)
    unit_price = list_price[product_idx % n_products]
    sales = np.round(unit_price * quantity, 2)
    profit = np.round(sales * RNG.uniform(-0.1, 0.35, size=rows), 2)

    df = pd.DataFrame(
        {
            "Type": RNG.choice(["DEBIT", "TRANSFER", "PAYMENT", "CASH"], size=rows),
            "Days for shipping (real)": real_days,
            "Days for shipment (scheduled)": scheduled,
            "Benefit per order": profit,
            "Sales per customer": sales,
            "Delivery Status": RNG.choice(DELIVERY_STATUS, size=rows, p=[0.25, 0.35, 0.35, 0.05]),
            "Late_delivery_risk": (real_days > scheduled).astype(int),
            "Category Id": (product_idx % len(CATEGORIES)) + 1,
            "Category Name": [CATEGORIES[i % len(CATEGORIES)] for i in product_idx],
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
            "Department Id": (product_idx % len(DEPARTMENTS)) + 2,
            "Department Name": [DEPARTMENTS[i % len(DEPARTMENTS)] for i in product_idx],
            "Market": market,
            "Order City": RNG.choice(CITIES, size=rows),
            "Order Country": RNG.choice(COUNTRIES, size=rows),
            "Order Customer Id": customer_ids,
            "order date (DateOrders)": [d.strftime("%m/%d/%Y %H:%M") for d in order_dates],
            "Order Id": RNG.integers(1, rows * 2, size=rows),
            "Order Item Cardprod Id": product_card_ids,
            "Order Item Discount": np.round(RNG.uniform(0, 50, size=rows), 2),
            "Order Item Discount Rate": np.round(RNG.uniform(0, 0.25, size=rows), 2),
            "Order Item Id": np.arange(1, rows + 1),
            "Order Item Product Price": unit_price,
            "Order Item Profit Ratio": np.round(RNG.uniform(-0.1, 0.35, size=rows), 2),
            "Order Item Quantity": quantity,
            "Sales": sales,
            "Order Item Total": sales,
            "Order Profit Per Order": np.where(
                RNG.random(rows) < 0.02, np.nan, profit  # ~2% nulls, as in source
            ),
            "Order Region": region,
            "Order State": RNG.choice(["PR", "Santa Fe", "California", "Texas"], size=rows),
            "Order Status": RNG.choice(["COMPLETE", "PENDING", "CLOSED", "PROCESSING"], size=rows),
            "Product Card Id": product_card_ids,
            "Product Category Id": (product_idx % len(CATEGORIES)) + 1,
            "Product Description": "",
            "Product Image": "http://images.example.com/img.jpg",
            "Product Name": [PRODUCTS[i % len(PRODUCTS)] for i in product_idx],
            "Product Price": unit_price,
            "Product Status": 0,
            "shipping date (DateOrders)": [d.strftime("%m/%d/%Y %H:%M") for d in ship_dates],
            "Shipping Mode": RNG.choice(SHIPPING_MODES, size=rows),
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


if __name__ == "__main__":
    main()
