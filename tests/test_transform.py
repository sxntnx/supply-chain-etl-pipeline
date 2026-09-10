"""Unit tests for the TRANSFORM stage.

Each transform step is a small pure function, so each one gets a small,
handwritten frame rather than a fixture chain.
"""

import pandas as pd

import config
from src import transform


def test_drop_pii_removes_every_configured_column():
    df = pd.DataFrame({
        "Customer Email": ["a@b.com"],
        "Customer Password": ["hunter2"],
        "Customer Id": [1],
    })

    out = transform.drop_pii(df)

    assert "Customer Id" in out.columns
    assert not set(config.PII_COLUMNS) & set(out.columns)


def test_parse_dates_converts_strings_and_coerces_garbage():
    df = pd.DataFrame({
        config.ORDER_DATE_COL: ["01/15/2015 10:30", "not a date"],
        config.SHIP_DATE_COL: ["01/17/2015 10:30", "01/18/2015 10:30"],
    })

    out = transform.parse_dates(df)

    assert out[config.ORDER_DATE_COL].iloc[0].year == 2015
    assert pd.isna(out[config.ORDER_DATE_COL].iloc[1])


def test_normalize_text_strips_and_title_cases():
    df = pd.DataFrame({"Customer City": ["  chicago ", "LOS ANGELES"]})

    out = transform.normalize_text(df)

    assert list(out["Customer City"]) == ["Chicago", "Los Angeles"]


def test_normalize_text_keeps_possessives_lowercase():
    """Title-casing must not turn "Women's Apparel" into "Women'S Apparel".

    The product name is an entity key now, so a mangled one is a defect.
    """
    df = pd.DataFrame({"Category Name": ["women's apparel", "men's footwear"]})

    out = transform.normalize_text(df)

    assert list(out["Category Name"]) == ["Women's Apparel", "Men's Footwear"]


def test_fill_nulls_applies_column_appropriate_defaults():
    df = pd.DataFrame({
        "Customer Zipcode": [12345.0, None],
        "Order Profit Per Order": [10.5, None],
    })

    out = transform.fill_nulls(df)

    assert out["Customer Zipcode"].tolist() == [12345, 0]
    assert out["Order Profit Per Order"].tolist() == [10.5, 0.0]


def test_deduplicate_removes_exact_duplicates_only():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "x"]})

    assert len(transform.deduplicate(df)) == 2


def test_engineer_features_signs_the_delay_and_flags_late_lines():
    df = pd.DataFrame({
        "Days for shipping (real)": [6, 2, 1],
        "Days for shipment (scheduled)": [4, 2, 4],
    })

    out = transform.engineer_features(df)

    assert out["delivery_delay_days"].tolist() == [2, 0, -3]
    assert out["is_late_delivery"].tolist() == [1, 0, 0]


def test_build_dim_products_holds_one_row_per_product():
    df = pd.DataFrame({
        "Product Card Id": [1000, 1000, 1001],
        "Product Name": ["Kong Classic Dog Toy"] * 2 + ["Crocs Classic Clog"],
        "Category Name": ["Accessories"] * 2 + ["Men's Footwear"],
        "Department Name": ["Pet Shop"] * 2 + ["Footwear"],
        "Product Price": [12.99, 12.99, 44.99],
    })

    dim = transform.build_dim_products(df)

    assert len(dim) == 2
    assert dim["product_id"].is_unique
    assert list(dim.columns) == [
        "product_id", "product_name", "category", "department", "list_price"
    ]


def test_build_dim_customers_holds_one_row_per_customer():
    df = pd.DataFrame({
        "Customer Id": [7, 7, 3],
        "Customer Segment": ["Consumer", "Consumer", "Corporate"],
        "Customer City": ["Chicago", "Chicago", "Bogota"],
    })

    dim = transform.build_dim_customers(df)

    assert dim["customer_id"].tolist() == [3, 7]


def test_build_fact_orders_emits_dates_not_strings():
    df = pd.DataFrame({
        "Order Item Id": [1],
        "Order Id": [10],
        "Order Customer Id": [7],
        "Product Card Id": [1000],
        config.ORDER_DATE_COL: pd.to_datetime(["2015-01-15"]),
        config.SHIP_DATE_COL: pd.to_datetime(["2015-01-19"]),
        "Order Item Quantity": [2],
        "Sales": [25.98],
        "Order Profit Per Order": [5.20],
        "Shipping Mode": ["Standard Class"],
    })

    fact = transform.build_fact_orders(df)

    assert fact["order_date"].iloc[0].isoformat() == "2015-01-15"
    assert not isinstance(fact["ship_date"].iloc[0], str)


def test_missing_source_column_drops_out_instead_of_shifting_names():
    """`_select_rename` is keyed by name, so a missing column is not fatal."""
    df = pd.DataFrame({"Customer Id": [1], "Customer City": ["Chicago"]})

    dim = transform.build_dim_customers(df)

    assert list(dim.columns) == ["customer_id", "city"]
