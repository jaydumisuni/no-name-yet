"""IDE-friendly launcher for Sergeant.

Run this file from PyCharm or VS Code with the same arguments as `main-review`.
"""

from __future__ import annotations

from main_review.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
