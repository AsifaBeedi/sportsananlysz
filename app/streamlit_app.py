from __future__ import annotations

import runpy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_DASHBOARD = PROJECT_ROOT / "streamlit_app.py"


if __name__ == "__main__":
    runpy.run_path(str(ROOT_DASHBOARD), run_name="__main__")
