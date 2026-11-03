"""Hermetic launcher: `python.exe launch.py <asset> <command> ...` (embedded python ignores PYTHONPATH)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "workshop"))

from lowpoly_workshop.cli import main

if __name__ == "__main__":
    main(sys.argv[1:])
