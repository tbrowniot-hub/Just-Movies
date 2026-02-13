from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_import_package():
    import MovieRipper

    assert hasattr(MovieRipper, "__version__")
