"""Stage 1 — EXTRACT.

Load the raw supply chain CSV into a DataFrame. This stage does no cleaning:
its only job is to read the source faithfully and report what arrived, so that
data-quality issues are handled (and visible) downstream in TRANSFORM.
"""

from pathlib import Path

import pandas as pd

import config
from src.utils import fmt_int, get_logger

log = get_logger("extract")


def extract(csv_path: Path = config.RAW_CSV_PATH) -> pd.DataFrame:
    """Read the raw CSV and return it as a DataFrame.

    Parameters
    ----------
    csv_path:
        Location of the source CSV. Defaults to the configured raw path.

    Raises
    ------
    FileNotFoundError
        If the source file is missing, with guidance on how to obtain it.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at '{csv_path}'.\n"
            f"  → Download it from Kaggle (DataCo Smart Supply Chain), or\n"
            f"  → Run `python scripts/generate_sample_data.py` to create a "
            f"synthetic sample for testing the pipeline."
        )

    df = pd.read_csv(csv_path, encoding=config.RAW_CSV_ENCODING)
    log.info(
        "Extracted %s rows x %s columns",
        fmt_int(len(df)),
        fmt_int(df.shape[1]),
    )
    return df
