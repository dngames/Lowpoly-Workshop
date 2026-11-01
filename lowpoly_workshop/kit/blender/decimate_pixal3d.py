"""Reduce a Pixal3D raw GLB (`inputs/pixal3d_raw.glb`) in Blender to the asset's low-poly budget.

Run with the kit Blender launcher:
  blender -b --factory-startup --python-exit-code 1 -P decimate_pixal3d.py -- <asset_dir> [budget height node_name ground rotate_front]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lowpoly_workshop.pixal3d import blender_mcp_decimate_code


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    folder = argv[0]
    budget = int(argv[1]) if len(argv) > 1 and argv[1] else None
    height = float(argv[2]) if len(argv) > 2 and argv[2] else None
    node_name = argv[3] if len(argv) > 3 and argv[3] else None
    ground = (argv[4] == "1") if len(argv) > 4 else None
    rotate_front = (argv[5] == "1") if len(argv) > 5 else True
    code = blender_mcp_decimate_code(
        folder,
        budget=budget,
        height=height,
        node_name=node_name,
        ground=ground,
        rotate_front=rotate_front,
    )
    exec(compile(code, "decimate_pixal3d", "exec"), {"__name__": "__main__"})


if __name__ == "__main__":
    main()
