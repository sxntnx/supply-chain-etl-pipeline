# Working in this repo

An ETL pipeline that turns a wide, dirty supply chain export into a star schema
in PostgreSQL (Neon) or SQLite. Read `README.md` for the what; this file is the
how.

## Environment

Use the project virtualenv, not the system Python:

```bash
python -m venv .venv                       # first time only
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Then run everything through `.\.venv\Scripts\python.exe` (or activate the
environment). `requirements.txt` is the runtime; `requirements-dev.txt` adds
pytest and ruff.

## Commands

```bash
python scripts/generate_sample_data.py --rows 20000   # synthetic source CSV
python main.py                                        # extract, transform, load
python scripts/plot_kpis.py                           # reports/kpi_dashboard.png
pytest                                                # 31 tests
ruff check .                                          # line length 100
```

Run `ruff check .` and `pytest` before pushing. CI runs both plus a full
pipeline run, so a red build here is a red build there.

## Storage backends

`DB_BACKEND` selects the destination: `sqlite` (default, zero setup) or
`postgres` (needs `DATABASE_URL`). Extract and transform are identical either
way; only `load.py` branches. `.env` holds the real connection string, is
git-ignored, and must never be printed, pasted into a commit, or echoed into a
log. Set `DB_BACKEND=sqlite` in the environment for a local run that must not
touch the cloud database.

## Invariants — do not break these

The star schema is only useful if the dimensions are joinable. These hold by
construction in `scripts/generate_sample_data.py` and are pinned by tests in
`tests/test_sample_data.py`:

- a product name resolves to exactly one id, category, department and list price
- a category belongs to exactly one department
- a line's selling price derives from that product's list price
- scheduled shipping days are a property of the shipping mode, and premium modes
  miss the promise less often than Standard Class
- margin varies by category and by region, with enough noise that no cut
  separates cleanly

An earlier generator drew name, category, department and price independently per
product id. Every row looked fine and every `GROUP BY` was nonsense: 400
products with 10 distinct names, one name across 4 categories, all 8 categories
under all 7 departments. If a change makes any test in that file fail, the fix
is the change, not the test.

Two more that are easy to reintroduce:

- `method="multi"` binds rows x columns parameters per INSERT, and SQLite caps
  that. `load._chunksize` clamps the configured chunk size per backend.
- `str.title()` capitalizes after an apostrophe. `transform.normalize_text`
  undoes that, because a product name is an entity key.

## Conventions

- Each transform step is a small pure function, tested in isolation.
- Comments explain why, not what. Docstrings carry the reasoning behind a
  design choice, not a restatement of the signature.
- Paths, PII columns and settings live in `config.py`. No module hard-codes a
  filesystem location.
- `data/raw/*.csv` and `database/*.db` are generated and git-ignored. Never
  commit them.
