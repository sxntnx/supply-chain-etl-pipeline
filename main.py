"""Pipeline entry point.

Wires the three stages together and reports a single end-to-end runtime.
Run with:  python main.py
"""

import time

from src.extract import extract
from src.load import load
from src.transform import transform
from src.utils import get_logger

log = get_logger("pipeline")


def run() -> None:
    log.info("Supply Chain ETL Pipeline - START")
    start = time.perf_counter()

    log.info("[1/3] EXTRACT")
    raw = extract()

    log.info("[2/3] TRANSFORM")
    tables = transform(raw)

    log.info("[3/3] LOAD")
    load(tables)

    elapsed = time.perf_counter() - start
    log.info("Pipeline completed in %.2fs", elapsed)


if __name__ == "__main__":
    run()
