"""Make the project importable from `tests/` without installing it.

The pipeline runs as scripts from the repo root (`python main.py`), not as an
installed package, so the root has to be on `sys.path` for `import config` and
`from src import ...` to resolve the same way in tests as at runtime.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
