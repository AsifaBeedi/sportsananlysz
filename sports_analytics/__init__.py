from __future__ import annotations

import sys
from pathlib import Path
from pkgutil import extend_path


_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent
_SRC_DIR = _PROJECT_ROOT / "src"
_SRC_PACKAGE_DIR = _SRC_DIR / "sports_analytics"

# Make `src` importable for sibling packages like `biomechanics`.
if _SRC_DIR.is_dir():
    src_dir_str = str(_SRC_DIR)
    if src_dir_str not in sys.path:
        sys.path.insert(0, src_dir_str)

# Allow `sports_analytics.*` submodules to resolve from `src/sports_analytics`.
__path__ = extend_path(__path__, __name__)
if _SRC_PACKAGE_DIR.is_dir():
    src_package_str = str(_SRC_PACKAGE_DIR)
    if src_package_str not in __path__:
        __path__.append(src_package_str)

