"""Reduce a GLB in headless Blender from a JSON config (see lowpoly_workshop/reduce.py for its keys).

Run with the kit Blender launcher:
  blender -b --factory-startup --python-exit-code 1 -P reduce_mesh.py -- <config.json>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lowpoly_workshop.reduce import reduce_code


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    config = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    exec(compile(reduce_code(config), "reduce_mesh", "exec"), {"__name__": "__main__"})


if __name__ == "__main__":
    main()
