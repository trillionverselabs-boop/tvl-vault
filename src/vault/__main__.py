"""`python -m vault` — the package's entrypoint.

Without this file `python -m vault` fails with "No module named vault.__main__;
'vault' is a package and cannot be directly executed", which is exactly the
command `scripts/rebuild.sh` runs. `scripts/rebuild.sh` sets PYTHONPATH=src and
calls it; this file is the thing it calls.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
