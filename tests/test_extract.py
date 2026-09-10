"""Tests for the EXTRACT stage."""

import pandas as pd
import pytest

from src import extract


def test_extract_reads_the_csv_faithfully(tmp_path):
    """Extract does no cleaning: what is in the file is what comes back."""
    csv = tmp_path / "raw.csv"
    pd.DataFrame({"Customer City": ["  caguas "], "Sales": [10.0]}).to_csv(
        csv, index=False, encoding="latin-1"
    )

    df = extract.extract(csv_path=csv)

    assert df.shape == (1, 2)
    assert df["Customer City"].iloc[0] == "  caguas "


def test_missing_source_file_says_how_to_get_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="generate_sample_data"):
        extract.extract(csv_path=tmp_path / "absent.csv")
