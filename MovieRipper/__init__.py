from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_FALLBACK_VERSION = "0.3.1"

try:
    __version__ = version("MovieRipper")
except PackageNotFoundError:
    __version__ = _FALLBACK_VERSION
