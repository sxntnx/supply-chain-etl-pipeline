"""Integrity tests for the synthetic data generator.

The point of these is the referential integrity of the product dimension. An
earlier generator drew name, category, department and price independently per
product id, which produced a warehouse that could not be aggregated: one name
spread across 40 ids, 4 categories and a 20x price range. These tests fail if
that ever comes back.
"""

import pandas as pd
import pytest

from scripts import generate_sample_data as gen
from src import transform


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return gen.generate(4_000)


def test_catalog_product_names_are_unique():
    names = [name for name, _category, _price in gen.CATALOG]

    assert len(names) == len(set(names))


def test_every_category_belongs_to_exactly_one_department():
    catalog = gen.build_catalog()

    assert catalog.groupby("category")["department"].nunique().max() == 1


def test_catalog_categories_are_all_known():
    categories = {category for _name, category, _price in gen.CATALOG}

    assert categories == set(gen.CATEGORY_DEPARTMENT)


def test_catalog_prices_are_positive():
    assert all(price > 0 for _name, _category, price in gen.CATALOG)


def test_a_product_name_resolves_to_one_entity(sample):
    """Same name => same id, category, department and list price. Always."""
    per_name = sample.groupby("Product Name").agg(
        {
            "Product Card Id": "nunique",
            "Category Name": "nunique",
            "Department Name": "nunique",
            "Product Price": "nunique",
        }
    )

    assert (per_name == 1).all().all()


def test_category_never_spans_departments_in_generated_rows(sample):
    per_category = sample.groupby("Category Name")["Department Name"].nunique()

    assert per_category.max() == 1


def test_selling_price_tracks_the_products_list_price(sample):
    ratio = sample["Order Item Product Price"] / sample["Product Price"]

    assert ratio.between(0.94, 1.06).all()


def test_sales_equal_price_times_quantity(sample):
    expected = sample["Order Item Product Price"] * sample["Order Item Quantity"]

    assert (sample["Sales"] - expected).abs().max() < 0.01


def test_scheduled_days_are_a_property_of_the_shipping_mode(sample):
    per_mode = sample.groupby("Shipping Mode")["Days for shipment (scheduled)"].nunique()

    assert per_mode.max() == 1


def test_premium_shipping_misses_its_promise_less_often(sample):
    late = sample.groupby("Shipping Mode")["Late_delivery_risk"].mean()

    assert late["Same Day"] < late["First Class"] < late["Standard Class"]


def test_delivery_status_agrees_with_the_dates(sample):
    delay = sample["Days for shipping (real)"] - sample["Days for shipment (scheduled)"]
    shipped = sample["Delivery Status"] != "Shipping canceled"

    assert (sample.loc[shipped & (delay > 0), "Delivery Status"] == "Late delivery").all()
    assert (sample.loc[shipped & (delay == 0), "Delivery Status"] == "Shipping on time").all()


def test_margin_differs_by_category(sample):
    margin = sample.groupby("Category Name")["Order Item Profit Ratio"].mean()

    # Wide enough to be a real signal, not so wide it is a giveaway.
    assert 0.05 < margin.max() - margin.min() < 0.45


def test_dim_products_has_one_row_per_real_product(sample):
    tables = transform.transform(sample)
    dim = tables["dim_products"]

    assert len(dim) == len(gen.CATALOG)
    assert dim["product_name"].nunique() == len(dim)
    assert dim.groupby("category")["department"].nunique().max() == 1


def test_generator_injects_duplicates_for_the_dedup_step_to_find(sample):
    assert sample.duplicated().sum() > 0
