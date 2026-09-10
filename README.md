# Supply Chain ETL Pipeline

An end-to-end ETL pipeline that extracts raw supply chain data, applies data
quality transformations, and loads a normalized **star schema** into an
analytical database — ready to answer real operational questions about
delivery performance and profitability.

Runs against **managed PostgreSQL in the cloud** (Neon) or a local **SQLite**
file, selected by one environment variable. The extract and transform stages
are identical either way.

Built with **Python · Pandas · SQLAlchemy · PostgreSQL / SQLite**

---

## Why this project

I'm an industrial engineer working in data analytics. Supply chains generate
wide, messy transactional exports that are useless for analysis until they're
cleaned and modeled. This pipeline does exactly that: it takes a raw 53-column
order export and turns it into a tidy star schema where questions like *"what's
our late-delivery rate by shipping mode?"* are a one-line SQL query.

---

## Architecture

```
data/raw/
  └── DataCoSupplyChainDataset.csv
        │
        ▼
   [extract.py]        → Load raw CSV (latin-1, 180K+ rows)
        │
        ▼
   [transform.py]      → Clean · Enrich · Split
        │
        ├── dim_customers   (unique customers)
        ├── dim_products    (unique products)
        └── fact_orders     (one row per order line)
                │
                ▼
          [load.py]         → typed schema + PKs + indexes
                │
        ┌───────┴────────┐
        ▼                ▼
  Neon PostgreSQL   database/supply_chain.db
   (DB_BACKEND=       (DB_BACKEND=sqlite)
     postgres)
```

---

## Transformations applied

| Step | Description |
|------|-------------|
| PII removal | Drop customer email, password, street, name fields |
| Date parsing | Parse order and ship dates to `datetime` |
| Feature engineering | `delivery_delay_days`, `is_late_delivery` |
| Text normalization | Title-case + strip city, country, product fields |
| Null handling | Fill missing zipcodes and profit values |
| Deduplication | Remove exact duplicate rows |
| Schema split | Normalize into 1 fact table + 2 dimension tables |

---

## Database schema

### `fact_orders`
| Column | Type | Description |
|--------|------|-------------|
| order_item_id | INTEGER | Primary key (order line grain) |
| order_id | INTEGER | Order identifier |
| order_customer_id | INTEGER | FK → dim_customers |
| product_id | INTEGER | FK → dim_products |
| order_date | DATE | Order date |
| ship_date | DATE | Shipping date |
| quantity | INTEGER | Units ordered |
| sales | REAL | Revenue |
| order_profit | REAL | Profit per order |
| delivery_delay_days | INTEGER | Actual − scheduled shipping days |
| is_late_delivery | INTEGER | 1 if late, 0 if on time |
| delivery_status | TEXT | Delivery outcome |
| shipping_mode | TEXT | Service level |
| market / order_region | TEXT | Geography |

### `dim_customers`
Unique customers with segment, city, state, country, zipcode.

### `dim_products`
Unique products with category, department, list price.

Primary keys are declared on all three tables, and indexes cover the fact
table's foreign keys, `is_late_delivery` and `order_date` — the columns the
KPI queries below actually filter and join on.

---

## Getting started

### 1. Clone and install
```bash
git clone https://github.com/sxntnx/supply-chain-etl-pipeline.git
cd supply-chain-etl-pipeline
pip install -r requirements.txt
```

### 2. Get the data — two options

**Option A — Real dataset (Kaggle).**
Download the [DataCo Smart Supply Chain Dataset](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis)
and place the CSV at `data/raw/DataCoSupplyChainDataset.csv`.

**Option B — Synthetic sample (no download).**
Generate a statistically plausible sample with the same schema so the pipeline
runs end-to-end out of the box:
```bash
python scripts/generate_sample_data.py --rows 20000
```

### 3. Choose where the data lands

**Option A — Cloud PostgreSQL (Neon).** Create a free project at
[neon.com](https://neon.com/), copy its connection string, then:

```bash
cp .env.example .env
# edit .env:
#   DB_BACKEND=postgres
#   DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

**Option B — Local SQLite.** Nothing to configure; this is the default when no
`.env` is present.

`.env` is git-ignored: credentials never enter the repository.

### 4. Run the pipeline
```bash
python main.py
```

Example run (synthetic 20K sample):
```
2026-06-11 11:56:22 | INFO     | pipeline  | Supply Chain ETL Pipeline - START
2026-06-11 11:56:22 | INFO     | pipeline  | [1/3] EXTRACT
2026-06-11 11:56:22 | INFO     | extract   | Extracted 20,020 rows x 50 columns
2026-06-11 11:56:22 | INFO     | pipeline  | [2/3] TRANSFORM
2026-06-11 11:56:22 | INFO     | transform | Removed 20 exact duplicate rows
2026-06-11 11:56:22 | INFO     | transform | dim_customers: 2,500 unique customers
2026-06-11 11:56:22 | INFO     | transform | dim_products:    400 unique products
2026-06-11 11:56:22 | INFO     | transform | fact_orders:   20,000 rows
2026-06-11 11:56:22 | INFO     | pipeline  | [3/3] LOAD
2026-06-11 11:56:22 | INFO     | load      | Database written to .../supply_chain.db
2026-06-11 11:56:22 | INFO     | pipeline  | Pipeline completed in 0.34s
```

---

## Analytics

The point of modeling the data is to query it. `sql/analytics_queries.sql`
contains the operational questions this schema was built to answer:

```bash
# PostgreSQL / Neon
psql "$DATABASE_URL" -f sql/analytics_queries.sql

# SQLite
sqlite3 database/supply_chain.db < sql/analytics_queries.sql
```

| # | Question (KPI) |
|---|----------------|
| 1 | On-Time Delivery rate — % of order lines shipped late |
| 2 | Average delivery delay by shipping mode |
| 3 | Profitability by region (revenue vs. margin) |
| 4 | Top 10 products by revenue and their margin |
| 5 | Late-delivery rate by customer segment |

And `scripts/plot_kpis.py` renders these into a dashboard image:

```bash
python scripts/plot_kpis.py     # → reports/kpi_dashboard.png
```

![KPI dashboard](reports/kpi_dashboard.png)

---

## Project structure

```
supply-chain-etl/
├── data/raw/                   # Source CSV lives here
├── database/                   # supply_chain.db (generated)
├── src/
│   ├── extract.py              # Stage 1: load raw data
│   ├── transform.py            # Stage 2: clean, enrich, model
│   ├── load.py                 # Stage 3: write to Postgres/SQLite + index
│   └── utils.py                # Logger and helpers
├── scripts/
│   ├── generate_sample_data.py # Synthetic DataCo-style data generator
│   └── plot_kpis.py            # Render KPI dashboard image
├── sql/
│   └── analytics_queries.sql   # Operational KPI queries
├── reports/
│   └── kpi_dashboard.png       # Generated KPI visuals
├── config.py                   # Paths, backend selection, settings
├── .env.example                # Template for local credentials
├── main.py                     # Pipeline entry point
├── requirements.txt
└── README.md
```

---

## Key design decisions

- **Modular stages** — extract / transform / load are isolated and independently testable. Each transform step is a small pure function.
- **Config-driven** — paths, PII columns and settings live in `config.py`; no module hard-codes a path.
- **Star schema** — separating dimensions from facts keeps the fact table narrow and analytical joins cheap.
- **Pluggable storage** — persistence is isolated in `load.py` behind a single SQLAlchemy engine factory, so PostgreSQL and SQLite are one environment variable apart. Cloud Postgres for a shareable, BI-connectable warehouse; SQLite for a zero-setup local run.
- **Typed schema, not inferred** — explicit column types, primary keys and indexes are declared on load rather than left to pandas' inference, so the database documents its own grain.
- **Credentials out of the repo** — the connection string is read from the environment via `.env`, which is git-ignored; `.env.example` documents the shape.
- **Reproducible** — the synthetic generator means anyone can run the full pipeline without hunting down the source data.

---

## Dataset

**DataCo Smart Supply Chain for Big Data Analysis**
Source: [Kaggle](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis)
~180K order records across global markets — orders, shipping, customers, products.
